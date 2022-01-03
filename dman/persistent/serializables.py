import inspect

from dataclasses import MISSING, dataclass, field, fields, is_dataclass
import sys
import traceback
from typing import List

from dman.utils import sjson
import textwrap


SER_TYPE = '_ser__type'
SER_CONTENT = '_ser__content'
SERIALIZE = '__serialize__'
DESERIALIZE = '__deserialize__'
NO_SERIALIZE = '__no_serialize__'


__serializable_types = dict()


def ser_type2str(obj):
    """
    Returns the serialize type string of an object or class.
    """
    return getattr(obj, SER_TYPE)


def ser_str2type(ser):
    """
    Returns the class represented by a serialize type string.
    """
    return __serializable_types.get(ser)


def is_serializable(ser):
    """
    Check if an object supports serialization
    """
    if getattr(ser, SER_TYPE, None) in __serializable_types:
        return True
    if isinstance(ser, (list, dict, tuple)):
        return True
    return sjson.atomic_type(ser)


def is_deserializable(serialized: dict):
    """
    Check if a dictionary has been produced through serialization.
    """
    if sjson.atomic_type(serialized) or isinstance(serialized, (list, tuple)):
        return True
    if not isinstance(serialized, dict):
        return False
    ser_type = serialized.get(SER_TYPE, None)
    if ser_type:
        return ser_type in __serializable_types
    return False


def register_serializable(name: str, cls):
    """
    Register a class as a serializable type with a given name
    """
    __serializable_types[name] = cls


class BaseInvalid: ...


@dataclass(repr=False)
class Unserializable(BaseInvalid):
    type: str
    info: str = field(default='')

    def __post_init__(self):
        if not isinstance(self.type, str):
            self.type = str(self.type)

    def __serialize__(self):
        res = {'type': self.type}
        if len(self.info) > 0:
            res['info'] = self.info
        return res

    def __repr__(self):
        return f'Unserializable: {self.type}'

    def __str__(self):
        head = self.__repr__() + '\n'
        content = self.info
        return head+content


@dataclass(repr=False)
class ExcUnserializable(Unserializable):
    traceback: List[str] = field(default_factory=list)
    exc: str = field(default=None)

    def __post_init__(self):
        super().__post_init__()

        if self.exc is not None:
            return
        exc_tp, exc_vl, exc_tb = sys.exc_info()
        tb_str = traceback.format_tb(exc_tb)
        if len(tb_str) > 1:
            tb_str = tb_str[1:]
        
        tb_res = []
        for i in range(len(tb_str)):
            tb_res.extend(tb_str[i].split('\n')[:-1])

        exc = f'{exc_tp.__name__}: {exc_vl}'
        self.traceback = tb_res
        self.exc = exc

    def __serialize__(self):
        res = super().__serialize__()
        if len(self.traceback) > 0:
            res['traceback'] = self.traceback
        if self.exc is not None:
            res['exc'] = self.exc
        return res

    def __str__(self):
        head = super().__str__()
        content = ''
        if len(self.traceback) > 0:
            content += '\n'
            for st in self.traceback:
                content += st + '\n'
        if self.exc is not None:
            content += self.exc
        content = textwrap.indent(content, ' '*4)
        return head+content


def isvalid(obj):
    """
    Check if an object is valid
    """
    return not isinstance(obj, BaseInvalid)


class ValidationError(BaseException):
    """
    Validation Error raised when an object could not be validated.
    """
    pass


def validate(obj, msg: str = 'Could not validate object'):
    """
    Check if the object is valid, raise a ValidationError otherwise. 

    :param obj: The object to validate
    :param str msg: An optional message set in the Validation Error
    :raises ValidationError: if the obj is not valid.
    """
    if isvalid(obj):
        return
    raise ValidationError(msg, str(obj))


def serialize(ser, context: 'BaseContext' = None, content_only: bool = False):
    """
    Serialize a serializable object.

    The context can be used for logging / error handling or other more 
    advanced behavior. 

    :param ser: The object to serialize
    :param context: The serialization context
    :param bool content_only: Do not include type information when true
    """
    if isinstance(ser, (list, tuple)):
        return _serialize__list(ser, context)
        
    if isinstance(ser, dict):
        return _serialize__dict(ser, context)

    if sjson.atomic_type(ser):
        return _serialize__atomic(ser, context)

    content = _serialize__object(ser, context) 
    if isinstance(content, Unserializable):
        return serialize(content, context, content_only=False)

    if content_only:
        return content

    return {SER_TYPE: getattr(ser, SER_TYPE), SER_CONTENT: content}


