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
from dman.core.path import TargetException, UserQuitException, get_root_path, normalize_path, mount, target, Mount, Target, AUTO, config
from dman.utils.smartdataclasses import configclass, optionfield


STO_TYPE = "_sto__type"
WRITE = "__write__"
READ = "__read__"
LOAD = "__load__"

__storable_types = dict()
__custom_storable = dict()


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
        return deserialize(sjson.load(f), context, expected=cls)


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