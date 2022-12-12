"""
Contains utilities for creating serializable types and to serialize and 
deserialize them into objects that can be encoded through json.
"""


from dataclasses import MISSING, dataclass, fields, is_dataclass, asdict
import inspect
import sys
from typing import Any, Callable, Optional, Sequence, Type


from dman.utils import sjson
from dman.core import log
from dman.core.errors import Trace, Stack, Frame, BaseInvalid, ExcInvalid
from dman.utils.smartdataclasses import configclass
import textwrap
from contextlib import suppress

from enum import Enum


SER_TYPE = "_ser__type"
SER_CONTENT = "_ser__content"
SERIALIZE = "__serialize__"
DESERIALIZE = "__deserialize__"
NO_SERIALIZE = "__no_serialize__"
CONVERT = "__convert__"
DECONVERT = "__de_convert__"


__serializable_types = dict()
__custom_serializable = dict()


@configclass
class Config:
    """Configuration for serializables.

        This class has a global instance that can be accessed as follows:

        >>> dman.core.serializables.config.validate = True
        >>> dman.params.serialize.validate = True  # equivalent

    Args:
        validate (bool, optional): Cancel serialization when an invalid object is encountered. Defaults to False.
    """

    validate: bool = False


config = Config()


def compare_type(base: Type, check: Sequence[Type]):
    """Compare two types, supporting generic types.

    The signature operates similarly to ``isinstance``.
    """
    if not isinstance(check, Sequence):
        check = (check,)
    if base in check:
        return True
    base = getattr(base, "__origin__", MISSING)
    return base is not MISSING and base in check
    

def get_type_name(ser_type):
    """Get the class name of an instance or type."""
    name = getattr(ser_type, "__name__", None)
    if name is None:
        name = getattr(ser_type, "name", str(ser_type))
    return name


def ser_type2str(obj):
    """
    Returns the serialize type string of an object or class."""
    return getattr(obj, SER_TYPE, None)


def ser_str2type(ser):
    """
    Returns the class represented by a serialize type string."""
    return __serializable_types.get(ser, None)


def is_serializable(ser):
    """Check if an object is a serializable type."""
    if _Instance.__convert__(ser) is not None:
        return True
    if is_serializable_type_str(getattr(ser, SER_TYPE, None)):
        return True
    if isinstance(ser, (list, dict, tuple)):
        return True
    if sjson.atomic_type(ser):
        return True
    return type(ser) in __custom_serializable
    

def is_serializable_type_str(ser: str):
    """Check if a string is the name of a registered serializable type."""
    return ser is not None and ser in __serializable_types


def is_deserializable(serialized: Any):
    """Check if an object has been produced through serialization.

    If the serialized object is a dictionary, then it should include
    the serializable type string.
    """
    if sjson.atomic_type(serialized) or isinstance(serialized, (list, tuple)):
        return True
    if not isinstance(serialized, dict):
        return False
    ser_type = serialized.get(SER_TYPE, None)
    if ser_type:
        return is_serializable_type_str(ser_type)
    return False


def register_serializable(
    name: str,
    cls: Type[Any],
    serialize: Callable[[Any, Optional["BaseContext"]], Any] = None,
    deserialize: Callable[[Any, Optional["BaseContext"]], Any] = None,
):
    """Register a class as a serializable type with a given name.

        If the serialize and deserialize methods are not provided then the class
        should have a `__serialize__` and `__deserialize__` method defined.
        In this case however you should prefer using the :func:``serializable``
        decorator instead.

    Args:
        name (str): Name of the serializable
        cls (Type[Any]): Class to register
        serialize (Callable[[Any, Optional[BaseContext]], Any], optional): Serialize method. Defaults to None.
        deserialize (Callable[[Any, Optional[BaseContext]], Any], optional): Deserialize method. Defaults to None.

    Example:
        >>> class Base: ...
        >>> register_serializable('base', Base, lambda obj: '<base>', lambda ser: Base())
    """
    __serializable_types[name] = cls
    if serialize is not None and deserialize is not None:
        __custom_serializable[cls] = (name, serialize, deserialize)


def serializable_types():
    """Return the serializable types dictionary."""
    return __serializable_types


def get_custom_serializable(cls: Type[Any], default=None):
    """Get the signature of a custom serializable object."""
    return __custom_serializable.get(cls, default)

