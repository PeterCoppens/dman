from abc import ABC, abstractmethod

from dataclasses import dataclass, field, Field, MISSING, is_dataclass, fields


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
        Field.__init__(self, default, default_factory, init, repr, hash, compare, metadata)
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


def _process__wrappedclass(cls, init, repr, eq, order, unsafe_hash, frozen):
    attributes = [a for a in dir(cls) if not a.startswith('__')]
    wrapped_fields = {}

    for attr in attributes:
        value = getattr(cls, attr, None)
        if isinstance(value, WrappedField):
            wrapper: Wrapper = value.wrapper

            # add to list of storable fields
            lst = wrapped_fields.get(wrapper.WRAPPED_FIELDS_NAME, list())
            lst.append(attr)
            wrapped_fields[wrapper.WRAPPED_FIELDS_NAME] = lst
            
            # store wrapper
            set_wrapper(cls, attr, wrapper)

    # convert to dataclass
    res = dataclass(cls, init=init, repr=repr, eq=eq, order=order, unsafe_hash=unsafe_hash, frozen=frozen)

    # replace attr fields by the storable properties
    for k in wrapped_fields:
        for attr in wrapped_fields[k]:
            setattr(res, attr, property(
                _attr__getter(attr), _attr__setter(attr)
            ))
            setattr(res, k, attr)
        
    return res


def _attr__getter(attr: str):
    def _wrapped__getter(self):
        wrapper: Wrapper = get_wrapper(self, attr)
        value = wrapper.__process__(self, getattr(self, attr_wrapped_field(attr)))
        to_store = wrapper.__store_process__(self, value)
        if to_store is not NO_STORE:
            setattr(self, attr_wrapped_field(attr), to_store)
        return value

    return _wrapped__getter


def _attr__setter(attr: str):
    def _wrapped__setter(self, value):
        wrapper: Wrapper = get_wrapper(self, attr)
        to_store = wrapper.__store__(self, value, getattr(self, attr_wrapped_field(attr), MISSING))
        if to_store is not NO_STORE:
            setattr(self, attr_wrapped_field(attr), to_store)
    
    return _wrapped__setter


    from dataclasses import is_dataclass, dataclass, fields, field, Field, MISSING
from smartdataclasses import wrapfield, Wrapper, WrappedField
import copy

AUTO = '_merg__auto'

def overrideable(cls=None, /, *, init=True, repr=True, eq=True, order=False,
              unsafe_hash=False, frozen=True):

    def wrap(cls):
        annotations = cls.__dict__.get('__annotations__', dict())

        for k in annotations:
            fld: Field = getattr(cls, k, None)
            if fld is None:
                setattr(cls, k, field(default=AUTO))
            elif isinstance(fld, Field):
                setattr(cls, k, field(default=fld.default, default_factory=fld.default_factory, init=True, repr=fld.repr, hash=fld.hash, compare=fld.compare, metadata=fld.metadata))
            else:
                setattr(cls, k, field(default=fld))
        
        res = dataclass(cls, init=init, repr=repr, eq=eq, order=order, unsafe_hash=unsafe_hash, frozen=frozen)

        setattr(res, '__lshift__', _override__lshift__)
        setattr(res, '__rshift__', _override__rshift__)

        return res

    # See if we're being called as @serializable or @serializable().
    if cls is None:
        # We're called with parens.
        return wrap

    # We're called as @serializable without parens.
    return wrap(cls)


def _override__rshift__(self, other):
    result = copy.deepcopy(self)
    if not is_dataclass(other) or not is_dataclass(self):
        return result
    
    flds = {}
    
    other_flds = [fld.name for fld in fields(other)]

    for fld in fields(self):
        attr = getattr(self, fld.name)
        if attr is AUTO and fld.name in other_flds:
            flds[fld.name] = getattr(other, fld.name)
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





if __name__ == '__main__':
    @overrideable
    class Over:
        a: str
        b: int
        c: int = 5

    m1 = Over(a='test')
    m2 = Over(a='hello', b=5)

    # starting from m1, if m2 has an assigned value, override it
    # i.e., m1 is the default, m2 overrides

    # m1.a (default) = 'test << m2.b = 'hello', m1.b (default) = AUTO << m2.b = 5
    print(m1 << m2)  

    # the reverse operation
    # m2.a (default) = 'hello << m1.b = 'test', m2.b (default) = 5 remains five since m1.b = AUTO (i.e., unassigned)
    print(m2 << m1)



if __name__ == '__main__':
    class PrintWrapper(Wrapper):
        def __process__(self, obj, wrapped):
            print(f'[processing] {wrapped} for {obj}')
            return wrapped
        
        def __store__(self, obj, value, currentvalue):
            if currentvalue is not MISSING:
                print(f'[storing] {value} for {obj} from {currentvalue}')
            else:
                print(f'[storing] {value} for {obj}')
            return value
    
    @wrappedclass
    class Foo:
        a: str = wrapfield(PrintWrapper(), default='hi')
    
    foo = Foo(a='hello')
    print(foo)
    print(foo.a)
    foo.a = 'oh noes'
    print(foo.a)