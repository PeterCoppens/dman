from contextlib import suppress

from dataclasses import asdict, is_dataclass, dataclass
import os
from typing import Type, Union, Any, Callable, Optional

from dman.core.serializables import (
    is_serializable,
    serialize,
    deserialize,
    BaseContext,
    _call_optional_context,
    SerializationError,
)
from dman.utils import sjson
from dman.utils.regex import substitute
from dman.utils.user import prompt_user
from dman.core import log
from dman.core.path import TargetException, UserQuitException, get_root_path, normalize_path, mount, target, Mount, Target, AUTO
from dman.utils.smartdataclasses import configclass, optionfield


STO_TYPE = "_sto__type"
WRITE = "__write__"
READ = "__read__"
LOAD = "__load__"

__storable_types = dict()
__custom_storable = dict()


@configclass
@dataclass
class Config:
    on_retouch: str = optionfield(
        ["prompt", "quit", "ignore", "auto"], default="ignore"
    )
    default_suffix: str = '.sto'


config = Config()


def storable_type(obj):
    cls = obj if isinstance(obj, type) else type(obj)
    if cls in __custom_storable:
        return __custom_storable[cls][0]
    return getattr(obj, STO_TYPE, None)


def storable_name(obj):
    return obj if isinstance(obj, str) else getattr(obj, STO_TYPE, None)


def is_storable(obj):
    return storable_type(obj) in __storable_types


def is_storable_type(type: str):
    return type in __storable_types


def register_storable(
    name: str,
    cls: Type[Any],
    *,
    write: Callable[[Any, Optional["BaseContext"]], Any] = None,
    read: Callable[[Any, Optional["BaseContext"]], Any] = None,
):
    """
    Register a class as a storable type with a given name
    """
    __storable_types[name] = cls
    if write is not None and read is not None:
        __custom_storable[cls] = (name, write, read)


def get_custom_storable(cls: Type[Any], default=None):
    return __custom_storable.get(cls, default)


def storable(
    cls=None,
    /,
    *,
    name: str = None,
    ignore_serializable: bool = None,
    ignore_dataclass: bool = False,
):
    def wrap(cls):
        local_name = name
        if local_name is None:
            local_name = getattr(cls, "__name__")

        setattr(cls, STO_TYPE, local_name)
        register_storable(local_name, cls)

        if not ignore_serializable and is_serializable(cls):
            if getattr(cls, WRITE, None) is None:
                setattr(cls, WRITE, _write__serializable)

            if getattr(cls, READ, None) is None:
                setattr(cls, READ, _read__serializable)

        elif not ignore_dataclass and is_dataclass(cls):
            if getattr(cls, WRITE, None) is None:
                setattr(cls, WRITE, _write__dataclass)

            if getattr(cls, READ, None) is None:
                setattr(cls, READ, _read__dataclass)

        if not hasattr(cls, READ) or not hasattr(cls, WRITE):
            raise ValueError(
                f"Class {cls} could not be made serializable. Provide a manual definition of a `__write__` and `__read__` method."
            )

        return cls

    # See if we're being called as @storable or @storable().
    if cls is None:
        # We're called with parens.
        return wrap

    # We're called as @storable without parens.
    return wrap(cls)


def _write__dataclass(self, path: os.PathLike):
    with open(path, "w") as f:
        sjson.dump(asdict(self), f, indent=4)


@classmethod
def _read__dataclass(cls, path: os.PathLike):
    with open(path, "r") as f:
        return cls(**sjson.load(f))


def _write__serializable(self, path: os.PathLike, context: BaseContext = None):
    with open(path, "w") as f:
        sjson.dump(serialize(self, context, content_only=True), f, indent=4)


@classmethod
def _read__serializable(cls, path: os.PathLike, context: BaseContext = None):
    with open(path, "r") as f:
        return deserialize(sjson.load(f), context, ser_type=cls)


class WriteException(RuntimeError):
    ...


class ReadException(RuntimeError):
    ...


def write(storable, path: os.PathLike, context: BaseContext = None):
    _, inner_write, _ = get_custom_storable(type(storable), (None, None, None))
    if inner_write is None:
        inner_write = getattr(storable, WRITE, None)
    else:
        return _call_optional_context(inner_write, storable, path, context=context)

    if inner_write is None:
        raise WriteException("Could not find __write__ method.")
    return _call_optional_context(inner_write, path, context=context)


def read(type: Union[str, Type], path: os.PathLike, context: BaseContext = None, **kwargs):
    if isinstance(type, str):
        type = __storable_types.get(type, None)
        if type is None:
            raise ReadException(f"Unregistered type: {type}.")

    _, _, inner_read = get_custom_storable(type, (None, None, None))
    if inner_read is None:
        inner_read = getattr(type, READ, None)
    if inner_read is None:
        raise ReadException(f"Could not find __read__ method.")
    return _call_optional_context(inner_read, path, context=context, **kwargs)


class FileSystemError(SerializationError):
    ...


class FileSystem:
    def __init__(self, mnt: Mount):
        """Initialize a new FileSystem at the specified mount point."""
        self.mnt = mnt

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
        """Get a file system from a mount point.
            The path of the directory is determined as described below.

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
        return cls(mount(key, subdir=subdir, cluster=cluster, generator=generator, base=base, gitignore=gitignore))

    def __repr__(self):
        return f"FileSystem({self.mnt})"

    def abspath(self, path: os.PathLike, *, validate: bool = False):
        return self.mnt.abspath(path, validate=validate)

    def write(
        self,
        storable,
        target: os.PathLike,
        context: BaseContext = None,
        *,
        open: bool = False
    ):
        """Write a storable to disk, keeping in mind previous writes.

        Args:
            storable: The storable to write to disk.
            target (os.PathLike): The target to which to write.
            context (BaseContext, optional): The context for serialization. Defaults to None.
            choice (str, optional): The default choice. Defaults to None.

        Raises:
            FileSystemError: If the quit choice was passed
                and the system tries to write to the same file twice.
            TargetException: If the specified target was incomplete.
        """
        try:
            target = self.mnt.open(target) if open else target
            return write(storable, self.mnt.abspath(target), context)
        except UserQuitException as e:  
            raise FileSystemError(*e.args)
        
    def read(self, sto_type, target: os.PathLike, context: BaseContext = None):
        """Read a file from the specified target with specified type."""
        return read(sto_type, self.mnt.abspath(target), context)

    def delete(self, target: os.PathLike):
        """Remove file at specified target."""

        # Remove from touched
        with suppress(ValueError):
            self.mnt.remove(target)

        # Remove file if it exists.
        path = self.mnt.abspath(target)
        if os.path.exists(path):
            log.io(f'Deleting file: "{target}".', "fs")
            os.remove(path)
        
    def open(self, target: os.PathLike, *, validate: bool = True, choice: str = None):
        return self.mnt.open(target, validate=validate, choice=choice)
    
    def close(self):
        self.mnt.close()
    
    def __enter__(self): ...

    def __exit__(self, *_):
        self.close()