@dataclass
class Undeserializable(Unserializable):
    serialized: dict = None

    def __repr__(self):
        return f'Undeserializable: {self.type}'
    
    def __str__(self):
        res = super().__str__()
        if self.serialized:
            res += '\n'
            res += 'Serialized: \n'
            res += textwrap.indent(sjson.dumps(self.serialized), ' '*4)
        return res


@dataclass
class ExcUndeserializable(ExcUnserializable):
    serialized: dict = None

    def __repr__(self):
        return f'Undeserializable: {self.type}'

    def __str__(self):
        res = super().__str__()
        if self.serialized:
            res += '\n'
            res += 'Serialized: \n'
            res += textwrap.indent(sjson.dumps(self.serialized), ' '*4)
        return res


def deserialize(serialized, context: 'BaseContext' = None, ser_type=None):
    """
    Deserialize a dictionary produced through serialization.

    The context can be used for logging / error handling or other more 
    advanced behavior. 

    :param ser: The dictionary to deserialize
    :param context: The serialization context
    :param ser_type: Class or string representing the expected type. If set to 
                        None the type is received from the dictionary. 
    """
    if context is None:
        context = BaseContext()

    if ser_type is None:
        if isinstance(serialized, (list, tuple)):
            return _deserialize__list(list, serialized, context)

        if sjson.atomic_type(serialized):
            return _deserialize__atomic(serialized, type(serialized), context)

        if not isinstance(serialized, dict):
            exc = Undeserializable(type=ser_type, 
                info=f'Unexpected type for serialized: {type(serialized)}. \
                    Expected either list, tuple, atomic type or dict.'
            )
            context.error(exc)
            return exc
            
        ser_type = serialized.get(SER_TYPE, MISSING)
        if ser_type is MISSING:
            return _deserialize__dict(dict, serialized, context)
        else:
            serialized = serialized.get(SER_CONTENT, {})
            ser_type = __serializable_types.get(ser_type, None)
            if ser_type is None:
                exc = Undeserializable(type=ser_type, info=f'Unregistered type stored in serialized.', serialized=serialized)
                context.error(exc)
                return exc
            return _deserialize__object(serialized, ser_type, context)

    if ser_type is dict:
        return _deserialize__dict(dict, serialized, context)

    if ser_type in (list, tuple):
        return _deserialize__list(list, serialized, context)
    
    if isinstance(ser_type, str) and type(serialized) is not str:
        ser_type = __serializable_types.get(ser_type, None)
        if ser_type is None:
            exc = Undeserializable(type=ser_type, info=f'Unregistered type provided as argument.', serialized=serialized)
            context.error(exc)
            return exc
        return _deserialize__object(serialized, ser_type, context)

    if ser_type in sjson.atomic_types:
        return _deserialize__atomic(serialized, ser_type, context)
    
    return _deserialize__object(serialized, ser_type, context)


def _serialize__object(ser, context: 'BaseContext'):
    if not is_serializable(ser):
        result = Unserializable(
            type=ser, info=f'Unserializable type: {repr(ser)}.')
        if context:
            context.error(str(result))
        return result

    ser_method = getattr(ser, SERIALIZE, lambda: {})
    sig = inspect.signature(ser_method)
    try:
        if len(sig.parameters) == 0:
            content = ser_method()
        elif len(sig.parameters) == 1:
            if context is None:
                context = BaseContext()
            content = ser_method(context)
        else:
            result = Unserializable(
                type=ser, info='Invalid inner serialize method.')
            if context:
                context.error(result.info)
            return result
    except Exception:
        result = ExcUnserializable(
            type=ser, info='Error during serialization:')
        if context:
            context.error(msg=result.info)
        return result
    
    return content



