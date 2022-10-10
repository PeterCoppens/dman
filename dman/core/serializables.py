from contextlib import suppress

from dataclasses import MISSING, dataclass, field, fields, is_dataclass, asdict
import inspect
import re
import sys
import traceback
from typing import Any, Callable, List, Optional, Sequence, Type
from types import TracebackType



from dman.utils import sjson
from dman.core import log
import textwrap

from enum import Enum


SER_TYPE = '_ser__type'
SER_CONTENT = '_ser__content'
SERIALIZE = '__serialize__'
DESERIALIZE = '__deserialize__'
NO_SERIALIZE = '__no_serialize__'
CONVERT = '__convert__'
DECONVERT = '__de_convert__'



__serializable_types = dict()
__custom_serializable = dict()


def compare_type(base: Type, check: Sequence[Type]):
    if not isinstance(check, Sequence):
        check = (check,)
    if base in check:
        return True
    base = getattr(base, '__origin__', MISSING)
    return base is not MISSING and base in check


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


def is_serializable_type_str(ser: str):
    return ser is not None and ser in __serializable_types


def is_serializable(ser):
    """
    Check if an object supports serialization
    """
    if is_serializable_type_str(getattr(ser, SER_TYPE, None)):
        return True
    if isinstance(ser, (list, dict, tuple)):
        return True
    if sjson.atomic_type(ser):
        return True
    return type(ser) in __custom_serializable


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
        return is_serializable_type_str(ser_type)
    return False


def register_serializable(name: str, cls: Type[Any], *, serialize: Callable[[Any, Optional['BaseContext']], Any] = None, deserialize: Callable[[Any, Optional['BaseContext']], Any] = None):
    """
    Register a class as a serializable type with a given name
    """
    __serializable_types[name] = cls
    if serialize is not None and deserialize is not None:
        __custom_serializable[cls] = (name, serialize, deserialize)


def get_custom_serializable(cls: Type[Any], default=None):
    return __custom_serializable.get(cls, default)


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
        
        if not hasattr(cls, SERIALIZE) or not hasattr(cls, DESERIALIZE):
            raise ValueError(f'Class {cls} could not be made serializable. Provide a manual definition of a `__serialize__` and `__deserialize__` method.')

        return cls

    # See if we're being called as @serializable or @serializable().
    if cls is None:
        # We're called with parens.
        return wrap

    # We're called as @serializable without parens.
    return wrap(cls)
 

class BaseInvalid:
    ...


@serializable(name='__frame')
@dataclass
class Frame:
    filename: str
    lineno: int
    name: str
    line: str = ""

    def __post_init__(self):
        if isinstance(self.lineno, str):
            self.lineno = int(self.lineno)

    def __str__(self):
        return f"File {self.filename}, line {self.lineno}, in {self.name}: {self.line}"

    def __serialize__(self):
        return str(self)

    @classmethod
    def __deserialize__(cls, ser):
        pattern = r"File (?P<filename>.*), line (?P<lineno>[0-9]*), in (?P<name>.*): (?P<line>)"
        res, *_ = re.findall(pattern, ser)
        return cls(*res)
    
    def summary(self):
        return traceback.FrameSummary(self.filename, self.lineno, self.name)



@serializable(name='__stack')
@dataclass
class Stack:
    exc_type: str
    exc_value: str
    is_cause: bool = False
    frames: List[Frame] = field(default_factory=list)

    def __serialize__(self):
        res = {"exc": f"{self.exc_type}({self.exc_value})"}
        if self.is_cause:
            res["is_cause"] = True
        res["frames"] = [frame.__serialize__() for frame in self.frames]
        return res
    
    def __str__(self):
        return self.format_exception()

    @classmethod
    def __deserialize__(cls, ser: dict):
        exc = ser.pop("exc")
        pattern = r"(?P<filename>.*)\((?P<name>.*)\)"
        (ser["exc_type"], ser["exc_value"]), *_ = re.findall(pattern, exc)
        res = cls(**ser)
        res.frames = [Frame.__deserialize__(frame) for frame in res.frames]
        return res

    def format_exception(self):
        yield f'{self.exc_type}: {self.exc_value}'
    
    def format(self, *, single: bool = False):
        if single:
            yield '\n'
        elif not self.is_cause:
            yield '\n\nThe above exception was the direct cause of the following exception:\n\n'
            
        if len(self.frames) > 0:
            yield 'Traceback (most recent call last):\n'
            yield from traceback.StackSummary.from_list(
                [frame.summary() for frame in self.frames]
            ).format()

        yield from self.format_exception()


