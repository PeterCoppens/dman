import inspect
import json

from dataclasses import asdict, is_dataclass
from os import PathLike

from dman.persistent.serializables import SER_CONTENT, SER_TYPE, is_serializable, serialize, deserialize, BaseContext

STO_TYPE = '_sto__type'
WRITE = '__write__'
READ = '__read__'
LOAD = '__load__'

__storeable_types = dict()


def storeable_type(obj):
    return getattr(obj, STO_TYPE, None)


def get_storeable(name):
    return getattr(__storeable_types, name)


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


def _write__dataclass(self, path: PathLike):
    with open(path, 'w') as f:
        json.dump(asdict(self), f, indent=4)


@classmethod
def _read__dataclass(cls, path: PathLike):
    with open(path, 'r') as f:
        return cls(**json.load(f))


def _write__serializable(self, path: PathLike, context: BaseContext = None):
    with open(path, 'w') as f:
        serialized = serialize(self, context)
        json.dump(serialized[SER_CONTENT], f, indent=4)


@classmethod
def _read__serializable(cls, path: PathLike, context: BaseContext = None):
    with open(path, 'r') as f:
        serialized = {SER_TYPE: getattr(cls, SER_TYPE), SER_CONTENT: json.load(f)}
        return deserialize(serialized, context)


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
    else:
        raise ValueError(f'object has invalid signature for method {WRITE}')


def read(type: str, path: PathLike, context: BaseContext = None):
    # if not preload:
    #     return Unloaded(type, path, context)

    storeable = __storeable_types.get(type, None)
    if storeable is None:
        raise ValueError(f'type {type} is not registered as a storeable type')

    inner_read = getattr(storeable, READ, None)
    if inner_read is None:
        return None

    sig = inspect.signature(inner_read)
    if len(sig.parameters) == 1:
        return inner_read(path)
    elif len(sig.parameters) == 2:
        if context is None:
            context = BaseContext
        return inner_read(path, context)
    else:
        raise ValueError(f'object has invalid signature for method {WRITE}')