def _deserialize__object(serialized, expected, context: 'BaseContext'):
    try:
        ser_method = getattr(expected, DESERIALIZE, None)
        if ser_method is None:
            exc = Undeserializable(
                type=expected, info=f'Type {expected} has no deserialize method.', serialized=serialized)
            context.error(exc)
            return exc

        sig = inspect.signature(ser_method)
        if len(sig.parameters) == 1:
            return ser_method(serialized)
        elif len(sig.parameters) == 2:
            return ser_method(serialized, context)
        else:
            exc = ExcUndeserializable(
                type=expected, info=f'Type {expected} has invalid deserialize method.', serialized=serialized)
            context.error(exc)
            return exc
    except Exception:
        exc = ExcUndeserializable(
            type=expected, info=f'Exception encountered while deserializing {expected}:', serialized=serialized)
        context.error(exc)
        return exc


def _serialize__atomic(ser, context: 'BaseContext'):
    return ser


def _deserialize__atomic(serialized, expected, context: 'BaseContext'):
    if expected is not type(serialized):
        exc = Undeserializable(type=expected, info=f'Specified type {expected}, but got {type(serialized)}.', serialized=serialized)
        context.error(exc)
        return exc
    return serialized


def _serialize__list(self: list, context: 'BaseContext' = None):
    res = []
    for itm in self:
        if not sjson.atomic_type(itm):
            itm = serialize(itm, context)
        res.append(itm)
    return res


def _deserialize__list(cls, ser, context: 'BaseContext' = None):
    res: list = cls()
    for itm in ser:
        if not sjson.atomic_type(itm):
            itm = deserialize(itm, context)
        res.append(itm)
    return res


def _serialize__dict(self: dict, context: 'BaseContext' = None):
    res = {}
    for k, v in self.items():
        k = serialize(k, context)
        res[k] = serialize(v, context)

    return res


def _deserialize__dict(cls, ser: dict, context: 'BaseContext' = None):
    res: dict = cls()
    for k, v in ser.items():
        k = deserialize(k, context)
        res[k] = deserialize(v, context)
    
    return res


def _serialize__dataclass(self, context: 'BaseContext' = None):
    serialized = dict()
    for f in fields(self):
        if f.name not in getattr(self, NO_SERIALIZE, []):
            value = getattr(self, f.name)
            serialized[f.name] = serialize(value, context)

    return serialized


@classmethod
def _deserialize__dataclass(cls, serialized: dict, context: 'BaseContext'):
    res = dict()
    for k, v in serialized.items():
        res[k] = deserialize(v, context)

    return cls(**res)


def serializable(cls=None, /, *, name: str = None):
    """
    Returns the same class as was passed in and the class is registered as a 
    serializable type. 

    Serialization and Deserialization methods are added automatically if cls
    is a dataclass. Otherwise a ``__serialize__`` or ``__deserialize__``
    method should be provided for serialization. If these are not provided 
    serialization will fail.

    :param cls: The class to process.
    :param str name: The name of the serializable type.
    """
    def wrap(cls):
        local_name = name
        if local_name is None:
            local_name = getattr(cls, '__name__')
        setattr(cls, SER_TYPE, local_name)
        register_serializable(local_name, cls)

        if is_dataclass(cls):
            if getattr(cls, SERIALIZE, None) is None:
                setattr(cls, SERIALIZE, _serialize__dataclass)
            if getattr(cls, DESERIALIZE, None) is None:
                setattr(cls, DESERIALIZE, _deserialize__dataclass)

        return cls

    # See if we're being called as @serializable or @serializable().
    if cls is None:
        # We're called with parens.
        return wrap

    # We're called as @serializable without parens.
    return wrap(cls)


Unserializable = serializable(Unserializable, name='__unserializable')
ExcUnserializable = serializable(ExcUnserializable, name='__exc_unserializable')
Undeserializable = serializable(Undeserializable, name='__undeserializable')
ExcUndeserializable = serializable(ExcUndeserializable, name='__exc_undeserializable')
 

class BaseContext: 
    """
    The basic interface for serialization contexts.
    """

    def track(self, *args, **kwargs): 
        """
        Activate this context.
        """
        pass

    def untrack(self, *args, **kwargs): 
        """
        De-activate this context.
        """
        pass
        
    def error(self, msg: str): 
        """
        Process an error.

        :param str msg: The error message.
        """
        # print(msg)
        pass

    def log(self, msg: str):
        """
        Log a message
        
        :param str msg: The log message.
        """
        pass