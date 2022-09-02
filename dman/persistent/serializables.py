import inspect

from dataclasses import MISSING, dataclass, field, fields, is_dataclass, asdict
import re
import sys
import traceback
from typing import Any, List, Type

from dman.utils import sjson
from dman import log
import textwrap

from enum import Enum

from contextlib import nullcontext


SER_TYPE = '_ser__type'
SER_CONTENT = '_ser__content'
SERIALIZE = '__serialize__'
DESERIALIZE = '__deserialize__'
NO_SERIALIZE = '__no_serialize__'
CONVERT = '__convert__'
DECONVERT = '__de_convert__'



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


def _serialize__enum(self):
    return str(self)


@classmethod
def _deserialize__enum(cls, serialized: str):
    *_, name = serialized.split('.')
    return cls[name]

    
@classmethod
def _default__convert(cls, base):
    return cls(**asdict(base))


def _serialize__template(template: Any, cls: any):
    convert = getattr(template, CONVERT, None)
    if convert is None: 
        if not is_dataclass(cls): 
            raise ValueError(f'Serializable should either be a dataclass or should have a "{CONVERT}" method specified.')
        setattr(template, CONVERT, _default__convert) 
        convert = getattr(template, CONVERT, None)

    def __serialize__(self, context: BaseContext = None):
        return serialize(convert(self), context, content_only=True)

    return __serialize__


def _deserialize__template(template: Any):
    @classmethod
    def __deserialize__(cls, ser, context: BaseContext = None):
        convert = getattr(cls, CONVERT, None)
        if convert is None:
            convert = getattr(template, DECONVERT, None)
        if convert is None:
            convert = lambda x: x
        return convert(deserialize(ser, context, ser_type=template))
    return __deserialize__


def serializable(cls=None, /, *, name: str = None, template: Any = None):
    """
    Returns the same class as was passed in and the class is registered as a 
    serializable type. 

    Serialization and Deserialization methods are added automatically if cls
    is a dataclass. Otherwise a ``__serialize__`` or ``__deserialize__``
    method should be provided for serialization. If these are not provided 
    serialization will fail.

    :param cls: The class to process.
    :param str name: The name of the serializable type.
    :param template: Template class to use during serialization.
    """
    def wrap(cls):
        local_name = name
        if local_name is None:
            local_name = getattr(cls, '__name__')
        setattr(cls, SER_TYPE, local_name)
        register_serializable(local_name, cls)

        if template is not None:
            if not hasattr(cls, CONVERT):
                if not is_dataclass(template):
                    raise ValueError(f'Template should be either a dataclass or should have a "{CONVERT}" method defined.')
                if not hasattr(template, DECONVERT):
                    setattr(cls, CONVERT, _default__convert)
            if getattr(cls, SERIALIZE, None) is None:
                setattr(cls, SERIALIZE, _serialize__template(template, cls))
            if getattr(cls, DESERIALIZE, None) is None:
                setattr(cls, DESERIALIZE, _deserialize__template(template))

        elif is_dataclass(cls):
            if getattr(cls, SERIALIZE, None) is None:
                setattr(cls, SERIALIZE, _serialize__dataclass)
            if getattr(cls, DESERIALIZE, None) is None:
                setattr(cls, DESERIALIZE, _deserialize__dataclass)

        elif issubclass(cls, Enum):
            if getattr(cls, SERIALIZE, None) is None:
                setattr(cls, SERIALIZE, _serialize__enum)
            if getattr(cls, DESERIALIZE, None) is None:
                setattr(cls, DESERIALIZE, _deserialize__enum)

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
        self.type = self.type.replace('\n', '')
        self.type = re.sub(' +', ' ', self.type)

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
    ser_type: str = None

    def __repr__(self):
        return f'Undeserializable: {self.type}'
    
    def __post_init__(self):
        self.ser_type = ser_type2str(self.ser_type)

    def __str__(self):
        res = super().__str__()
        if self.serialized:
            res += '\n'
            res += ' '*4 + 'Serialized: \n'
            res += textwrap.indent(sjson.dumps(self.serialized), ' '*8)
        return res

    def __serialize__(self):
        res = super().__serialize__()
        if self.serialized is not None:
            res['serialized'] = self.serialized
        if self.ser_type is not None:
            res['ser_type'] = self.ser_type
        return res
    
    @classmethod
    def __deserialize__(cls, serialized: dict, context):
        res = cls(**deserialize(serialized, context))
        if res.serialized is not None:
            return deserialize(res.serialized, context, res.ser_type)
        return res



@serializable(name='__exc_undeserializable')
@dataclass
class ExcUndeserializable(ExcUnserializable):
    serialized: dict = None
    ser_type: str = None

    def __repr__(self):
        return f'Undeserializable: {self.type}'
    
    def __post_init__(self):
        super().__post_init__()
        if not isinstance(self.ser_type, str):
            self.ser_type = ser_type2str(self.ser_type)

    def __str__(self):
        res = super().__str__()
        if self.serialized:
            res += '\n'
            res += ' '*4 + 'Serialized: \n'
            res += textwrap.indent(sjson.dumps(self.serialized), ' '*8)
        return res

    def __serialize__(self):
        res = super().__serialize__()
        if self.serialized is not None:
            res['serialized'] = self.serialized
        if self.ser_type is not None:
            res['ser_type'] = self.ser_type
        return res
    
    @classmethod
    def __deserialize__(cls, serialized: dict, context):
        res = cls(**serialized)
        if res.serialized is not None:
            return deserialize(res.serialized, context, res.ser_type)
        return res


