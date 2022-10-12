import copy
import os

from dataclasses import asdict, dataclass, fields, is_dataclass
import sys
from types import TracebackType
from typing import Any, Type
import uuid
from dman.core import log
from dman.core.serializables import (
    SER_CONTENT,
    SER_TYPE,
    BaseInvalid,
    deserialize,
    is_serializable,
    serializable,
    BaseContext,
    serialize,
    ValidationError,
    Trace,
    isvalid,
)
from dman.utils import sjson
from dman.core.serializables import (
    ExcUndeserializable,
    ExcUnserializable,
    Unserializable,
    Undeserializable,
)
from dman.utils.smartdataclasses import AUTO, overrideable
from dman.core.storables import (
    STO_TYPE,
    is_storable,
    storable_type,
    read,
    write,
    storable,
    _read__serializable,
)
from dman.core.path import logger_context, normalize_path


REMOVE = "__remove__"


@serializable(name="__no_file")
class NoFile(Unserializable):
    def __repr__(self):
        return f"NoFile: {self.type}"


@serializable(name="__un_writable")
class UnWritable(Unserializable):
    def __repr__(self):
        return f"UnWritable: {self.type}"


@serializable(name="__exc_un_writable")
class ExcUnWritable(ExcUnserializable):
    def __repr__(self):
        return f"ExcUnWritable: {self.type}"


@serializable(name="__un_readable")
@dataclass
class UnReadable(Unserializable):
    target: str

    def __repr__(self):
        return f"UnReadable: {self.type}"

    def __serialize__(self):
        res = super().__serialize__()
        res["target"] = self.target
        return res

    @classmethod
    def __deserialize__(cls, ser: dict, context):
        target = ser.pop("target")
        res: Unserializable = Unserializable.__deserialize__(ser, context)
        return cls(type=res.type, info=res.info, target=target)


@serializable(name="__exc_un_readable")
@dataclass
class ExcUnReadable(ExcUnserializable):
    target: str

    def __serialize__(self):
        res = super().__serialize__()
        res["target"] = self.target
        return res

    @classmethod
    def __deserialize__(cls, ser: dict, context):
        target = ser.pop("target")
        res: ExcUnserializable = ExcUnserializable.__deserialize__(ser, context)
        return cls(res.type, res.info, res.trace, target=target)


