import os
import sys
import uuid

from dataclasses import asdict, dataclass, is_dataclass
from typing import Any, Tuple, Union

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
from dman.core.storables import (
    STO_TYPE,
    is_storable,
    storable_type,
    storable_name,
    FileSystem,
    config
)
from dman.core.path import target, mount, Target, Mount, AUTO


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
        fs: FileSystem,
        subdir: os.PathLike = '',
    ):
        super().__init__()
        self.fs = fs
        self.subdir = subdir
    
    @property
    def directory(self):
        return self.fs.abspath(self.subdir, validate=False)
    
    def __repr__(self):
        return f'Context({self.directory})'

    @classmethod
    def mount(
        cls,
        key: str,
        *,
        subdir: os.PathLike = "",
        cluster: bool = True,
        generator: str = AUTO,
        base: os.PathLike = None,
        gitignore: bool = True,
    ):
        """Get a context from a mount point.
            The path of the file is determined as described below.

                If the files are clustered then the path is ``<base>/<generator>/<subdir>/<key>/<key>.<ext>``
                If cluster is set to False then the path is ``<base>/<generator>/<subdir>/<key>.<ext>``

                When base is not provided then it is set to .dman if
                it does not exist an exception is raised.

                When generator is not provided it will automatically be set based on
                the location of the script relative to the .dman folder
                (again raising an exception if it is not found). For example
                if the script is located in ``<project-root>/examples/folder/script.py``
                and .dman is located in ``<project-root>/.dman``.
                Then generator is set to cache/examples:folder:script (i.e.
                the / is replaced by : in the output).

        Args:
            key (str):  Key for the file.
            subdir (os.PathLike, optional): Specifies optional subdirectory in generator folder. Defaults to "".
            cluster (bool, optional): A subfolder ``key`` is automatically created when set to True. Defaults to True.
            generator (str, optional): Specifies the generator that created the file. Defaults to script label.
            base (os.PathLike, optional): Specifies the root folder. Defaults to ".dman".
            gitignore (bool, optional): Specifies whether files added to this mount point should be ignored.
        """
        return cls(FileSystem.mount(key, subdir=subdir, cluster=cluster, generator=generator, base=base, gitignore=gitignore))

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

    def absolute(self, target: os.PathLike):
        if not isinstance(target, Target):
            target = Target.from_path(target)
        return target.update(subdir=os.path.join(self.subdir, target.subdir))

    def write(self, target: os.PathLike, storable):
        try:
            target = Target.from_path(target)
            local, _target = self.open(target)
            return target.update(name=_target.name), self.fs.write(storable, local.absolute(_target), local, open=False)
        except SerializationError:
            raise
        except Exception:
            res = ExcUnWritable.from_exception(
                *sys.exc_info(),
                type=storable_name(storable),
                info="Exception encountered while writing.",
                ignore=0,
            )
            self._process_invalid("An error occurred while writing.", res)
            return target.update(name=_target.name), res

    def read(self, target: os.PathLike, sto_type):
        try:
            local, target = self.open(target, choice='_ignore')
            return self.fs.read(sto_type, local.absolute(target), local)
        except FileNotFoundError:
            if not isinstance(sto_type, str):
                sto_type = getattr(sto_type, STO_TYPE, None)
            res = NoFile(type=sto_type, info=f"Missing Target: {target}.")
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
                ignore=0,
            )
            self._process_invalid("An error occurred while reading.", res)
            return res

    def remove(self, obj, target: os.PathLike=None):
        """Remove object, stored at specified target."""
        if target is None:
            local = self
        else:
            # Parse the target
            local, target = self.open(target, choice='ignore')

            # Remove the file associated with the object
            local.fs.delete(target)  

        # Remove files created by the object
        tp = type(obj)
        if is_removable(obj):
            with log.layer(tp.__name__, "remove"):
                inner_remove = getattr(obj, REMOVE, None)
                if inner_remove is not None:
                    inner_remove(local)
                return

        if is_dataclass(obj):
            obj = asdict(obj)

        if isinstance(obj, (tuple, list)):
            with log.layer(tp.__name__, "remove"):
                for x in obj[:]:
                    local.remove(x)
        elif isinstance(obj, dict):
            with log.layer(tp.__name__, "remove"):
                for k in obj.keys():
                    local.remove(obj[k])
    
    def open(self, target: os.PathLike, *, choice='ignore') -> Tuple['Context', Target]:
        target = self.fs.open(self.absolute(target), choice=choice)
        local = self if target.subdir == '' else self.__class__(
            fs=self.fs, subdir=target.subdir)
        return local, Target(name=target.name)


def is_unloaded(obj):
    return isinstance(obj, Unloaded)


@dataclass
class Unloaded:
    type: str
    target: os.PathLike
    base: os.PathLike
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
        self, content: Any, target: Target = None, preload: bool = False
    ):
        self._content = content
        self._target = Target() if target is None else target

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
        if self._target.is_complete():
            return self._target
        
        base = Target(stem=f"{uuid.uuid4()}", subdir=f"{uuid.uuid4()}")
        if is_serializable(self._content) or is_dataclass(self._content):
            base = base.update(suffix='.json')
        else:
            base = base.update(suffix=config.default_suffix)
        request = Target(suffix=getattr(self._content, EXTENSION, AUTO))
        self._target = base.merge(request, self._target)
        return self._target

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
            target, self.exceptions.write = context.write(self.target, self._content)
            return target
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
        target: Target = self.store(context)
        self._target = target
        res = {
            "target": str(target) if target.is_complete() else tuple(target),
            "sto_type": sto_type,
        }
        if self.preload:
            res["preload"] = self.preload
        if not self.exceptions.empty():
            res["exceptions"] = serialize(self.exceptions, context, content_only=True)

        return res

    @classmethod
    def __deserialize__(cls, serialized: dict, context: BaseContext):
        target = serialized.get("target", None)
        if isinstance(target, str):
            target = Target.from_path(target)
        if isinstance(target, list):
            target = Target(*target)
        sto_type = serialized.get("sto_type")
        preload = serialized.get("preload", False)

        # load previous exceptions
        exceptions = serialized.get("exceptions", None)
        if exceptions is None:
            exceptions = _RecordExceptions()
        else:
            exceptions = _RecordExceptions.__deserialize__(exceptions)

        # try to load the contents of the record
        if isinstance(context, Context) and isinstance(target, Target):
            content = Unloaded(
                sto_type, target, context.directory, context
            )
        elif not isinstance(context, Context):
            exceptions.read = UnReadable(
                type=sto_type,
                info=f"Invalid context passed to Record({sto_type}, target={target}).",
                target=target,
            )
            context._process_invalid(
                "Exception encountered during read.", exceptions.read
            )
            content = Undefined(sto_type)
        else:
            exceptions.read = UnReadable(
                type=sto_type,
                info=f"Invalid target recovered Record({sto_type}, target={target}).",
                target=target,
            )
            context._process_invalid(
                "Exception encountered during read.", exceptions.read
            )
            content = Undefined(sto_type)

        out = cls(content=content, target=target, preload=preload)
        if preload:
            out.load()
        out.exceptions = exceptions
        return out

    def __remove__(self, context: BaseContext):
        if isinstance(context, Context):
            if isvalid(self.content):
                return context.remove(self.content, self.target)
            log.warning(
                "Loaded content is invalid. Could not continue removing.", "record"
            )
        log.warning("Tried removing with invalid context type.", "record")


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
        Target(stem=stem, suffix=suffix, name=name, subdir=subdir),
        preload,
    )


def remove(obj, context: Context = None):
    if not isinstance(context, Context):
        return
    context.remove(obj)
