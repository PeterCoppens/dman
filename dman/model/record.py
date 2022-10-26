import os
import sys
import uuid

from dataclasses import asdict, dataclass, is_dataclass
from typing import Any

from dman.core import log
from dman.core.serializables import (
    SER_CONTENT,
    SER_TYPE,
    deserialize,
    is_serializable,
    serializable,
    BaseContext,
    serialize,
    SerializationError,
    isvalid,
    ExcUnserializable,
    Unserializable,
)

from dman.utils.smartdataclasses import AUTO, overrideable
from dman.core.storables import (
    STO_TYPE,
    is_storable,
    storable_type,
    storable_name,
    FileSystem,
    config
)
from dman.core.path import logger_context


REMOVE = "__remove__"
EXTENSION = "__ext__"


def is_removable(obj):
    return hasattr(obj, REMOVE)


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
        fs: FileSystem = None
    ):
        super().__init__()
        if fs is None:
            fs = FileSystem(directory)
        self.fs = fs
        self.directory = fs.abspath(directory, validate=True)
    
    def abspath(self, path: os.PathLike):
        return self.fs.abspath(os.path.join(self.directory, path), validate=True)

    def normalize(self, path: os.PathLike):
        """Normalize a path relative to the current directory."""
        return os.path.relpath(self.abspath(path), start=self.directory)

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

    def make_valid(self, target: str):
        path = self.fs.make_valid(self.abspath(target))
        return self.normalize(path)

    def write(self, target: str, storable, *, choice: str = None):
        try:
            return self.fs.write(storable, self.abspath(target), self, choice=choice)
        except SerializationError:
            raise
        except Exception:
            res = ExcUnWritable.from_exception(
                *sys.exc_info(),
                type=storable_name(storable),
                info="Exception encountered while writing.",
                ignore=4,
            )
            self._process_invalid("An error occurred while writing.", res)
            return res

    def read(self, target: str, sto_type):
        try:
            path = self.abspath(target)
            return self.fs.read(sto_type, path, self)
        except FileNotFoundError:
            if not isinstance(sto_type, str):
                sto_type = getattr(sto_type, STO_TYPE, None)
            res = NoFile(type=sto_type, info=f"Missing File: {path}.")
            self._process_invalid("Could not find specified file.", res)
            return res
        except SerializationError:
            raise
        except Exception:
            res = ExcUnReadable.from_exception(
                *sys.exc_info(),
                type=storable_name(sto_type),
                info="Exception encountered while reading.",
                target=target,
                ignore=4,
            )
            self._process_invalid("An error occurred while reading.", res)
            return res

    def delete(self, target: str):
        self.fs.delete(target)

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

    def join(self, other: str):
        return self.__class__(other, self.fs)



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
        return Context(os.path.join(self.directory, other), parent=self)


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
    def from_target(cls, target: str):
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


@dataclass
class Undefined:
    type: str

    def __repr__(self) -> str:
        return f"ERR[{self.type}]"


def is_undefined(obj):
    return isinstance(obj, Undefined)


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
        return cls(ser.get("write", None), ser.get("read", None))

    def empty(self):
        return self.write is None and self.read is None


@serializable(name="_ser__record")
class Record:
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
        else:
            base = base << RecordConfig(suffix=config.default_suffix)

        request = RecordConfig(suffix=getattr(self._content, EXTENSION, AUTO))

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
                return self._content.target # no load needed

            # execute store
            local = context.join(self.config.subdir)
            target = local.make_valid(self.config.name)
            self.exceptions.write = local.write(target, self._content, choice='_ignore')
            return os.path.join(self.config.subdir, target)
        else:
            self.exceptions.write = UnWritable(
                type=self.sto_type,
                info=f"Invalid context passed to Record({self.sto_type}, target={self.target}).",
            )
            context._process_invalid(
                "Exception encountered during write.", self.exceptions.write
            )
            return self.target

    def __serialize__(self, context: BaseContext):
        sto_type = self.sto_type
        target = self.store(context)
        self._config = RecordConfig.from_target(target)
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
            content = Unloaded(
                sto_type, config.name, context.directory, context.join(config.subdir)
            )
        else:
            exceptions.read = UnReadable(
                type=sto_type,
                info=f"Invalid context passed to Record({sto_type}, target={config.target}).",
                target=config.target,
            )
            context._process_invalid(
                "Exception encountered during read.", exceptions.read
            )
            content = Undefined(sto_type)

        out = cls(content=content, config=config, preload=preload)
        if preload:
            out.load()
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
                log.warning(
                    "Loaded content is invalid. Could not continue removing.", "record"
                )


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


def remove(obj, context: Context = None):
    if not isinstance(context, Context):
        return
    context.remove(obj)