class Context(BaseContext):
    def __init__(
        self,
        directory: os.PathLike,
        parent: "Context" = None,
        children: dict = None,
        validate: bool = None,
    ):
        super().__init__(validate=validate)
        self.directory = directory
        self.parent = parent
        self.children = dict() if children is None else children

    def _serialize__list(self, ser: list):
        res = []
        is_model = False
        for itm in ser:
            if is_storable(itm):
                itm = record(itm)
                is_model = True
            res.append(self.serialize(itm))
        if is_model:
            res = {SER_TYPE: "_ser__mlist", SER_CONTENT: {"store": res}}
        return res

    def _serialize__dict(self, ser: dict):
        res = {}
        is_model = False
        for k, v in ser.items():
            if is_storable(v):
                v = record(v)
                is_model = True
            k = self.serialize(k)
            res[k] = self.serialize(v)
        if is_model:
            res = {SER_TYPE: "_ser__mdict", SER_CONTENT: {"store": res}}
        return res

    @staticmethod
    def _sto_type(obj):
        return obj if isinstance(obj, str) else getattr(obj, STO_TYPE, None)

    def write(self, target: str, storable):
        self.open()
        path = os.path.join(self.directory, target)
        log.io(f'writing to file: "{normalize_path(path)}".', "context")
        try:
            return write(storable, path, self)
        except Exception as e:
            if isinstance(e, ValidationError):
                raise e
            res = ExcUnWritable.from_exception(
                *sys.exc_info(),
                type=self._sto_type(storable), 
                info="Exception encountered while writing.", 
                ignore=2
            )
            self._process_invalid("An error occurred while writing.", res)
            return res

    def read(self, target: str, sto_type):
        try:
            path = os.path.join(self.directory, target)
            log.io(f'reading from file: "{normalize_path(path)}".', "context")
            return read(sto_type, path, self)
        except FileNotFoundError:
            if not isinstance(sto_type, str):
                sto_type = getattr(sto_type, STO_TYPE, None)
            res = NoFile(type=sto_type, info=f"Missing File: {path}.")
            self._process_invalid("An error occurred while writing.", res)
            return res
        except Exception as e:
            if isinstance(e, ValidationError):
                raise e
            res = ExcUnReadable.from_exception(
                *sys.exc_info(),
                type=self._sto_type(sto_type),
                info="Exception encountered while reading.",
                target=target,
            )
            self._process_invalid("An error occurred while reading.", res)
            return res

    def delete(self, target: str):
        path = os.path.join(self.directory, target)
        if os.path.exists(path):
            log.io(f'Deleting file: "{normalize_path(path)}".', "context")
            os.remove(path)
        self.clean()

    def remove(self, obj):
        original = obj
        if is_removable(obj):
            with log.layer(type(obj).__name__, "remove"):
                inner_remove = getattr(obj, REMOVE, None)
                if inner_remove is not None:
                    inner_remove(self)
                return

        if is_dataclass(obj):
            obj = asdict(obj)

        if isinstance(obj, (tuple, list)):
            with log.layer(type(obj).__name__, "remove"):
                for x in obj[:]:
                    self.remove(x)
        elif isinstance(obj, dict):
            with log.layer(type(original).__name__, "remove"):
                for k in obj.keys():
                    self.remove(obj[k])

    def open(self):
        if not os.path.isdir(self.directory):
            log.io(f'Creating directory "{normalize_path(self.directory)}".')
            os.makedirs(self.directory)

    def clean(self):
        if self.parent is None:
            return  # do not clean root
        if os.path.isdir(self.directory) and len(os.listdir(self.directory)) == 0:
            log.io(f'Removing empty directory "{normalize_path(self.directory)}".')
            os.rmdir(self.directory)
            self.parent.clean()

    def normalize(self, other: os.PathLike):
        return os.path.relpath(
            os.path.join(self.directory, other), start=self.directory
        )

    def make_child(self, other: os.PathLike):
        res = self.__class__(os.path.join(self.directory, other), parent=self)
        self.children[other] = res
        res.validate = self.validate
        return res

    def join(self, other: os.PathLike) -> "Context":
        # normalize
        other = self.normalize(other)
        if other == ".":
            return self

        head, tail = os.path.split(other)
        if len(head) > 0:
            return self.join(head).join(tail)

        res = self.children.get(other, None)
        if res is not None:
            return res

        return self.make_child(other)


class _GenerateContext(Context):
    def __init__(self, verbose: bool, **kwargs):
        super().__init__(**kwargs)
        self._logger_context = logger_context(verbose)
        self._logger_context.__enter__()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self._logger_context.__exit__(*_)

    def make_child(self, other: os.PathLike):
        res = Context(os.path.join(self.directory, other), parent=self)
        self.children[other] = res
        res.validate = self.validate
        return res


def context(directory: str = None, *, verbose: bool = None, validate: bool = None):
    """Create a context factory.

    :param directory (str): if specified a context instance at the directory is provided.
        Otherwise a factory is returned.
    :param verbose (int): verbosity level, defaults to the current level
    :param validate (bool): validate the output, defaults to False
    """
    return _GenerateContext(verbose, directory=directory, validate=validate)


@serializable(name="__ser_rec_config")
@overrideable(frozen=True)
class RecordConfig:
    subdir: os.PathLike
    suffix: str
    stem: str

    @classmethod
    def from_target(cls, /, *, target: str):
        subdir, name = os.path.split(target)
        return cls.from_name(name=name, subdir=subdir)

    @classmethod
    def from_name(cls, /, *, name: str, subdir: os.PathLike = AUTO):
        if name == AUTO:
            return cls(subdir=subdir)

        split = name.split(".")
        if len(split) == 1:
            split.append("")

        *stem, suffix = split
        if len(suffix) > 0:
            suffix = "." + suffix
        return cls(subdir=subdir, suffix=suffix, stem="".join(stem))

    @property
    def name(self):
        if self.stem == AUTO:
            return AUTO
        return self.stem + ("" if self.suffix == AUTO else self.suffix)

    @property
    def target(self):
        return os.path.normpath(os.path.join(".", self.subdir, self.name))

    def __serialize__(self):
        log.info(f"target={self.target}", "record")
        return self.target

    @classmethod
    def __deserialize__(cls, serialized):
        log.info(f"target={serialized}", "record")
        return cls.from_target(target=serialized)