@serializable(name='__trace')
@dataclass
class Trace:
    stacks: List[Stack] = field(default_factory=list)

    def __serialize__(self):
        return [stack.__serialize__() for stack in self.stacks]

    @classmethod
    def __deserialize__(cls, ser: list):
        return cls([Stack.__deserialize__(stack) for stack in ser])

    @classmethod
    def from_exception(
        cls,
        exc_type: Type[BaseException],
        exc_value: BaseException,
        exc_tb: TracebackType,
    ):
        def safe_str(_object: Any) -> str:
            try:
                return str(_object)
            except Exception:
                return "<exception str() failed>"

        stacks: List[Stack] = []
        is_cause = False

        while True:
            summary = traceback.extract_tb(exc_tb)
            frames = [Frame(f.filename, f.lineno, f.name, f.line) for f in summary]
            stacks.append(
                Stack(
                    safe_str(exc_type.__name__), safe_str(exc_value), is_cause, frames
                )
            )

            cause = getattr(exc_value, "__cause__", None)
            if cause and cause.__traceback__:
                exc_type = cause.__class__
                exc_value = cause
                exc_tb = cause.__traceback__
                is_cause = True
                continue

            cause = exc_value.__context__
            if (
                cause
                and cause.__traceback__
                and not getattr(exc_value, "__suppress_context__", False)
            ):
                exc_type = cause.__class__
                exc_value = cause
                exc_tb = cause.__traceback__
                is_cause = False
                continue
            # No cover, code is reached but coverage doesn't recognize it.
            break  # pragma: no cover

        return cls(stacks)
    
    def format(self):
        for stack in reversed(self.stacks):
            yield from stack.format(single=len(self.stacks) == 1)



@serializable(name='__unserializable')
@dataclass(repr=False)
class Unserializable(BaseInvalid):
    type: str
    info: str

    def __serialize__(self):
        res = {'type': self.type}
        if len(self.info) > 0:
            res['info'] = self.info
        return res

    def __repr__(self):
        return f'{self.__class__.__name__}: {self.type}'

    def __str__(self):
        return self.__repr__() + '\n' + ' '*2 + self.info


@serializable(name = '__exc_unserializable')
@dataclass(repr=False)
class ExcUnserializable(Unserializable):
    trace: Trace

    @classmethod
    def from_exception(
        cls,
        type: str,
        info: str,
        exc_type: Type[BaseException],
        exc_value: BaseException,
        exc_tb: TracebackType,
    ):
        trace = Trace.from_exception(exc_type, exc_value, exc_tb)
        return cls(type, info, trace)

    def __str__(self):
        return super().__str__() + '\n' + ''.join(self.trace.format())
    
    def __serialize__(self):
        res = super().__serialize__()
        res['trace'] = self.trace.__serialize__()
        return res
    
    @classmethod
    def __deserialize__(cls, ser, context):
        res = super().__deserialize__(ser, context)
        res.trace = Trace.__deserialize__(res.trace)
        return res


@serializable(name='__undeserializable')
@dataclass
class Undeserializable(Unserializable):
    serialized: dict = None
    expected: str = None

    def __repr__(self):
        return f'Undeserializable: {self.type}'
    
    def __post_init__(self):
        if not isinstance(self.expected, str):
            self.expected = ser_type2str(self.expected)

    def __str__(self):
        res = super().__str__()
        if self.serialized:
            res += '\n\nSerialized\n'
            res += textwrap.indent(sjson.dumps(self.serialized, indent=4), ' '*0)
        return res

    def __serialize__(self):
        res = super().__serialize__()
        if self.serialized is not None:
            res['serialized'] = self.serialized
        if self.expected is not None:
            res['ser_type'] = self.expected
        return res
    
    @classmethod
    def __deserialize__(cls, serialized: dict, context):
        res = cls(**deserialize(serialized, context))
        if res.serialized is not None:
            return deserialize(res.serialized, context, res.expected)
        return res