def serialize(obj, context: "BaseContext" = None, content_only: bool = False):
    """Serialize a serializable object.

        The context can be used to store the current directory, logging
        and custom serialization behavior. Serializable objects are created
        using :func:`serializable` or alternatively using :func:`register_serializable`.

        By default, any object that can be handled by json is serializable.
        That is ``str``, ``int``, ``float``, ``None``, ``list``, ``tuple`` and ``dict``.

    Args:
        obj: The object to serialize
        context (BaseContext, optional): The serialization context. Defaults to None.
        content_only (bool, optional): Do not include type information when true.
            Results in more compact serialization. Defaults to False.

    Example:
        >>> @serializable
        >>> @dataclass
        >>> class Base:
        >>>     value: str
        >>> ser = serialize([Base('content'), 'message'])
        >>> print(sjson.dumps(ser, indent=4))
        [
            {
                "_ser__type": "Base",
                "_ser__content": {
                    "value": "content"
                }
            },
            "message"
        ]
        >>> ser = serialize(Base('content'), content_only=True)
        >>> print(sjson.dumps(ser, indent=4))
        {
            "value": "content"
        }
    """

    if context is None:
        context = BaseContext()
    return context.serialize(obj, content_only=content_only)


def deserialize(serialized, context: "BaseContext" = None, expected=None):
    """Deserialize an object produced through serialization.

        The context can be used to store the current directory, logging
        and custom serialization behavior. Deserializable objects are created
        using :func:`serializable` or alternatively using :func:`register_serializable`.

        By default, any object that can be handled by json is deserializable.
        That is ``str``, ``int``, ``float``, ``None``, ``list``, ``tuple`` and ``dict``.

    Args:
        serialized: The object to deserialize.
        context (BaseContext, optional): _description_. Defaults to None.
        expected (_type_, optional): Class or string representing the expected type. If set to
            None the type is received from the dictionary. Defaults to None.

    Example:
        >>> @serializable(name='_base')
        >>> @dataclass
        >>> class Base:
        >>>     value: str
        >>> ser = serialize(Base('content'))
        >>> print(deserialize(ser).value)
        content
        >>> ser = serialize(Base('content'), content_only=True)
        >>> print(deserialize(ser, expected=Base).value)
        content
        >>> print(deserialize(ser, expected='_base').value)
        content
    """

    if context is None:
        context = BaseContext()
    return context.deserialize(serialized, expected)


def _serialize__dataclass(self, context: "BaseContext" = None):
    serialized = dict()
    for f in fields(self):
        if f.name not in getattr(self, NO_SERIALIZE, []):
            value = getattr(self, f.name)
            serialized[f.name] = serialize(value, context)

    return serialized


@classmethod
def _deserialize__dataclass(cls, serialized: dict, context: "BaseContext"):
    res = dict()
    for k, v in serialized.items():
        res[k] = deserialize(v, context)

    return cls(**res)


def _serialize__enum(self):
    return str(self)


@classmethod
def _deserialize__enum(cls, serialized: str):
    *_, name = serialized.split(".")
    return cls[name]


@classmethod
def _default__convert(cls, base):
    return cls(**asdict(base))


def _serialize__template(template: Any, cls: any):
    convert = getattr(template, CONVERT, None)
    if convert is None:
        if not is_dataclass(cls):
            raise ValueError(
                f'Serializable should either be a dataclass or should have a "{CONVERT}" method specified.'
            )
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
        return convert(deserialize(ser, context, expected=template))

    return __deserialize__


def serializable(cls=None, /, *, name: str = None, template: Any = None):
    """Make a class serializable.

        Returns the same class as was passed in and the class is registered as a
        serializable type. Serialization and Deserialization methods are added
        automatically if cls is a dataclass or an Enum. Otherwise a
        ``__serialize__`` and ``__deserialize__`` method should be provided
        for serialization. If these are not provided conversion will fail.

        See :ref:`sphx_glr_gallery_fundamentals_example0_serializables.py` for
        detailed examples on how to create serializable types.

    Args:
        cls (Any): The class to process.
        name (str, optional): The name of the serializable type. Defaults to None.
        template (Any, optional): Template class to use during serialization. Defaults to None.
    """

    def wrap(cls):
        local_name = name
        if local_name is None:
            local_name = getattr(cls, "__name__")
        setattr(cls, SER_TYPE, local_name)
        register_serializable(local_name, cls)

        if template is not None:
            if not hasattr(cls, CONVERT):
                if not is_dataclass(template):
                    raise ValueError(
                        f'Template should be either a dataclass or should have a "{CONVERT}" method defined.'
                    )
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
            raise ValueError(
                f"Class {cls} could not be made serializable. Provide a manual definition of a `__serialize__` and `__deserialize__` method."
            )

        return cls

    # See if we're being called as @serializable or @serializable().
    if cls is None:
        # We're called with parens.
        return wrap

    # We're called as @serializable without parens.
    return wrap(cls)