def is_unloaded(obj):
    return isinstance(obj, Unloaded)


@dataclass
class Unloaded:
    type: str
    target: str
    base: str
    context: Context

    @property
    def path(self):
        return os.path.join(self.base, self.target)

    def __load__(self):
        return self.context.read(self.target, self.type)

    def __repr__(self) -> str:
        return f"UL[{self.type}]"


@serializable(name="_record_exceptions")
@dataclass
class _RecordExceptions:
    write: Any = None
    read: Any = None

    def __serialize__(self):
        res = {}
        if self.write is not None:
            res["write"] = serialize(self.write)
        if self.read is not None:
            res["read"] = serialize(self.read)
        return res
    
    @classmethod
    def __deserialize__(cls, ser: dict):
        return cls(ser.get('write', None), ser.get('read', None))

    def empty(self):
        return self.write is None and self.read is None


@dataclass
class Undefined:
    type: str

    def __repr__(self) -> str:
        return f"ERR[{self.type}]"


def is_undefined(obj):
    return isinstance(obj, Undefined)


@serializable(name="_ser__record")
class Record:
    EXTENSION = "__ext__"

    def __init__(
        self, content: Any, config: RecordConfig = None, preload: bool = False
    ):
        self._content = content

        if config is None:
            config = RecordConfig()
        self._config = config
        self._evaluated = False

        self.preload = preload
        self.exceptions = _RecordExceptions()

    def exists(self):
        return not isinstance(self.exceptions.read, NoFile)

    def isvalid(self, *, load: bool = False):
        if load:
            self.load()
        return self.exceptions.read is None

    @property
    def target(self):
        return self.config.target

    @property
    def config(self):
        if self._evaluated:
            return self._config

        base = RecordConfig(stem=f"{uuid.uuid4()}", subdir=f"{uuid.uuid4()}")
        if is_serializable(self._content) or is_dataclass(self._content):
            base = base << RecordConfig(suffix=".json")

        request = RecordConfig(suffix=getattr(self._content, Record.EXTENSION, AUTO))

        self._config: RecordConfig = base << request << self._config
        self._evaluated = True

        return self._config

    @property
    def sto_type(self):
        if is_unloaded(self._content) or is_undefined(self._content):
            return self._content.type
        return storable_type(self._content)

    @property
    def content(self):
        return self.load()

    @content.setter
    def content(self, value: Any):
        if not is_storable(value):
            raise ValueError("Expected storable type.")
        self._content = value

    def __repr__(self) -> str:
        content = self._content
        preload_str = ""
        if self.preload:
            preload_str = ", preload"
        if content is None:
            return f"Record(None, target={self.target}{preload_str})"
        if is_unloaded(content) or is_undefined(content):
            return f"Record({content}, target={self.target}{preload_str})"
        return f"Record({storable_type(content)}, target={self.target}{preload_str})"
    
    def load(self):
        if not is_unloaded(self._content):
            return self._content

        ul: Unloaded = self._content
        with log.layer("loading content", "record", owner="record"):
            content = ul.__load__()
            if isvalid(content):
                self.exceptions.read = None
            else:
                ul.context._process_invalid(
                    "Exception encountered while reading.",
                    content
                )
                self.exceptions.read = content
                return content
            self._content = content
        return self._content

    def store(self, context: BaseContext):
        if isinstance(context, Context):
            if is_unloaded(self._content) and self._content.base != context.directory:
                self.load()  # the target was moved
            elif self.exceptions.write is not None:
                self.load()  # the previous store failed
            elif is_unloaded(self._content):
                return  # no load needed

            # execute store
            target, local = Record.__parse(self.config, context)
            self.exceptions.write = local.write(target, self._content)
            if self.exceptions.write is not None:
                context._process_invalid(
                    f"Exception encountered while writing to {os.path.join(local.directory, target)}.",
                    self.exceptions.write
                )
        else:
            self.exceptions.write = UnWritable(
                type=self.sto_type, 
                info=f"Invalid context passed to Record({self.sto_type}, target={self.target})."
            )
            context._process_invalid('Exception encountered during write.', self.exceptions.write)

    @staticmethod
    def __parse(config: RecordConfig, context: Context):
        return config.name, context.join(config.subdir)

    def __serialize__(self, context: BaseContext):
        sto_type = self.sto_type
        self.store(context)
        res = {
            "target": serialize(self.config, content_only=True),
            "sto_type": sto_type,
        }
        if self.preload:
            res["preload"] = self.preload
        if not self.exceptions.empty():
            res["exceptions"] = serialize(self.exceptions, context, content_only=True)

        return res

    @classmethod
    def __deserialize__(cls, serialized: dict, context: BaseContext):
        config: RecordConfig = deserialize(
            serialized.get("target", ""), ser_type=RecordConfig
        )
        sto_type = serialized.get("sto_type")
        preload = serialized.get("preload", False)

        # load previous exceptions
        exceptions = serialized.get("exceptions", None)
        if exceptions is None:
            exceptions = _RecordExceptions()
        else:
            exceptions = _RecordExceptions.__deserialize__(exceptions)

        # try to load the contents of the record
        if isinstance(context, Context):
            target, local = Record.__parse(config, context)
            content = Unloaded(sto_type, target, context.directory, local)
        else:
            exceptions.read = UnReadable(
                type=sto_type,
                info=f"Invalid context passed to Record({sto_type}, target={config.target}).",
                target=config.target,
            )
            context._process_invalid(
                'Exception encountered during read.', 
                exceptions.read
            )
            content = Undefined(sto_type)

        out = cls(content=content, config=config, preload=preload)
        if preload:
            out.content
        out.exceptions = exceptions
        return out

    def __remove__(self, context: BaseContext):
        if isinstance(context, Context):
            target, local = Record.__parse(self.config, context)
            content = self.content
            if isvalid(content):
                local.remove(content)  # remove contents
                local.delete(target)  # remove this file
            else:
                log.warning("Loaded content is invalid. Could not continue removing.", "record")


