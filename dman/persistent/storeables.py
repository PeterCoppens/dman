import inspect

from dataclasses import asdict, dataclass, is_dataclass
from os import PathLike
import os

from dman.persistent.serializables import is_serializable, serializable, serialize, deserialize, BaseContext
from dman.utils import sjson

STO_TYPE = '_sto__type'
WRITE = '__write__'
READ = '__read__'
LOAD = '__load__'

__storeable_types = dict()


def storeable_type(obj):
    return getattr(obj, STO_TYPE, None)


def is_storeable(obj):
    return storeable_type(obj) in __storeable_types


def is_storeable_type(type: str):
    return type in __storeable_types


def storeable(cls=None, /, *, name: str = None, ignore_serializable: bool = None, ignore_dataclass: bool = False):
    def wrap(cls):
        local_name = name
        if local_name is None:
            local_name = getattr(cls, '__name__')

        setattr(cls, STO_TYPE, local_name)
        __storeable_types[local_name] = cls

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

        return cls

    # See if we're being called as @storeable or @storeable().
    if cls is None:
        # We're called with parens.
        return wrap

    # We're called as @storeable without parens.
    return wrap(cls)


@storeable(name='__unreadable')
@dataclass
class Unreadable:
    path: str
    type: str

    def __write__(self, path: PathLike):
        pass

    @classmethod
    def __read__(cls, path: PathLike):
        return cls(path)


def unreadable(path: PathLike, type: str):
    return Unreadable(path, type)


def is_unreadable(obj):
    return isinstance(obj, Unreadable)


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


def write(storeable, path: PathLike, context: BaseContext = None):
    inner_write = getattr(storeable, WRITE, None)
    if inner_write is None:
        return
    sig = inspect.signature(inner_write)
    if len(sig.parameters) == 1:
        inner_write(path)
    elif len(sig.parameters) == 2:
        if context is None:
            context = BaseContext
        inner_write(path, context)    


def read(type: str, path: PathLike, context: BaseContext = None):
    if isinstance(type, str):
        type = __storeable_types.get(type, None)
        if type is None:
            return unreadable(path, type)

    inner_read = getattr(type, READ, None)
    if inner_read is None:
        return unreadable(path, type)

    try:
        sig = inspect.signature(inner_read)
        if len(sig.parameters) == 1:
            return inner_read(path)
        elif len(sig.parameters) == 2:
            if context is None:
                context = BaseContext
            return inner_read(path, context)
        else:
            return unreadable(path, type)
    except FileNotFoundError:
        return unreadable(path, type)