serializable(Frame, name="__frame")
serializable(Stack, name="__stack")
serializable(Trace, name="__trace")


@serializable(name='__instance')
class _Instance:
    registered = {}
    def __init__(self, name: str):
        if name not in self.__class__.registered:
            raise ValueError('Created an instance tracker for an unregistered name')
        self.name = name
    
    @classmethod
    def __convert__(cls, inst: Any):
        for k, v in cls.registered.items():
            if v is inst:
                return cls(k)
        return None

    def __serialize__(self):
        return self.name
    
    @classmethod
    def __deserialize__(cls, ser):
        return cls.registered[ser]


def register_instance(inst: Any = None, /, *, name: str = MISSING):
    """Register instance for serialization

    Args:
        inst (Any): Instance to serialize. Defaults to None.
        name (str): Name of instances.
    
    Example:
        >>> @dman.register_instance(name='ell1')
        >>> def ell1(x, y):
        >>>     return abs(x) + abs(y)

        >>> dman.register_instance(ell1, name='ell1')
    """
    if name is MISSING:
        raise TypeError("registered_instance() missing 1 required keyword-only argument: 'name'")
    
    def wrap(inst):
        old = _Instance.registered.get(name, None)
        if old is not None:
            log.warning(f'Overwrote registered instance with name {name} from {old.__repr__()} to {inst.__repr__()}.')
        _Instance.registered[name] = inst
        return inst
    if inst is None:
        return wrap
    return wrap(inst)
        


@serializable(name="__unserializable")
class Unserializable(BaseInvalid):
    """Represents an object that could not be serialized."""

    ...


@serializable(name="__exc_unserializable")
class ExcUnserializable(ExcInvalid):
    """Represents an object that could not be serialized due to an exception."""

    ...


@serializable(name="__undeserializable")
@dataclass(repr=False)
class Undeserializable(BaseInvalid):
    """Represents an object that could not be deserialized."""

    serialized: dict = None  #: The serialized object.
    expected: str = None  #: The expected serializable type of the object.

    def format(self):
        yield from super().format()
        if self.serialized:
            yield "\n\nSerialized\n"
            yield textwrap.indent(sjson.dumps(self.serialized, indent=4), " " * 0)

    def __serialize__(self):
        res = super().__serialize__()
        if self.serialized is not None:
            res["serialized"] = self.serialized
        if self.expected is not None:
            res["ser_type"] = self.expected
        return res

    @classmethod
    def __deserialize__(cls, serialized: dict):
        res = cls(**deserialize(serialized))
        if res.serialized is not None:
            return deserialize(res.serialized, res.expected)
        return res


@serializable(name="__exc_undeserializable")
@dataclass(repr=False)
class ExcUndeserializable(ExcInvalid):
    """Represents an object that could not be deserialized due to an exception."""

    serialized: dict
    expected: str

    def format(self):
        yield from super().format()
        if self.serialized:
            yield "\n\nSerialized\n"
            yield textwrap.indent(sjson.dumps(self.serialized, indent=4), " " * 0)

    def __serialize__(self):
        res = super().__serialize__()
        if self.serialized is not None:
            res["serialized"] = self.serialized
        if self.expected is not None:
            res["expected"] = self.expected
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


class SerializationError(Exception):
    """
    Serialization Error raised when an object could not be serialized.
    """

    pass


class ValidationError(SerializationError):
    """
    Validation Error raised when an object could not be validated.
    """

    pass


def validate(obj, msg: str = "Could not validate object"):
    """Check if the object is valid, raise a ValidationError otherwise.

    Args:
        obj: The object to validate
        msg (str, optional): An optional message set in the Validation Error.
            Defaults to 'Could not validate object'.

    Raises:
        ValidationError: The object is not valid.
    """

    if isvalid(obj):
        return
    raise ValidationError(msg, str(obj))


