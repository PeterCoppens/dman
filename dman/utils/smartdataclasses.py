from dataclasses import asdict, dataclass, field, Field, MISSING, is_dataclass, fields
import copy
from typing import Any, Callable, TypeVar, Type, List
from typing_extensions import dataclass_transform
from dman.utils import sjson


BASE_KEY = "__base"
DESCRIPTOR_KEY = "__descriptor"
DESCRIPTOR = Any
CONFIGFIELD = "_configclass"

_T = TypeVar("_T")

@dataclass_transform(field_specifiers=(Field, field))
def idataclass(
    cls=None,
    *,
    init=True,
    repr=True,
    eq=True,
    order=False,
    unsafe_hash=False,
    frozen=False,
) -> Callable[[Type[_T]], Type[_T]]:
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
        res = dataclass(
            cls,
            init=init,
            repr=repr,
            eq=eq,
            order=order,
            unsafe_hash=unsafe_hash,
            frozen=frozen,
        )
        setattr(
            res, "__iter__", lambda self: (getattr(self, f.name) for f in fields(self))
        )
        return res

    return wrap if cls is None else wrap(cls)


def wrapfield(
    wrap: DESCRIPTOR,
    /,
    *,
    default=MISSING,
    default_factory=MISSING,
    init=True,
    repr=False,
    hash=False,
    compare=False,
    metadata: dict = None,
) -> Field:

    _metadata = {DESCRIPTOR_KEY: wrap}
    if metadata is not None:
        _metadata[BASE_KEY] = metadata
    if not hasattr(wrap, "__set__"):
        init = False

    return field(
        default=default,
        default_factory=default_factory,
        init=init,
        repr=repr,
        hash=hash,
        compare=compare,
        metadata=_metadata,
    )


def is_wrapfield(fld: Field):
    return fld.metadata is not None and fld.metadata.get(DESCRIPTOR_KEY, None) is not None


def get_descriptor(fld: Field):
    return fld.metadata.get(DESCRIPTOR_KEY, None)


def set_descriptor(fld: Field, value):
    fld.metadata[DESCRIPTOR_KEY] = value


@dataclass_transform(field_specifiers=(wrapfield, field, Field))
def wrappedclass(
    cls=None,
    /,
    *,
    init=True,
    repr=True,
    eq=True,
    order=False,
    unsafe_hash=False,
    frozen=False,
) -> Callable[[Type[_T]], Type[_T]]:
    def wrap(cls):
        # convert to dataclass
        res = cls
        if not is_dataclass(cls):
            res = dataclass(
                cls,
                init=init,
                repr=repr,
                eq=eq,
                order=order,
                unsafe_hash=unsafe_hash,
                frozen=frozen,
            )

        # go through fields and process wrapped fields
        for f in fields(res):
            if is_wrapfield(f):
                prop = f.metadata.get(DESCRIPTOR_KEY)
                if hasattr(prop, "__set_name__"):
                    prop.__set_name__(cls, f.name)
                f.metadata = f.metadata.get(BASE_KEY, None)
                setattr(res, f.name, prop)

        return res

    return wrap if cls is None else wrap(cls)


def is_configclass(cls):
    return hasattr(cls, "_configclass")


class OptionField:
    def __init__(self, tp: Type = None, options: List = None):
        self.tp = tp
        self.options = options
        self.key = None

    def __set_name__(self, owner, name):
        self.key = f"_{name}"

    def __get__(self, obj, objtype=None):
        if not hasattr(obj, self.key):
            return self.options
        return getattr(obj, self.key)

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
        setattr(obj, self.key, value)


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
        repr=repr,
    )


@dataclass_transform(field_specifiers=(wrapfield, optionfield, field, OptionField, Field))
def configclass(cls=None, /, *, atomic: bool = True, force_defaults: bool = True) -> Callable[[Type[_T]], Type[_T]]:
    """Convert a class to a configclass."""

    def wrap(cls):
        if not is_dataclass(cls):
            cls = dataclass(cls)

        for f in fields(cls):
            # get the list of options (if available)
            options = cls.__dict__.get(f.name, None)
            options = None if not isinstance(options, OptionField) else options.options

            # check if the type is atomic if required
            if atomic and (
                f.type not in sjson.atomic_types and not is_configclass(f.type)
            ):
                raise ValueError(
                    f"Specified field with non-atomic type {f.type} for atomic configclass."
                )

            # update field with new type
            wrapped_field: Field = optionfield(tp=f.type, options=options)
            f.metadata = wrapped_field.metadata

            # check if all types have defaults
            if force_defaults and f.default is MISSING and f.default_factory is MISSING:
                raise ValueError(
                    (
                        f"All fields for the configclass should have defaults."
                        f" Found {f.name} without one."
                    )
                )

        cls = wrappedclass(cls)
        setattr(cls, CONFIGFIELD, True)
        return cls

    return wrap if cls is None else wrap(cls)


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