@serializable(name='__exc_undeserializable')
@dataclass
class ExcUndeserializable(ExcUnserializable):
    serialized: dict
    expected: str

    @classmethod
    def from_exception(
        cls,
        type: str,
        info: str,
        serialized: dict,
        expected: str,
        exc_type: Type[BaseException],
        exc_value: BaseException,
        exc_tb: TracebackType,
    ):
        trace = Trace.from_exception(exc_type, exc_value, exc_tb)
        return cls(type, info, trace, serialized, expected)

    def __repr__(self):
        return f'Undeserializable: {self.type}'
    
    def __post_init__(self):
        if not isinstance(self.expected, str):
            self.expected = ser_type2str(self.expected)

    def __str__(self):
        res = super().__str__()
        if self.serialized:
            res += '\n\nSerialized\n'
            res += textwrap.indent(sjson.dumps(self.serialized, indent=2), ' '*0)
        return res

    def __serialize__(self):
        res = super().__serialize__()
        if self.serialized is not None:
            res['serialized'] = self.serialized
        if self.expected is not None:
            res['expected'] = self.expected
        return res
    
    @classmethod
    def __deserialize__(cls, serialized: dict, context):
        res = cls(**serialized)
        if res.serialized is not None:
            return deserialize(res.serialized, context, res.expected)
        return res


def isvalid(obj):
    """
    Check if an object is valid
    """
    if isinstance(obj, dict):
        return not issubclass(ser_str2type(obj.get(SER_TYPE, None)), BaseInvalid)
    return not isinstance(obj, BaseInvalid)


class ValidationError(Exception):
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


def _call_optional_context(method, *args, context=None):
    sig = inspect.signature(method)
    if len(sig.parameters) == len(args): 
        return method(*args)
    if len(sig.parameters) == len(args) + 1:
        return method(*args, BaseContext() if context is None else context)
    raise TypeError(f'Expected method that takes {len(args)} or {len(args)+1} positional arguments but got {len(sig.parameters)}.')


 