def isvalid(obj):
    """
    Check if an object is valid
    """
    if isinstance(obj, dict):
        return not issubclass(ser_str2type(obj.get(SER_TYPE, None)), BaseInvalid)
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
    VALIDATE = False
    def __init__(self, validate: bool = None):
        self.validate = self.VALIDATE if validate is None else validate
        self._invalid = False
        self._root = True
    
    def _process_invalid(self, msg: str, obj: BaseInvalid):
        log.warning(msg + '\n' + str(obj))
        self._invalid = True
    
    def _check_valid(self, ser):
        if self.validate and self._invalid:
            raise RuntimeError(f'Failed to serialize {ser}.')

    def serialize(self, ser, content_only: bool = False): 
        acting_root = self._root
        if acting_root:
            log.emphasize(f'starting serialization of "{type(ser).__name__}"', 'context')
            self._root = False

        if isinstance(ser, BaseInvalid):
            self._process_invalid('Invalid object encountered during serialization.', ser)

        if isinstance(ser, (list, tuple)):
            with log.layer(f'list({len(ser)})', 'serializing', owner='list'):
                return self._serialize__list(ser)

        if isinstance(ser, dict):
            with log.layer(f'dict({len(ser)})', 'serializing', owner='dict'):
                return self._serialize__dict(ser)

        if sjson.atomic_type(ser):
            return self._serialize__atomic(ser)

        with log.layer(f'{type(ser).__name__}', 'serializing', f'{type(ser).__name__}'):
            content = self._serialize__object(ser)
            if isinstance(content, Unserializable):
                return serialize(content, self, content_only=False)

        if content_only:
            return content

        self._check_valid(ser)
        if acting_root:
            self._root = True
        return {SER_TYPE: getattr(ser, SER_TYPE), SER_CONTENT: content}
    
    def _serialize__object(self, ser):
        if not is_serializable(ser):
            return Unserializable(
                type=type(ser), 
                info=f'Unserializable type: {type(ser).__name__}.'
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
                    type=type(ser), 
                    info='Invalid inner serialize method.'
                )
        except Exception:
            return ExcUnserializable(
                type=type(ser), 
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

    def _get_type_name(_, ser_type):
        name = getattr(ser_type, 'name', None)
        if name is None:
            name = getattr(ser_type, '__name__', str(ser_type))
        return name

    def deserialize(self, serialized, ser_type=None):
        acting_root = self._root
        if acting_root:
            log.emphasize(f'starting deserialization of "{type(serialized).__name__}".', 'context')
            self._root = False
            
        if serialized is None:
            return None

        if ser_type is None:
            if isinstance(serialized, (list, tuple)):
                with log.layer(f'list({len(serialized)})', 'deserializing', owner='list'):
                    return self._deserialize__list(list, serialized)

            if sjson.atomic_type(serialized):
                return self._deserialize__atomic(type(serialized), serialized)

            if not isinstance(serialized, dict):
                res =  Undeserializable(type=ser_type,
                    info=f'Unexpected type for serialized: {type(serialized)}. Expected either list, tuple, atomic type or dict.',
                    serialized=serialized
                )
                self._process_invalid('An error occurred during deserialization:', res)
                return res

            ser_type = serialized.get(SER_TYPE, MISSING)
            if ser_type is MISSING:
                with log.layer(f'dict({len(serialized)})', 'deserializing', owner='dict'):
                    return self._deserialize__dict(dict, serialized)
            else:
                serialized = serialized.get(SER_CONTENT, {})
                ser_type_get = ser_str2type(ser_type)
                if ser_type_get is None:
                    res = Undeserializable(type=ser_type_get, 
                        info=f'Unregistered type stored in serialized.', 
                        serialized=serialized,
                        ser_type=ser_type
                    )
                    self._process_invalid('An error occurred during deserialization:', res)
                    return res

                _ser_name = self._get_type_name(ser_type_get)
                with log.layer(f'{_ser_name}', 'deserializing', f'{_ser_name}'):
                    return self._deserialize__object(serialized, ser_type_get)

        if ser_type is dict:
            with log.layer(f'dict({len(serialized)})', 'deserializing', owner='dict'):
                return self._deserialize__dict(dict, serialized)

        if ser_type in (list, tuple):
            with log.layer(f'list({len(serialized)})', 'deserializing', owner='list'):
                return self._deserialize__list(list, serialized)

        if isinstance(ser_type, str) and type(serialized) is not str:
            ser_type_get = ser_str2type(ser_type)
            if ser_type_get is None:
                res = Undeserializable(
                    type=ser_type_get, 
                    info=f'Unregistered type provided as argument.', 
                    serialized=serialized,
                    ser_type=ser_type
                )
                self._process_invalid('An error occurred during deserialization:', res)
                return res

            _ser_name = self._get_type_name(ser_type_get)
            with log.layer(f'{_ser_name}', 'deserializing', f'{_ser_name}'):
                return self._deserialize__object(serialized, ser_type_get)

        if ser_type in sjson.atomic_types:
            return self._deserialize__atomic(ser_type, serialized)

        _ser_name = self._get_type_name(ser_type)
        with log.layer(f'{_ser_name}', 'deserializing', f'{_ser_name}'):
            return self._deserialize__object(serialized, ser_type)
    
    def _deserialize__object(self, serialized, expected):
        try:
            ser_method = getattr(expected, DESERIALIZE, None)
            if ser_method is None:
                return Undeserializable(
                    type=expected, 
                    info=f'Type {expected} has no deserialize method.', 
                    serialized=serialized,
                    ser_type=expected
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
                    serialized=serialized,
                    ser_type=expected
                )
        except Exception:
            return ExcUndeserializable(
                type=expected, 
                info=f'Exception encountered while deserializing {expected}:', 
                serialized=serialized,
                ser_type=expected
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
