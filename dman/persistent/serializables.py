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
    return getattr(obj, SER_TYPE, None)


def ser_str2type(ser):
    """
    Returns the class represented by a serialize type string.
    """
    return __serializable_types.get(ser, None)


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


def serialize(ser, context: 'BaseContext' = None, content_only: bool = False):
    """
    Serialize a serializable object.
        The context can be used for logging / error handling or other more 
        advanced behavior. 

    :param ser: The object to serialize
    :param context: The serialization context
    :param bool content_only: Do not include type information when true
    """
    if context is None:
        context = BaseContext()
    return context.serialize(ser, content_only=content_only)


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
    return context.deserialize(serialized, ser_type)


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
 

class BaseInvalid:
    ...


@serializable(name='__unserializable')
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
        return head+textwrap.indent(content, ' '*4)


@serializable(name = '__exc_unserializable')
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


@serializable(name='__undeserializable')
@dataclass
class Undeserializable(Unserializable):
    serialized: dict = None

    def __repr__(self):
        return f'Undeserializable: {self.type}'

    def __str__(self):
        res = super().__str__()
        if self.serialized:
            res += '\n'
            res += ' '*4 + 'Serialized: \n'
            res += textwrap.indent(sjson.dumps(self.serialized), ' '*8)
        return res


@serializable(name='__exc_undeserializable')
@dataclass
class ExcUndeserializable(ExcUnserializable):
    serialized: dict = None

    def __repr__(self):
        return f'Undeserializable: {self.type}'

    def __str__(self):
        res = super().__str__()
        if self.serialized:
            res += '\n'
            res += ' '*4 + 'Serialized: \n'
            res += textwrap.indent(sjson.dumps(self.serialized), ' '*8)
        return res


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

 
class BaseContext: 
    """
    The basic interface for serialization contexts.
    """
    def log(self, msg: str): ...

    def error(self, msg: str): ...

    def serialize(self, ser, content_only: bool = False): 
        if isinstance(ser, (list, tuple)):
            return self._serialize__list(ser)

        if isinstance(ser, dict):
            return self._serialize__dict(ser)

        if sjson.atomic_type(ser):
            return self._serialize__atomic(ser)

        content = self._serialize__object(ser)
        if isinstance(content, Unserializable):
            return serialize(content, self, content_only=False)

        if content_only:
            return content

        return {SER_TYPE: getattr(ser, SER_TYPE), SER_CONTENT: content}
    
    def _serialize__object(self, ser):
        if not is_serializable(ser):
            return Unserializable(
                type=ser, 
                info=f'Unserializable type: {repr(ser)}.'
            )

        ser_method = getattr(ser, SERIALIZE, lambda: {})
        sig = inspect.signature(ser_method)
        try:
            if len(sig.parameters) == 0:
                content = ser_method()
            elif len(sig.parameters) == 1:
                content = ser_method(self)
            else:
                return Unserializable(
                    type=ser, 
                    info='Invalid inner serialize method.'
                )
        except Exception:
            return ExcUnserializable(
                type=ser, 
                info='Error during serialization:'
            )

        return content

    def _serialize__atomic(self, ser):
        return ser

    def _serialize__list(self, ser: list):
        res = []
        for itm in ser:
            if not sjson.atomic_type(itm):
                itm = self.serialize(itm)
            res.append(itm)
        return res

    def _serialize__dict(self, ser: dict):
        res = {}
        for k, v in ser.items():
            k = self.serialize(k)
            res[k] = self.serialize(v)

        return res

    def deserialize(self, serialized, ser_type=None):
        if serialized is None:
            return None

        if ser_type is None:
            if isinstance(serialized, (list, tuple)):
                return self._deserialize__list(list, serialized)

            if sjson.atomic_type(serialized):
                return self._deserialize__atomic(type(serialized), serialized)

            if not isinstance(serialized, dict):
                return Undeserializable(type=ser_type,
                    info=f'Unexpected type for serialized: {type(serialized)}. Expected either list, tuple, atomic type or dict.'
                )

            ser_type = serialized.get(SER_TYPE, MISSING)
            if ser_type is MISSING:
                return self._deserialize__dict(dict, serialized)
            else:
                serialized = serialized.get(SER_CONTENT, {})
                ser_type = ser_str2type(ser_type)
                if ser_type is None:
                    return Undeserializable(type=ser_type, 
                        info=f'Unregistered type stored in serialized.', serialized=serialized
                    )
                return self._deserialize__object(serialized, ser_type)

        if ser_type is dict:
            return self._deserialize__dict(dict, serialized)

        if ser_type in (list, tuple):
            return self._deserialize__list(list, serialized)

        if isinstance(ser_type, str) and type(serialized) is not str:
            ser_type = __serializable_types.get(ser_type, None)
            if ser_type is None:
                return Undeserializable(
                    type=ser_type, 
                    info=f'Unregistered type provided as argument.', serialized=serialized
                )
            return self._deserialize__object(serialized, ser_type)

        if ser_type in sjson.atomic_types:
            return self._deserialize__atomic(ser_type, serialized)

        return self._deserialize__object(serialized, ser_type)
    
    def _deserialize__object(self, serialized, expected):
        try:
            ser_method = getattr(expected, DESERIALIZE, None)
            if ser_method is None:
                return Undeserializable(
                    type=expected, 
                    info=f'Type {expected} has no deserialize method.', 
                    serialized=serialized
                )

            sig = inspect.signature(ser_method)
            if len(sig.parameters) == 1:
                return ser_method(serialized)
            elif len(sig.parameters) == 2:
                return ser_method(serialized, self)
            else:
                return ExcUndeserializable(
                    type=expected, 
                    info=f'Type {expected} has invalid deserialize method.', 
                    serialized=serialized
                )
        except Exception:
            return ExcUndeserializable(
                type=expected, 
                info=f'Exception encountered while deserializing {expected}:', 
                serialized=serialized
            )

    def _deserialize__atomic(self, cls, serialized):
        if cls is not type(serialized):
            return Undeserializable(
                type=cls,
                info=f'Specified type {cls}, but got {type(serialized)}.',
                serialized=serialized
            )
        return serialized

    def _deserialize__list(self, cls, ser):
        res: list = cls()
        for itm in ser:
            if not sjson.atomic_type(itm):
                itm = self.deserialize(itm)
            res.append(itm)
        return res

    def _deserialize__dict(self, cls, ser: dict):
        res: dict = cls()
        for k, v in ser.items():
            k = self.deserialize(k)
            res[k] = self.deserialize(v)
        return res
