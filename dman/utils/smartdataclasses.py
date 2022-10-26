from dataclasses import asdict, dataclass, field, Field, MISSING, is_dataclass, fields
import copy
from typing import Callable, Union, Type, List
from dman.utils import sjson


def idataclass(cls=None, /, *, init=True, repr=True, eq=True, order=False, 
                unsafe_hash=False, frozen=False):
    """
    Convert a class to an iterable dataclass.
        Returns the same class as was passed in, with dunder methods added based on the fields
        defined in the class.
        The class is automatically made ``iterable`` by adding ``__iter__``

        The arguments of the ``dataclass`` decorator are provided.

    :param bool init: add an ``__init__`` method. 
    :param bool repr: add a ``__repr__`` method. 
    :param bool order: rich comparison dunder methods are added. 
    :param bool unsafe_hash: add a ``__hash__`` method function.
    :param bool frozen: fields may not be assigned to after instance creation.
    """

    def wrap(cls):
        res = dataclass(cls, init=init, repr=repr, eq=eq, order=order, unsafe_hash=unsafe_hash, frozen=frozen)
        setattr(res, '__iter__', lambda self: (getattr(self, f.name) for f in fields(self)))
        return res

    # See if we're being called as @idataclass or @idataclass().
    if cls is None:
        # We're called with parens.
        return wrap

    # We're called as @idataclass without parens.
    return wrap(cls)


BASE_KEY = '__base'
PROP_KEY = '__property'
LABEL_KEY = '__label'
WRAPPED_DICT_KEY = '__wrapped_fields'


WrapField = Callable[[str], property]


def wrapfield(wrap: Union[WrapField, property], /, *, label: str = None, 
    default=MISSING, default_factory=MISSING, init=True, repr=False, 
    hash=False, compare=False, metadata: dict = None) -> Field:

    _metadata = {PROP_KEY: wrap}
    if metadata is not None: _metadata[BASE_KEY] = metadata
    if label is not None: _metadata[LABEL_KEY] = label

    return field(default=default, default_factory=default_factory, 
        init=init, repr=repr, hash=hash, compare=compare, metadata=_metadata)


def is_wrapfield(fld: Field):
    return fld.metadata.get(PROP_KEY, None) is not None


def get_wrapfield(fld: Field, *, default=None):
    if fld.metadata is None:
        return default
    return fld.metadata.get(PROP_KEY, default)


def wrappedclass(cls=None, /, *, init=True, repr=True, eq=True, order=False,
    unsafe_hash=False, frozen=False):

    def wrap(cls):
        return _process__wrappedclass(cls, init, repr, eq, order, unsafe_hash, frozen)

    # See if we're being called as @modelclass or @modelclass().
    if cls is None:
        # We're called with parens.
        return wrap

    # We're called as @modelclass without parens.
    return wrap(cls)


def _process__wrappedclass(cls, init, repr, eq, order, unsafe_hash, frozen):
    # convert to dataclass
    res = cls
    if not is_dataclass(cls):
        res = dataclass(cls, init=init, repr=repr, eq=eq,
            order=order, unsafe_hash=unsafe_hash, frozen=frozen)
    
    # go through fields and process wrapped fields
    for f in fields(res):
        if is_wrapfield(f):
            prop = f.metadata.get(PROP_KEY)
            if callable(prop):
                prop = prop(key=f.name)
            if hasattr(prop, '__set_name__'):
                prop.__set_name__(cls, f.name)
            label = f.metadata.get(LABEL_KEY, None)
            f.metadata = f.metadata.get(BASE_KEY, None)
            setattr(res, f.name, prop)

            if label is not None:
                wrapped = getattr(res, WRAPPED_DICT_KEY, dict())
                lst = wrapped.get(label, list())
                lst.append(f.name)
                wrapped[label] = lst
                setattr(res, WRAPPED_DICT_KEY, wrapped)

    return res


def wrappedfields(cls, label: str):
    wrapped = getattr(cls, WRAPPED_DICT_KEY, dict())
    return wrapped.get(label, list())


AUTO = '_merg__auto'
OVERRIDABLE_TYPE = '_overridable'


def is_overrideable(cls):
    return getattr(cls, OVERRIDABLE_TYPE, False)


def overrideable(cls=None, /, *, init=True, repr=True, eq=True, order=False,
                 unsafe_hash=False, frozen=True):

    def wrap(cls):
        annotations = cls.__dict__.get('__annotations__', dict())

        for k in annotations:
            fld: Field = getattr(cls, k, None)
            if fld is None:
                setattr(cls, k, field(default=AUTO))
            elif isinstance(fld, Field):
                if fld.default is MISSING and fld.default_factory is MISSING:
                    fld.default=AUTO
                else:
                    setattr(cls, k, field(default=fld.default, default_factory=fld.default_factory,
                            init=True, repr=fld.repr, hash=fld.hash, compare=fld.compare, metadata=fld.metadata))
            else:
                setattr(cls, k, field(default=fld))

        res = dataclass(cls, init=init, repr=repr, eq=eq,
                        order=order, unsafe_hash=unsafe_hash, frozen=frozen)

        setattr(res, '__lshift__', _override__lshift__)
        setattr(res, '__rshift__', _override__rshift__)
        setattr(res, OVERRIDABLE_TYPE, True)

        return res

    # See if we're being called as @serializable or @serializable().
    if cls is None:
        # We're called with parens.
        return wrap

    # We're called as @serializable without parens.
    return wrap(cls)


