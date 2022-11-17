"""
Contains utilities for creating storable types and to write and read 
from disk.
"""



from dataclasses import asdict, is_dataclass
import os
from typing import Type, Union, Any, Callable, Optional
import io as _io
from tempfile import TemporaryDirectory
import shutil
from uuid import uuid4


from dman.core.serializables import (
    is_serializable,
    serialize,
    deserialize,
    BaseContext,
    _call_optional_context,
)
from dman.utils import sjson


STO_TYPE = "_sto__type"
WRITE = "__write__"
READ = "__read__"
LOAD = "__load__"

__storable_types = dict()
__custom_storable = dict()


def sto_type2str(obj):
    """Get the storable type string."""
    cls = obj if isinstance(obj, type) else type(obj)
    if cls in __custom_storable:
        return __custom_storable[cls][0]
    return getattr(obj, STO_TYPE, None)


def get_storable_name(obj):
    return obj if isinstance(obj, str) else getattr(obj, STO_TYPE, None)


def is_storable(obj):
    return sto_type2str(obj) in __storable_types


def is_storable_type_str(type: str):
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


def storable_types():
    """Return the storable types dictionary."""
    return __storable_types


def get_custom_storable(cls: Type[Any], default=None):
    """Get the signature of a custom storable object."""
    return __custom_storable.get(cls, default)


def storable(cls=None, /, *, name: str = None):
    """Make a class storable.
    
        Returns the same class as was passed in and the class is registered as a
        storable type. Write and Read methods are added
        automatically if cls is a dataclass or a serializable type. 
        Otherwise a ``__write__`` and ``__read__`` method should be provided for 
        storing. If these are not provided conversion will fail.

        See :ref:`sphx_glr_gallery_fundamentals_example1_storables.py` for
        detailed examples on how to create storable types.

    Args:
        cls: The class to convert.
        name (str, optional): The name of the storable. Defaults to the name of the class.

    Raises:
        ValueError: The class could not be made storable. 
            Provide a ``__write__`` and ``__read__`` method.
    """
    def wrap(cls):
        local_name = name
        if local_name is None:
            local_name = getattr(cls, "__name__")

        setattr(cls, STO_TYPE, local_name)
        register_storable(local_name, cls)

        if is_serializable(cls):
            if getattr(cls, WRITE, None) is None:
                setattr(cls, WRITE, _write__serializable)

            if getattr(cls, READ, None) is None:
                setattr(cls, READ, _read__serializable)

        elif is_dataclass(cls):
            if getattr(cls, WRITE, None) is None:
                setattr(cls, WRITE, _write__dataclass)

            if getattr(cls, READ, None) is None:
                setattr(cls, READ, _read__dataclass)

        if not hasattr(cls, READ) or not hasattr(cls, WRITE):
            raise ValueError(
                f"Class {cls} could not be made storable. Provide a manual definition of a `__write__` and `__read__` method."
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
        return deserialize(sjson.load(f), context, expected=cls)


class WriteException(RuntimeError):
    """Exception raised when a write of a storable fails."""
    ...


class ReadException(RuntimeError):
    """Exception raised when a read of a storable fails."""
    ...


def write(storable, path: os.PathLike, context: BaseContext = None):
    """Write a storable to the specified path.

        See :ref:`sphx_glr_gallery_fundamentals_example1_storables.py`
        for details on how to use this method. 

    Args:
        storable: The storable instance to write
        path (os.PathLike): Target path
        context (BaseContext, optional): Context to pass to the ``__write__`` method. 
            Defaults to None.
    """
    _, inner_write, _ = get_custom_storable(type(storable), (None, None, None))
    if inner_write is None:
        inner_write = getattr(storable, WRITE, None)
    else:
        return _call_optional_context(inner_write, storable, path, context=context)

    if inner_write is None:
        raise WriteException("Could not find __write__ method.")
    return _call_optional_context(inner_write, path, context=context)


def read(type: Union[str, Type], path: os.PathLike, context: BaseContext = None, **kwargs):
    """Read a storable from the specified path.

        See :ref:`sphx_glr_gallery_fundamentals_example1_storables.py`
        for details on how to use this method. 

    Args:
        type (Union[str, Type]): The type (string) of the storable
        path (os.PathLike): The path from which to read
        context (BaseContext, optional): The context to pass to the ``__read__`` method. 
            Defaults to None.
    """
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


class MovableIO:
    def __init__(self, content):
        self._content = content

    @property
    def content(self):
        return self._content

    @content.setter
    def content(self, value):
        # flush old content
        if self._content and hasattr(self._content, 'flush'):
            self._content.flush()  
        self._content = value

    def __getattr__(self, __name: str):
        return getattr(self.content, __name)


@storable(name='_storable__stream')
class FileTarget(MovableIO):
    def __init__(self, baseFileName: os.PathLike = None, suffix: str = '.txt', mode: str = 'a', encoding=None, errors=None):
        self.mode = mode
        self.errors = errors
        self.encoding = encoding
        if "b" not in mode:
            self.encoding = _io.text_encoding(encoding)

        if baseFileName is not None:
            self.tempdir = None
            self.baseFilename = baseFileName
            stream = open(baseFileName, mode, encoding=encoding, errors=errors)
            _, self.__ext__ = os.path.splitext(baseFileName)
        else:
            self.tempdir = TemporaryDirectory()
            self.baseFilename = os.path.join(self.tempdir.name, f"log-{uuid4()}{suffix}")
            stream = open(self.baseFilename, mode, encoding=encoding, errors=errors)
            self.__ext__ = suffix

        super().__init__(stream)
        
    def transfer(self, src: str, dst: str):
        with open(dst, "ab") as wfd:
            with open(src, "rb") as fd:
                shutil.copyfileobj(fd, wfd)

    def __write__(self, path: os.PathLike):
        if os.path.abspath(self.baseFilename) == os.path.abspath(path):
            return

        self.content = None  # remove current stream

        if os.path.exists(self.baseFilename):
            if self.tempdir is not None:
                self.transfer(self.baseFilename, path)
                os.remove(self.baseFilename)
            else:
                self.transfer(self.baseFilename, path)

        self.baseFilename = path
        self.content = open(self.baseFilename, self.mode, encoding=self.encoding)        
        
        if self.tempdir is not None:
            self.tempdir.cleanup()
            self.tempdir = None

    @classmethod
    def __read__(cls, path: os.PathLike):
        return cls(path)

    def __remove__(self, _):
        self.__init__()  # switch back to temporary file