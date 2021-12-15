from dataclasses import dataclass, field, Field, MISSING, is_dataclass, fields
import copy


class _NO_STORE_TYPE:
    pass


NO_STORE = _NO_STORE_TYPE()


class Wrapper:
    WRAPPED_FIELDS_NAME = '_wrapped__fields'

    def __process__(self, obj, wrapped):
        return wrapped

    def __store_process__(self, obj, processed):
        return NO_STORE

    def __store__(self, obj, value, currentvalue):
        return value


class WrappedField(Field):
    def __init__(self, wrapper: Wrapper, default, default_factory, init, repr, hash, compare, metadata) -> None:
        Field.__init__(self, default, default_factory,
                       init, repr, hash, compare, metadata)
        self.wrapper = wrapper

    def __repr__(self):
        return f'wrapped(wrapper={self.wrapper}, field={Field.__repr__(self)})'


def wrapfield(wrapper: Wrapper, *, default=MISSING, default_factory=MISSING, init=True, repr=False, hash=False, compare=False, metadata=None):
    return WrappedField(wrapper, default, default_factory, init, repr, hash, compare, metadata)


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


def attr_wrapped_field(attr: str):
    return f'_wrapped__{attr}'


def attr_wrapper(attr: str):
    return f'_wrapper__{attr}'


def get_wrapper(obj, attr: str):
    return getattr(obj, attr_wrapper(attr), None)


def set_wrapper(obj, attr: str, value: Wrapper):
    return setattr(obj, attr_wrapper(attr), value)


def get_wrapped_field(obj, attr: str):
    return getattr(obj, attr_wrapped_field(attr))


def set_wrapped_field(obj, attr: str, value):
    return setattr(obj, attr_wrapped_field(attr), value)


def _process__wrappedclass(cls, init, repr, eq, order, unsafe_hash, frozen):
    attributes = [a for a in dir(cls) if not a.startswith('__')]
    wrapped_fields = {}

    for attr in attributes:
        value = getattr(cls, attr, None)
        if isinstance(value, WrappedField):
            wrapper: Wrapper = value.wrapper

            # add to list of storeable fields
            lst = wrapped_fields.get(wrapper.WRAPPED_FIELDS_NAME, list())
            lst.append(attr)
            wrapped_fields[wrapper.WRAPPED_FIELDS_NAME] = lst

            # store wrapper
            set_wrapper(cls, attr, wrapper)

    # convert to dataclass
    res = dataclass(cls, init=init, repr=repr, eq=eq,
                    order=order, unsafe_hash=unsafe_hash, frozen=frozen)

    # replace attr fields by the storeable properties
    for k, v in wrapped_fields.items():
        for attr in v:
            setattr(res, attr, property(
                _attr__getter(attr), _attr__setter(attr)
            ))
        setattr(res, k, v)

    return res


def _attr__getter(attr: str):
    def _wrapped__getter(self):
        wrapper: Wrapper = get_wrapper(self, attr)
        value = wrapper.__process__(
            self, getattr(self, attr_wrapped_field(attr)))
        to_store = wrapper.__store_process__(self, value)
        if to_store is not NO_STORE:
            setattr(self, attr_wrapped_field(attr), to_store)
        return value

    return _wrapped__getter


def _attr__setter(attr: str):
    def _wrapped__setter(self, value):
        wrapper: Wrapper = get_wrapper(self, attr)
        to_store = wrapper.__store__(self, value, getattr(
            self, attr_wrapped_field(attr), MISSING))
        if to_store is not NO_STORE:
            setattr(self, attr_wrapped_field(attr), to_store)

    return _wrapped__setter


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


class OverrideWrapper(Wrapper):
    def __init__(self, default_wrapper) -> None:
        Wrapper.__init__(self)
        self.default_wrapper = default_wrapper

    def __store__(self, obj, value, currentvalue):
        if currentvalue is MISSING:
            currentvalue = self.default_wrapper()

        return super().__store__(obj, currentvalue << value, currentvalue)


def overridefield(*, default_factory, init=True, repr=False, hash=False, compare=False, metadata=None):
    return WrappedField(OverrideWrapper(default_factory), MISSING, default_factory, init, repr, hash, compare, metadata)
