import copy
from dman.persistent.serializables import serialize, deserialize
from dman.persistent.modelclasses import modelclass, recordfield, serializefield
from dman.persistent.record import VerboseContext
from dman.utils.display import list_files
from tempfile import TemporaryDirectory

from record import TestSto
from dataclasses import dataclass, field

from dman.utils import sjson

@modelclass
class Other:
    a: str


@modelclass(storable=True, compact=True)
@dataclass
class Foo:
    __ext__ = '.foo'

    a: str
    e: TestSto = field()
    b: TestSto = recordfield(preload=True, repr=True)
    c: TestSto = recordfield(stem='field_c')
    # if a field is serializable and storable you can avoid storage by making it a normal field
    d: TestSto = serializefield()
    f: dict = field(default_factory=dict)


@modelclass(storable=True)
@dataclass
class Boo:
    a: Foo = recordfield(name='file.a', subdir='foo')
    b: Foo = serializefield()


if __name__ == '__main__':

    print('\n====== model class tests =======\n')
    with TemporaryDirectory() as base:
        ctx = VerboseContext(base)
        foo = Foo(a=Other('c'), b=TestSto('b'), c=TestSto('c'), d=TestSto('d'), e=TestSto('e'))
        foo.f['test'] = 'hello'
        ser = serialize(foo, ctx)
        print(sjson.dumps(ser, indent=4))

        foo: Foo = deserialize(ser, ctx)
        print(foo)
        print(foo.a)
        print(foo.b)
        print(foo.c)

        print('=== processing boo ===')
        boo = Boo(a=foo, b=copy.deepcopy(foo))
        ser = serialize(boo, ctx)
        print(sjson.dumps(ser, indent=4))

        boo: Boo = deserialize(ser, ctx)
        print(boo.a.c)
        print(boo.b.c)

        print()
        list_files(ctx.path)