def _call_optional_context(
    method, *args, context=None, exc_type: Type[ExcInvalid] = None, **kwargs
):
    try:
        sig = inspect.signature(method)
        if len(sig.parameters) == len(args):
            return method(*args)
        if len(sig.parameters) == len(args) + 1:
            return method(*args, BaseContext() if context is None else context)
        raise TypeError(
            f"Expected method that takes {len(args)} or {len(args)+1} positional arguments but got {len(sig.parameters)}."
        )
    except SerializationError:
        raise
    except Exception as e:
        if exc_type is None:
            raise e
        return exc_type.from_exception(*sys.exc_info(), **kwargs, ignore=1)


class BaseContext:
    """
    The basic interface for serialization contexts.

    It is passed hierarchically through the hierarchy of objects that
    are being serialized and describes how the serialization should be completed.
    For :class:`dman.model.record.Context` for more information.
    """

    def process_invalid(self, msg: str, obj: BaseInvalid):
        if isinstance(obj, ExcInvalid):
            log.logger.warning(
                msg + "\n" + "".join(BaseInvalid.format(obj)),
                "context",
                obj.trace,
                stacklevel=2,
            )
        else:
            log.logger.warning(msg + "\n" + str(obj), "context", stacklevel=2)

        if config.validate:
            raise ValidationError(
                msg
                + "\n\nDescription:\n"
                + f"[{log.logger.format_stack()}] "
                + str(obj)
            )

    def serialize(self, obj, content_only: bool = False):
        """Serialize a serializable object.

            The context can be used to store the current directory, logging
            and custom serialization behavior. Serializable objects are created
            using :func:`serializable` or alternatively using :func:`register_serializable`.

            By default, any object that can be handled by json is serializable.
            That is ``str``, ``int``, ``float``, ``None``, ``list``, ``tuple`` and ``dict``.

        Args:
            obj: The object to serialize
            context (BaseContext, optional): The serialization context. Defaults to None.
            content_only (bool, optional): Do not include type information when true.
                Results in more compact serialization. Defaults to False.

        See also: :func:`serialize`.
        """
        # check whether the object a registered instance. If so, convert it.
        inst = _Instance.__convert__(obj)
        if inst is not None:
            obj = inst

        if sjson.atomic_type(obj):
            return obj

        if isinstance(obj, (list, tuple)):
            with log.layer(f"list({len(obj)})", "serializing", owner=list):
                return self.serialize_list(obj)

        if isinstance(obj, dict):
            with log.layer(f"dict({len(obj)})", "serializing", owner=dict):
                return self.serialize_dict(obj)

        # if isinstance(ser, BaseInvalid):
        #     self._process_invalid('Invalid object encountered during serialization.', ser)

        with log.layer(f"{type(obj).__name__}", "serializing", owner=obj):
            ser_type, content = self.serialize_object(obj)
            if isinstance(content, BaseInvalid):
                self.process_invalid(
                    "Serialization resulted in an invalid object.", content
                )
                ser_type, content = self.serialize_object(content)

        if content_only:
            return content
        return {SER_TYPE: ser_type, SER_CONTENT: content}

    def serialize_object(self, obj):
        """Serialize a generic serializable object."""
        ser_type, ser_method, _ = get_custom_serializable(type(obj), (None, None, None))
        if ser_type is None:
            ser_type = getattr(obj, SER_TYPE, None)
            if not is_serializable_type_str(ser_type):
                return None, Unserializable(
                    type=type(obj).__name__,
                    info=f"Unserializable type: {type(obj).__name__}.",
                )
            ser_method = getattr(obj, SERIALIZE, None)
            return ser_type, _call_optional_context(
                ser_method,
                context=self,
                exc_type=ExcUnserializable,
                type=type(obj).__name__,
                info="Error during serialization:",
            )
        else:
            return ser_type, _call_optional_context(
                ser_method,
                obj,
                context=self,
                exc_type=ExcUnserializable,
                type=type(obj).__name__,
                info="Error during serialization:",
            )

    def serialize_list(self, obj: list):
        """Serialize a list."""
        return [itm if sjson.atomic_type(itm) else self.serialize(itm) for itm in obj]

    def serialize_dict(self, obj: dict):
        """Serialize a dictionary."""
        return {self.serialize(k): self.serialize(v) for k, v in obj.items()}

    def deserialize(self, serialized, ser_type=None):
        """Deserialize an object produced through serialization.

            The context can be used to store the current directory, logging
            and custom serialization behavior. Deserializable objects are created
            using :func:`serializable` or alternatively using :func:`register_serializable`.

            By default, any object that can be handled by json is deserializable.
            That is ``str``, ``int``, ``float``, ``None``, ``list``, ``tuple`` and ``dict``.

        Args:
            serialized: The object to deserialize.
            context (BaseContext, optional): _description_. Defaults to None.
            expected (_type_, optional): Class or string representing the expected type. If set to
                None the type is received from the dictionary. Defaults to None.

            See also: :func:`deserialize`.
        """
        res = self._deserialize_inner(serialized, ser_type)
        if isinstance(res, BaseInvalid):
            self.process_invalid("An error occurred during deserialization:", res)
        return res

    def _deserialize_inner(self, serialized, expected=None):
        if serialized is None:
            return None

        if expected is None:
            if isinstance(serialized, (list, tuple)):
                with log.layer(f"list({len(serialized)})", "deserializing", owner=list):
                    return self.deserialize_list(serialized, list)

            if sjson.atomic_type(serialized):
                return self.deserialize_atomic(serialized, type(serialized))

            if not isinstance(serialized, dict):
                return Undeserializable(
                    type=expected,
                    info=f"Unexpected type for serialized: {type(serialized)}. Expected either list, tuple, atomic type or dict.",
                    serialized=serialized,
                )

            expected = serialized.get(SER_TYPE, MISSING)
            if expected is MISSING:
                with log.layer(f"dict({len(serialized)})", "deserializing", owner=dict):
                    return self.deserialize_dict(serialized, dict)
            else:
                serialized = serialized.get(SER_CONTENT, {})
                ser_type_get = ser_str2type(expected)
                if ser_type_get is None:
                    return Undeserializable(
                        type=ser_type_get,
                        info=f"Unregistered type stored in serialized.",
                        serialized=serialized,
                        expected=expected,
                    )

                _ser_name = get_type_name(ser_type_get)
                with log.layer(f"{_ser_name}", "deserializing", owner=ser_type_get):
                    return self.deserialize_object(serialized, ser_type_get)

        if compare_type(expected, dict):
            with log.layer(f"dict({len(serialized)})", "deserializing", owner=dict):
                return self.deserialize_dict(serialized, dict)

        if compare_type(expected, (list, tuple)):
            with log.layer(f"list({len(serialized)})", "deserializing", owner=list):
                return self.deserialize_list(serialized, list)

        if isinstance(expected, str):
            ser_type_get = ser_str2type(expected)
            if ser_type_get is None:
                return Undeserializable(
                    type=ser_type_get,
                    info=f"Unregistered type provided as argument.",
                    serialized=serialized,
                    expected=expected,
                )
            expected = ser_type_get

        if expected in sjson.atomic_types:
            return self.deserialize_atomic(serialized, expected)

        _ser_name = get_type_name(expected)
        with log.layer(f"{_ser_name}", "deserializing", owner=expected):
            return self.deserialize_object(serialized, expected)

    def deserialize_object(self, serialized, expected):
        """Deserialize an object of an expected type."""
        _, _, ser_method = get_custom_serializable(expected, (None, None, None))
        if ser_method is None:
            ser_method = getattr(expected, DESERIALIZE, None)
        if ser_method is None:
            return Undeserializable(
                get_type_name(expected), 
                f"Could not recover __deserialize__ method for type '{get_type_name(expected)}'.", 
                serialized
            )
        return _call_optional_context(
            ser_method,
            serialized,
            context=self,
            exc_type=ExcUndeserializable,
            type=ser_type2str(expected),
            info=f"Exception encountered while deserializing {expected}:",
            serialized=serialized,
            expected=ser_type2str(expected),
        )

    def deserialize_atomic(self, serialized, expected):
        """Deserialize an atomic object of an expected type"""
        with suppress(ValueError):
            return expected(serialized)
        if expected is not type(serialized):
            return Undeserializable(
                type=expected,
                info=f"Specified type {expected}, but got {type(serialized)}.",
                serialized=serialized,
            )
        return serialized

    def deserialize_list(self, serialized, expected):
        res = [
            itm if sjson.atomic_type(itm) else self.deserialize(itm)
            for itm in serialized
        ]
        if expected is list:
            return res
        return expected(res)

    def deserialize_dict(self, serialized: dict, expected):
        res = {self.deserialize(k): self.deserialize(v) for k, v in serialized.items()}
        if expected is dict:
            return res
        return expected(res)
