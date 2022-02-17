from typing import Any
import pytest


from dman import serializable, serialize, deserialize, sjson, dataclass, isvalid
from dman.persistent.serializables import SER_TYPE, SER_CONTENT, ExcUndeserializable, Undeserializable, Unserializable


atomics = [
    'hello world',
    5,
    2.3,
    True,
    None
]


collections = [
    ([1, 2, 3], [1, 2, 3]),
    ((1, 2, 3), [1, 2, 3]),
    ({'a': 'a', 'b': 3, 5: 6}, {'a': 'a', 'b': 3, '5': 6})
]


def recreate(arg):
    serialized = serialize(arg)
    serialized = sjson.dumps(serialized)
    serialized = sjson.loads(serialized)
    return deserialize(serialized)


def recreate_compact(arg):
    serialized = serialize(arg, content_only=True)
    serialized = sjson.dumps(serialized)
    serialized = sjson.loads(serialized)
    return deserialize(serialized, ser_type=type(arg))


@pytest.mark.parametrize('arg', atomics)
def test_atomics(arg):
    assert(arg == recreate(arg))
    assert(arg == recreate_compact(arg))


@pytest.mark.parametrize('arg', collections)
def test_collections(arg):
    value, expected = arg
    assert(expected == recreate(value))
    assert(expected == recreate_compact(value))


class Manual:
    def __init__(self, value):
        self.value = value

    def __serialize__(self):
        return self.value

    @classmethod
    def __deserialize__(cls, serialized):
        return cls(serialized)
    
    def __eq__(self, other):
        if not isinstance(other, Manual):
            return False
        return other.value == self.value


@dataclass
class Dataclass:
    value: str


@pytest.mark.parametrize('arg', [Manual, Dataclass])
def test_basic_classes(arg):
    cls = serializable(arg, name='__manual')
    def make(val: str = 'test'):
        return cls(value=val)

    res = recreate(make())
    assert(isinstance(res, arg))
    assert(res.value == make().value)

    res = recreate_compact(make())
    assert(isinstance(res, arg))
    assert(res.value == make().value)

    lst = [make(), make(val='b')]
    tpl = (make(val='c'), make(val='d'))
    dct = {'a': make(val='r'), 'b': make(val='g')}
    assert(lst == recreate(lst))
    assert(dct == recreate(dct))
    assert(list(tpl) == recreate(tpl))
    
    assert(lst == recreate_compact(lst))
    assert(dct == recreate_compact(dct))
    assert(list(tpl) == recreate_compact(tpl))


@dataclass
class Complex:
    str_test: str
    int_test: int
    float_test: float
    bool_test: bool
    none_test: Any
    list_test: list
    tuple_test: tuple
    dict_test: dict


@pytest.mark.parametrize('arg', [Complex])
@pytest.mark.parametrize('at', [atomics])
@pytest.mark.parametrize('col', [collections])
def test_complex_class(arg, at, col):
    cls = serializable(arg, name='__complex')
    def make():
        return cls(
            *at, *[a for a, _ in col]
        )

    def compare():
        return cls(
            *at, *[b for _, b in col]
        )

    res = recreate(make())
    assert(compare() == res)

    res = recreate_compact(make())
    assert(compare() == res)


@pytest.mark.parametrize('base', [Dataclass])
def test_nested_class(base):
    cls = serializable(base, name='__complex')
    @serializable(name='__nested')
    @dataclass
    class Nested:
        ser: cls
        lst: list
        dct: dict

    lst = [cls(value='test'), 'a']
    dct = {'a': cls(value='test'), 'b': lst}
    
    nested = Nested(
        ser = cls(value='test'),
        lst = [
            cls(value='test'), lst, dct 
        ],
        dct= {
            'a': cls(value='test'),
            'b': lst,
            'c': dct
        }
    )

    res = recreate(nested)
    assert(nested == res)

    res = recreate_compact(nested)
    assert(nested == res)


def test_fail_serialize_object():
    class NotRegistred: ...

    res = serialize(NotRegistred())
    assert(not isvalid(res))

    @serializable
    class InvalidSignature:
        def __serialize__(self, a: str, b: str, c: str):
            print(a, b, c)

    res = serialize(InvalidSignature())
    assert(not isvalid(res))

    @serializable
    class ErrorSerialize:
        def __serialize__(self):
            raise Exception('error')
    res = serialize(ErrorSerialize())
    assert(not isvalid(res))


def test_fail_deserialize():
    @serializable(name='__base')
    @dataclass
    class Base:
        a: str = 'test'

    serialized_incorrect = {
        SER_TYPE: '__base',
        SER_CONTENT: {'b': 25}
    }

    res = deserialize(serialized_incorrect)
    assert(isinstance(res, ExcUndeserializable))

    serialized = {
        SER_TYPE: '__base',
        SER_CONTENT: {'a': 'hello'}
    }
    
    res = deserialize(serialized, ser_type=str)
    assert(isinstance(res, Undeserializable))

    serialized = {
        SER_TYPE: '__base',
        SER_CONTENT: {'a': serialized_incorrect}
    }

    res: Base = deserialize(serialized)
    assert(isinstance(res.a, ExcUndeserializable))

    res = deserialize(serialized_incorrect)
    assert(isinstance(res, ExcUndeserializable))

    serialized_re = serialize(res)

    @serializable(name='__base')
    @dataclass
    class Base:
        a: str = 'test'
        b: str = None
    
    res = deserialize(serialized_re)
    assert(isinstance(res, Base))