class BaseContext: 
    """
    The basic interface for serialization contexts.
    """
    VALIDATE = False
    def __init__(self, validate: bool = None):
        self.validate = self.VALIDATE if validate is None else validate
    
    def _process_invalid(self, msg: str, obj: BaseInvalid):
        log.warning(msg + '\n' + str(obj), 'context')
        if self.validate:
            raise ValidationError(msg + '\n\nDescription:\n' + f'[{log.logger.format_stack()}] ' + str(obj))

    def serialize(self, ser, content_only: bool = False):         
        if sjson.atomic_type(ser):
            return ser

        if isinstance(ser, (list, tuple)):
            with log.layer(f'list({len(ser)})', 'serializing', owner=list):
                return self._serialize__list(ser)

        if isinstance(ser, dict):
            with log.layer(f'dict({len(ser)})', 'serializing', owner=dict):
                return self._serialize__dict(ser)

        if isinstance(ser, BaseInvalid):
            self._process_invalid('Invalid object encountered during serialization.', ser)

        with log.layer(f'{type(ser).__name__}', 'serializing', owner=ser):
            ser_type, content = self._serialize__object(ser)
            if isinstance(content, BaseInvalid):
                self._process_invalid('Invalid object encountered during serialization.', content)
                ser_type, content = self._serialize__object(content)

        if content_only:
            return content
        return {SER_TYPE: ser_type, SER_CONTENT: content}

    def _serialize__object(self, ser):
        ser_type, ser_method, _ = get_custom_serializable(type(ser), (None, None, None))
        
        try:
            if ser_type is None:
                ser_type = getattr(ser, SER_TYPE, None)
                if not is_serializable_type_str(ser_type):
                    return None, Unserializable(
                        type=type(ser).__name__, 
                        info=f'Unserializable type: {type(ser).__name__}.'
                    )
                ser_method = getattr(ser, SERIALIZE, None)
                return ser_type, _call_optional_context(ser_method, context=self)
            else:
                return ser_type, _call_optional_context(ser_method, ser, context=self)
        except Exception as e:
            if isinstance(e, ValidationError):
                raise e
            return ser_type, ExcUnserializable.from_exception(
                type(ser).__name__, 
                'Error during serialization:',
                *sys.exc_info()
            )

    def _serialize__list(self, ser: list):
        return [itm if sjson.atomic_type(itm) else self.serialize(itm) for itm in ser]

    def _serialize__dict(self, ser: dict):
        return {self.serialize(k): self.serialize(v) for k, v in ser.items()}
        
    def _get_type_name(_, ser_type):
        name = getattr(ser_type, '__name__', None)
        if name is None:
            name = getattr(ser_type, 'name', str(ser_type))
        return name
    
    def deserialize(self, serialized, ser_type=None):
        res = self._deserialize_inner(serialized, ser_type)
        if isinstance(res, BaseInvalid):
            self._process_invalid('An error occurred during deserialization:', res)
        return res

    def _deserialize_inner(self, serialized, expected=None):            
        if serialized is None:
            return None

        if expected is None:
            if isinstance(serialized, (list, tuple)):
                with log.layer(f'list({len(serialized)})', 'deserializing', owner=list):
                    return self._deserialize__list(list, serialized)

            if sjson.atomic_type(serialized):
                return self._deserialize__atomic(type(serialized), serialized)

            if not isinstance(serialized, dict):
                return Undeserializable(
                    type=expected,
                    info=f'Unexpected type for serialized: {type(serialized)}. Expected either list, tuple, atomic type or dict.',
                    serialized=serialized
                )

            expected = serialized.get(SER_TYPE, MISSING)
            if expected is MISSING:
                with log.layer(f'dict({len(serialized)})', 'deserializing', owner=dict):
                    return self._deserialize__dict(dict, serialized)
            else:
                serialized = serialized.get(SER_CONTENT, {})
                ser_type_get = ser_str2type(expected)
                if ser_type_get is None:
                    return Undeserializable(
                        type=ser_type_get, 
                        info=f'Unregistered type stored in serialized.', 
                        serialized=serialized,
                        expected=expected
                    )

                _ser_name = self._get_type_name(ser_type_get)
                with log.layer(f'{_ser_name}', 'deserializing', owner=ser_type_get):
                    return self._deserialize__object(serialized, ser_type_get)

        if compare_type(expected, dict):
            with log.layer(f'dict({len(serialized)})', 'deserializing', owner=dict):
                return self._deserialize__dict(dict, serialized)

        if compare_type(expected, (list, tuple)):
            with log.layer(f'list({len(serialized)})', 'deserializing', owner=list):
                return self._deserialize__list(list, serialized)

        if isinstance(expected, str) and type(serialized) is not str:
            ser_type_get = ser_str2type(expected)
            if ser_type_get is None:
                return Undeserializable(
                    type=ser_type_get, 
                    info=f'Unregistered type provided as argument.', 
                    serialized=serialized,
                    expected=expected
                )
            expected = ser_type_get

        if expected in sjson.atomic_types:
            return self._deserialize__atomic(expected, serialized)

        _ser_name = self._get_type_name(expected)
        with log.layer(f'{_ser_name}', 'deserializing', owner=expected):
            return self._deserialize__object(serialized, expected)
    
    def _deserialize__object(self, serialized, expected):
        _, _, ser_method = get_custom_serializable(expected, (None, None, None))
        if ser_method is None:
            ser_method = getattr(expected, DESERIALIZE, None)

        try:
            return _call_optional_context(ser_method, serialized, context=self)
        except Exception as e:
            if isinstance(e, ValidationError):
                raise e
            return ExcUndeserializable.from_exception(
                expected, 
                f'Exception encountered while deserializing {expected}:', 
                serialized,
                expected,
                *sys.exc_info()
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
        res = [itm if sjson.atomic_type(itm) else self.deserialize(itm) for itm in ser]
        if cls is list:
            return res
        return cls(res)

    def _deserialize__dict(self, cls, ser: dict):
        res = {self.deserialize(k): self.deserialize(v) for k, v in ser.items()}
        if cls is dict:
            return res
        return cls(res)