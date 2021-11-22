import copy
from dataclasses import dataclass, fields, is_dataclass
import json
import inspect
from typing import Dict, List, Tuple
from dman.persistent.smartdataclasses import overrideable


SER_TYPE = '_ser__type'
SER_CONTENT ='_ser__content'
SERIALIZE = '__serialize__'
DESERIALIZE = '__deserialize__'
NO_SERIALIZE = '__no_serialize__'


@overrideable
class BaseContextCommand:
    def evaluate(self, ctx: 'BaseContext'):
        return ctx
    
    def __rshift__(self, _: 'BaseContextCommand'):
        return self
    
    def __lshift__(self, other: 'BaseContextCommand'):
        return other.__rshift__(self)


def is_serializable(ser):
    return getattr(ser, SER_TYPE, None) in serializable_types


def is_deserializable(serialized: dict):
    if not isinstance(serialized, dict):
        return False
    return serialized.get(SER_TYPE, None) in serializable_types


def serialize(ser, context: 'BaseContext' = None):
    if not is_serializable(ser):
        raise ValueError('object is not a serializeble type')

    inner_serialize = getattr(ser, SERIALIZE, lambda: {})
    sig = inspect.signature(inner_serialize)
    if len(sig.parameters) == 0:
        return {SER_TYPE: getattr(ser, SER_TYPE), SER_CONTENT: inner_serialize()}
    elif len(sig.parameters) == 1:
        if context is None: context = BaseContext
        return {SER_TYPE: getattr(ser, SER_TYPE), SER_CONTENT: inner_serialize(context)}
    else:
        raise ValueError(f'object has invalid signature for method {SERIALIZE}')


def deserialize(serialized: dict, context: 'BaseContext' = None):
    if not is_deserializable(serialized):
        raise ValueError(f'provided dictionary is not deserializable.')
        
    sertype = serialized.get(SER_TYPE, None)
    if sertype not in serializable_types:
        raise ValueError(f'unregistered type {sertype}.')
    
    ser = serializable_types.get(sertype)
    inner_deserialize = getattr(ser, DESERIALIZE, lambda _: None)
    sig = inspect.signature(inner_deserialize)
    if len(sig.parameters) == 1:
        return inner_deserialize(serialized.get(SER_CONTENT, {}))
    elif len(sig.parameters) == 2:
        if context is None: context = BaseContext
        return inner_deserialize(serialized.get(SER_CONTENT, {}), context)
    else:
        raise ValueError(f'object has invalid signature for method {DESERIALIZE}')


serializable_types = dict()

def register_serializable(name: str, type):
    serializable_types[name] = type

def serializable(cls=None, /, *, name: str = None, ignore_dataclass: bool = False):
    def wrap(cls):
        local_name = name
        if local_name is None:
            local_name = str(cls)
        setattr(cls, SER_TYPE, local_name)
        register_serializable(local_name, cls)

        if not ignore_dataclass and is_dataclass(cls):
            if getattr(cls, SERIALIZE, None) is None:
                setattr(cls, SERIALIZE, _serialize__dataclass)
            if getattr(cls, DESERIALIZE, None) is None:
                setattr(cls, DESERIALIZE, _deserialize__dataclass)
                setattr(cls, '_deserialize__dataclass__inner', _deserialize__dataclass__inner)

        return cls

    # See if we're being called as @serializable or @serializable().
    if cls is None:
        # We're called with parens.
        return wrap

    # We're called as @serializable without parens.
    return wrap(cls)


def _serialize__dataclass(self, context: 'BaseContext' = None):
    serialized = dict()
    for f in fields(self):
        if f.name not in getattr(self, NO_SERIALIZE, []):
            value = getattr(self, f.name)
            serialized[f.name] = _serialize__dataclass__inner(value, context)
    
    return serialized


def _serialize__dataclass__inner(obj, context: 'BaseContext' = None):
        if is_serializable(obj):
            res = serialize(obj, context)
            return res
        elif isinstance(obj, (tuple, list)):
            return type(obj)([_serialize__dataclass__inner(v, context) for v in obj])
        elif isinstance(obj, dict):
            return type(obj)(
                (_serialize__dataclass__inner(k, context), _serialize__dataclass__inner(v, context)) 
                for k, v in obj.items() if v is not None
            )
        else:
            return copy.deepcopy(obj)

@classmethod
def _deserialize__dataclass(cls, serialized: dict, context: 'BaseContext'):
    processed = copy.deepcopy(serialized)
    for k, v in processed.items():
        processed[k] = getattr(cls, '_deserialize__dataclass__inner')(v, context)

    return cls(**processed)


@classmethod
def _deserialize__dataclass__inner(cls, obj, context: 'BaseContext'):
    if isinstance(obj, (tuple, list)):
        return type(obj)([
            getattr(cls, '_deserialize__dataclass__inner')(v, context) for v in obj
        ])
    elif isinstance(obj, dict) and is_deserializable(obj):
        return deserialize(obj, context)
    elif isinstance(obj, dict):
        return type(obj)(
            (
                getattr(cls, '_deserialize__dataclass__inner')(k, context), 
                getattr(cls, '_deserialize__dataclass__inner')(v, context)
            ) for k, v in obj.items() if v is not None
        )
    else:
        return obj


@serializable(name='__ser_b_ctx')
class BaseContext:
    def __serialize__(self):
        return {}
    
    @classmethod
    def __deserialize__(self, serialized: dict):
        return BaseContext()
