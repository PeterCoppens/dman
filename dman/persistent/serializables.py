import copy
import inspect

from dataclasses import dataclass, field, fields, is_dataclass
import sys
import traceback

from dman.utils import sjson


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


@dataclass(repr=False)
class Invalid:
    type: str = field(default='null')
    info: str = field(default='')

    @classmethod
    def at_error(cls, type: str, info: str):
        exc_tp, exc_vl, exc_tb = sys.exc_info()
        result = info + '\n\n'
        tb_str = traceback.format_tb(exc_tb)
        if len(tb_str) > 1:
            for tb in tb_str[1:]:
                result += tb
        else:
            result += tb_str
        result += f'{exc_tp.__name__}: {exc_vl}'
        return cls(type=type, info=result)
    
    @classmethod
    def from_dict(cls, type: str, info: str, dct: dict):
        result = info + '\n\n'
        result += sjson.dumps(dct, indent=4)
        return cls(type=type, info=result)

    def __serialize__(self):
        res = {'type': self.type}
        if len(self.info) > 0:
            res['info'] = self.info
        return res

    @classmethod
    def __deserialize__(cls, serialized: dict):
        return cls(type=serialized.get('type', None), info=serialized.get('info', ''))
    
    def __repr__(self):
        return f'Invalid: {self.type}'

    def __str__(self):
        result = f'Invalid: {self.type}\n\n'
        result += self.info
        return result

def invalid(type: str, info: str = '', error: Exception = None):
    return Invalid(type, info, error)


def isvalid(obj):
    return not isinstance(obj, Invalid)


class ValidationError(BaseException): ...

def validate(obj, msg: str = 'Could not validate object'):
    if isvalid(obj):
        return
    raise ValidationError(msg, str(obj))


def serialize(ser, context: 'BaseContext' = None, content_only: bool = False):
    if not is_serializable(ser):
        result = Invalid(type=ser, info=f'Unserializable type: {repr(ser)}')
        if context: context.error(str(result))
        return serialize(result, context, content_only=content_only)

    ser_method = getattr(ser, SERIALIZE, lambda: {})
    sig = inspect.signature(ser_method)
    try:
        if len(sig.parameters) == 0:
            content = ser_method()
        elif len(sig.parameters) == 1:
            if context is None:
                context = BaseContext
            content = ser_method(context)
        else:
            result = Invalid(type=ser, info='Invalid inner serialize method')
            if context: context.error(result.info)
            return serialize(result, context, content_only=content_only)
    except Exception:
        info = 'Error during serialization:'
        result = Invalid.at_error(ser, info=info)
        if context: context.error(result.info)
        return serialize(result, context, content_only=content_only)

    if content_only:
        return content

    return {SER_TYPE: getattr(ser, SER_TYPE), SER_CONTENT: content}


def deserialize(serialized: dict, context: 'BaseContext' = None, ser_type=None):
    if ser_type is None:
        ser_type = serialized.get(SER_TYPE, None)
        if ser_type not in __serializable_types:
            info = f'Unserializable type: {ser_type}'
            result = Invalid.from_dict(type=ser_type, info=info, dct=serialized)
            if context: context.error(result.info)
            return result
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
        info = f'Invalid inner serialize method'
        result = Invalid.from_dict(type=ser_type, info=info, dct=serialized)
        if context: context.error(result.info)
        return result


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


Invalid = serializable(Invalid, name='__unserializable')


class BaseContext:
    def track(self, *args, **kwargs): ...
    def untrack(self, *args, **kwargs): ...
    def error(self, msg: str): ...
    def log(self, msg: str): ...