from contextlib import suppress

from dataclasses import asdict, is_dataclass, dataclass
from os import PathLike
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
from dman.core.path import get_root_path, normalize_path
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


def _write__dataclass(self, path: PathLike):
    with open(path, "w") as f:
        sjson.dump(asdict(self), f, indent=4)


@classmethod
def _read__dataclass(cls, path: PathLike):
    with open(path, "r") as f:
        return cls(**sjson.load(f))


def _write__serializable(self, path: PathLike, context: BaseContext = None):
    with open(path, "w") as f:
        sjson.dump(serialize(self, context, content_only=True), f, indent=4)


@classmethod
def _read__serializable(cls, path: PathLike, context: BaseContext = None):
    with open(path, "r") as f:
        return deserialize(sjson.load(f), context, ser_type=cls)


class WriteException(RuntimeError):
    ...


class ReadException(RuntimeError):
    ...


def write(storable, path: PathLike, context: BaseContext = None):
    _, inner_write, _ = get_custom_storable(type(storable), (None, None, None))
    if inner_write is None:
        inner_write = getattr(storable, WRITE, None)
    else:
        return _call_optional_context(inner_write, storable, path, context=context)

    if inner_write is None:
        raise WriteException("Could not find __write__ method.")
    return _call_optional_context(inner_write, path, context=context)


def read(type: Union[str, Type], path: PathLike, context: BaseContext = None, **kwargs):
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
    def __init__(self, directory: str):
        """Initialize a new FileSystem at the specified directory."""
        self.directory = get_root_path() if directory is None else directory
        self.touched = []

    def __repr__(self):
        return f"FileSystem({self.directory}"

    def contains(self, path: str):
        """Is the specified path contained within this FileSystem."""
        return os.path.commonpath([self.directory]) == os.path.commonpath(
            [self.directory, os.path.abspath(path)]
        )

    def normalize(self, path: os.PathLike):
        """Normalize a path relative to the current directory."""
        return os.path.relpath(self.abspath(path), start=self.directory)

    def abspath(self, path: str, *, validate=False):
        """Get the absolute path

        Raises:
            ValueError: The path is not contained within this FileSystem.
        """
        # Get absolute path.
        path = os.path.join(self.directory, path)

        # Check if absolute path is contained within the controlled directory.
        if validate and not self.contains(path):
            raise ValueError((
                f'Can only adjust directory "{self.directory}". The specified'
                f'"{path}" is not contained within.'
            ))

        # Return result.
        return path

    def open(self, target: str):
        """Prepare directory to write to target path."""
        path = self.abspath(target, validate=True)
        directory = os.path.dirname(path)
        if not os.path.isdir(directory):
            os.makedirs(directory)
        return path

    def clean(self, target: str):
        """Prune empty directories starting from target."""
        directory = os.path.dirname(self.abspath(target, validate=True))
        if directory == self.directory:
            return
        if os.path.isdir(directory) and len(os.listdir(directory)) == 0:
            log.io(f'Removing empty directory "{normalize_path(directory)}".', "fs")
            os.rmdir(directory)
            self.clean(directory)

    def suggest_alternative(self, path: os.PathLike):
        """Get default suggestion for path in touched."""
        directory, basename = os.path.split(path)
        if self.normalize(path) not in self.touched:
            return directory, basename

        stem, suffix = os.path.splitext(basename)
        base, matches = substitute(r"[0-9]+\b", "", stem)
        if len(matches) == 0:
            base = f"{base}0"
        else:
            base = f"{base}{int(matches[0].group(0))+1}"
        default = f"{base}{suffix}"
        return self.suggest_alternative(os.path.join(directory, default))

    def write(
        self,
        storable,
        path: os.PathLike,
        context: BaseContext = None,
        *,
        choice: str = None,
    ):
        """Write a storable to disk, keeping in mind previous writes.

        Args:
            storable: The storable to write to disk.
            path (os.PathLike): The path to which to write.
            context (BaseContext, optional): The context for serialization. Defaults to None.
            choice (str, optional): The default choice. Defaults to None.

        Raises:
            SerializationError: If the quit choice was passed
                and the system tries to write to the same file twice.
        """
        # Create folder
        path = self.open(path)

        # Register the path in touched if not done so and execute write.
        _path = self.normalize(path)
        if _path not in self.touched:
            self.touched.append(_path)
            return write(storable, path, context)

        # Get the default directory and choice.
        directory, default = self.suggest_alternative(path)
        choice = config.on_retouch if choice is None else choice

        # If the choice is "prompt" then we request input from the user.
        if choice == "prompt":
            choice = prompt_user(
                (
                    f"Tried to write to same file twice: {path}.\n"
                    "Specify alternative filename.\n"
                    '    Enter "q" to cancel serialization and "x" to ignore'
                ),
                default=default,
            )

        # If the choice is "auto" (or the same as default) then write to the default
        if choice == default or choice == "auto":
            return self.write(
                storable, os.path.join(directory, default), context, choice="auto"
            )

        # If the choice is "quit" then we raise a SerializationError,
        # which will cancel serialization.
        if choice in ("q", "quit"):
            raise FileSystemError(
                (
                    f"Attempted to write to {path} twice during serialization."
                    "Operation exited by user."
                )
            )

        # If the choice is "ignore" then the file is overwritten.
        if choice in ("x", "ignore"):
            log.warning(
                f"Overwritten previously stored object at {path} during serialization.",
                "fs",
            )
            return write(storable, path, context)
        # We reach this option if a custom file name was provided by the user.
        return self.write(
            storable, os.path.join(directory, choice), context, choice="prompt"
        )

    def read(self, sto_type, target: str, context: BaseContext = None):
        """Read a file from the specified target with specified type."""

        return read(sto_type, self.abspath(target), context)

    def delete(self, target: str):
        """Remove file at specified target."""

        # Remove should only be called on root.
        path = self.abspath(target, validate=True)

        # Remove from touched
        with suppress(ValueError):
            self.touched.remove(self.normalize(path))

        # Remove file if it exists.
        if os.path.exists(path):
            log.io(f'Deleting file: "{normalize_path(path)}".', "fs")
            os.remove(path)
        
        # Prune directories
        self.clean(target)
