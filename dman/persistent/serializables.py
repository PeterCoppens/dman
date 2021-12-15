import copy
import inspect

from dataclasses import dataclass, fields, is_dataclass


SER_TYPE = '_ser__type'
SER_CONTENT = '_ser__content'
SERIALIZE = '__serialize__'
DESERIALIZE = '__deserialize__'
NO_SERIALIZE = '__no_serialize__'


__serializable_types = dict()


def ser_type2str(ser):
    return getattr(ser, SER_TYPE)


def ser_str2type(ser):
    return __serializable_types.get(ser)


def is_serializable(ser):
    return getattr(ser, SER_TYPE, None) in __serializable_types


def is_deserializable(serialized: dict):
    if not isinstance(serialized, dict):
        return False
    return serialized.get(SER_TYPE, None) in __serializable_types


def register_serializable(name: str, type):
    __serializable_types[name] = type


@dataclass
class Unserializable:
    type: str


def unserializable(type: str):
    return Unserializable(type)


def is_unserializable(obj):
    return isinstance(obj, Unserializable)


def serialize(ser, context: 'BaseContext' = None, content_only: bool = False):
    if not is_serializable(ser):
        return serialize(Unserializable(ser), context, content_only=content_only)

    ser_method = getattr(ser, SERIALIZE, lambda: {})
    sig = inspect.signature(ser_method)
    if len(sig.parameters) == 0:
        content = ser_method()
    elif len(sig.parameters) == 1:
        if context is None:
            context = BaseContext
        content = ser_method(context)
    else:
        return serialize(Unserializable(ser), context, content_only=content_only)

    if content_only:
        return content

    return {SER_TYPE: getattr(ser, SER_TYPE), SER_CONTENT: content}


def deserialize(serialized: dict, context: 'BaseContext' = None, ser_type=None):
    if ser_type is None:
        ser_type = serialized.get(SER_TYPE, None)
        if ser_type not in __serializable_types:
            return Unserializable(ser_type)
        serialized = serialized.get(SER_CONTENT, {})

    if isinstance(ser_type, str):
        ser_type = __serializable_types.get(ser_type)

    ser_method = getattr(ser_type, DESERIALIZE, lambda _: None)
    sig = inspect.signature(ser_method)
    if len(sig.parameters) == 1:
        return ser_method(serialized)
    elif len(sig.parameters) == 2:
        if context is None:
            context = BaseContext
        return ser_method(serialized, context)
    else:
        return Unserializable(ser_type)


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
            (_serialize__dataclass__inner(k, context),
             _serialize__dataclass__inner(v, context))
            for k, v in obj.items() if v is not None
        )
    else:
        return copy.deepcopy(obj)


@classmethod
def _deserialize__dataclass(cls, serialized: dict, context: 'BaseContext'):
    processed = copy.deepcopy(serialized)
    for k, v in processed.items():
        processed[k] = getattr(
            cls, '_deserialize__dataclass__inner')(v, context)

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


def serializable(cls=None, /, *, name: str = None, ignore_dataclass: bool = False):
    def wrap(cls):
        local_name = name
        if local_name is None:
            local_name = getattr(cls, '__name__')
        setattr(cls, SER_TYPE, local_name)
        register_serializable(local_name, cls)

        if not ignore_dataclass and is_dataclass(cls):
            if getattr(cls, SERIALIZE, None) is None:
                setattr(cls, SERIALIZE, _serialize__dataclass)
            if getattr(cls, DESERIALIZE, None) is None:
                setattr(cls, DESERIALIZE, _deserialize__dataclass)
                setattr(cls, '_deserialize__dataclass__inner',
                        _deserialize__dataclass__inner)

        return cls

    # See if we're being called as @serializable or @serializable().
    if cls is None:
        # We're called with parens.
        return wrap

    # We're called as @serializable without parens.
    return wrap(cls)


Unserializable = serializable(Unserializable, name='__unserializable')


class BaseContext:
    def track(self, *args, **kwargs):
        return
    
    def untrack(self, *args, **kwargs):
        return