def is_complete(value):
    for f in fields(value):
        if getattr(value, f.name) == AUTO:
            return False
    return True


def _override__rshift__(self, other):
    result = copy.deepcopy(self)
    if not is_dataclass(other) or not is_dataclass(self):
        return result

    flds = {}

    other_flds = [fld.name for fld in fields(other)]

    for fld in fields(self):
        attr = getattr(self, fld.name)
        if attr == AUTO and fld.name in other_flds:
            flds[fld.name] = getattr(other, fld.name)
        elif is_overrideable(attr) and fld.name in other_flds:
            flds[fld.name] = _override__rshift__(
                attr, getattr(other, fld.name))
        else:
            flds[fld.name] = attr

    return self.__class__(**flds)


def _override__lshift__(self, other):
    return _override__rshift__(other, self)




CONFIGFIELD = "_configclass"
OPTIONFIELD = "__option__"


def is_configclass(cls):
    return hasattr(cls, "_configclass")


def _option_key(key: str):
    return f"{OPTIONFIELD}{key}"


def get_option(self, key: str, default=MISSING):
    key = _option_key(key)
    if default is MISSING:
        return getattr(self, key)
    else:
        return getattr(self, key, default)


def set_option(self, key: str, value):
    setattr(self, _option_key(key), value)


def options(cls, key: str):
    if isinstance(key, str):
        for f in fields(cls):
            if f.name == key:
                key = f
                break
        else:
            raise ValueError(f'Could not find field with name "{key}"')
    return getattr(get_wrapfield(key), "options", None)


class OptionField:
    def __init__(self, tp: Type = None, options: List = None):
        self.tp = tp
        self.options = options
        self.key = None

    def __set_name__(self, owner, name):
        self.key = name

    @property
    def tp(self):
        return self._tp

    @tp.setter
    def tp(self, value: Type):
        if (
            value is not None
            and value not in sjson.atomic_types
            and not is_configclass(value)
        ):
            raise TypeError(
                "Invalid type for field of configclass. Only atomic types are supported."
            )
        self._tp = value
    
    def __get__(self, obj, objtype=None):
        if not hasattr(obj, _option_key(self.key)):
            return self.options
        return get_option(obj, self.key)
    
    def __set__(self, obj, value):
        if not isinstance(value, self.tp):
            raise ValueError(
                f"Invalid type assigned to field. Expected {self.tp} got {type(value)}"
            )
        if self.options is not None and value not in self.options:
            raise ValueError(
                (
                    f"Invalid value assigned to field. "
                    f'Expected "{"|".join([str(s) for s in  self.options])}" got "{value}".'
                )
            )
        set_option(obj, self.key, value)


def optionfield(
    options: list = None,
    *,
    default=MISSING,
    default_factory=MISSING,
    repr: bool = True,
    tp: Type = None,
):
    wrap = OptionField(tp=tp, options=options)
    return wrapfield(
        wrap,
        default=default,
        default_factory=default_factory,
        label=OPTIONFIELD,
        repr=repr,
    )


def configclass(cls=None):
    """
    Convert a class to a configclass
    """

    def wrap(cls):
        if not is_dataclass(cls):
            cls = dataclass(cls)
        for f in fields(cls):
            wrapped_field: Field = optionfield(tp=f.type, options=options(cls, f))
            f.metadata = wrapped_field.metadata
            if f.default is MISSING and f.default_factory is MISSING:
                raise ValueError(
                    (
                        f"All fields for a configclass should have defaults."
                        f" Found {f.name} without one."
                    )
                )
        cls = wrappedclass(cls)
        setattr(cls, CONFIGFIELD, True)
        return cls

    # See if we're being called as @configclass or @configclass().
    if cls is None:
        # We're called with parens.
        return wrap

    # We're called as @configclass without parens.
    return wrap(cls)


def override(left, right, *, inplace: bool = False, ignore: list = None):
    if not inplace:
        left = copy.deepcopy(left)
    if ignore is None:
        ignore = []

    if is_configclass(right):
        right = asdict(right)
    for f in fields(left):
        value = right.get(f.name, MISSING)
        if value is MISSING or value in ignore:
            continue
        if is_configclass(f.type):
            setattr(left, f.name, override(getattr(left, f.name), value, ignore=ignore))
        else:
            setattr(left, f.name, value)

    return left     