def recordconfig(
    *, stem: str = AUTO, suffix: str = AUTO, name: str = AUTO, subdir: os.PathLike = ""
):
    if name != AUTO and (stem != AUTO or suffix != AUTO):
        raise ValueError("Either provide a name or suffix + stem.")

    config = RecordConfig.from_name(name=name, subdir=subdir)
    return config << RecordConfig(stem=stem, suffix=suffix)


def record(
    content: Any,
    /,
    *,
    stem: str = AUTO,
    suffix: str = AUTO,
    name: str = AUTO,
    subdir: os.PathLike = "",
    preload: str = False,
):
    """
    Wrap a storable object in a serializable record.
        The target path is specified as:

        * ``./subdir/stem+suffix`` or
        * ``./subdir/name``.

    :param content:         The storable object.
    :param str stem:        The stem of a file.
    :param str suffix:      The suffix or extension of the file (e.g. ``'.json'``).
    :param str name:        The full name of the file.
    :param str subdir:      The subdirectory in which to store te file.
    :param bool preload:    When ``True`` the file will be loaded during deserialization.

    :raises ValueError:     if a name and a stem and/or suffix are specified.
    """
    return Record(
        content,
        recordconfig(stem=stem, suffix=suffix, name=name, subdir=subdir),
        preload,
    )


def is_removable(obj):
    return hasattr(obj, REMOVE)


def remove(obj, context: Context = None):
    if not isinstance(context, Context):
        return
    context.remove(obj)
