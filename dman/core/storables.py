from contextlib import suppress

from dataclasses import asdict, is_dataclass
from os import PathLike
from typing import Type, Union

from dman.core.serializables import is_serializable, serialize, deserialize, BaseContext, _call_optional_context
from dman.utils import sjson

STO_TYPE = '_sto__type'
WRITE = '__write__'
READ = '__read__'
LOAD = '__load__'

__storable_types = dict()


def storable_type(obj):
    return getattr(obj, STO_TYPE, None)


def is_storable(obj):
    return storable_type(obj) in __storable_types


def is_storable_type(type: str):
    return type in __storable_types


def storable(cls=None, /, *, name: str = None, ignore_serializable: bool = None, ignore_dataclass: bool = False):
    def wrap(cls):
        local_name = name
        if local_name is None:
            local_name = getattr(cls, '__name__')

        setattr(cls, STO_TYPE, local_name)
        __storable_types[local_name] = cls

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
            raise ValueError(f'Class {cls} could not be made serializable. Provide a manual definition of a `__write__` and `__read__` method.')

        return cls

    # See if we're being called as @storable or @storable().
    if cls is None:
        # We're called with parens.
        return wrap

    # We're called as @storable without parens.
    return wrap(cls)


def _write__dataclass(self, path: PathLike):
    with open(path, 'w') as f:
        sjson.dump(asdict(self), f, indent=4)


@classmethod
def _read__dataclass(cls, path: PathLike):
    with open(path, 'r') as f:
        return cls(**sjson.load(f))


def _write__serializable(self, path: PathLike, context: BaseContext = None):
    with open(path, 'w') as f:
        sjson.dump(serialize(self, context, content_only=True), f, indent=4)


@classmethod
def _read__serializable(cls, path: PathLike, context: BaseContext = None):
    with open(path, 'r') as f:
        return deserialize(sjson.load(f), context, ser_type=cls)


class WriteException(RuntimeError): ...


class ReadException(RuntimeError): ...


def write(storable, path: PathLike, context: BaseContext = None):
    inner_write = getattr(storable, WRITE, None)
    if inner_write is None:
        raise WriteException('__write__ method not found.')
    return _call_optional_context(inner_write, path, context=context)


def read(type: Union[str, Type], path: PathLike, context: BaseContext = None):
    if isinstance(type, str):
        type = __storable_types.get(type, None)
        if type is None:
            raise ReadException(f'Unregistered type: {type}.')

    inner_read = getattr(type, READ, None)
    if inner_read is None:
        raise ReadException(f'__read__ method not found.')
    return _call_optional_context(inner_read, path, context=context)
