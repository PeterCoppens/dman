import copy
from dman.core.serializables import serialize, deserialize
from dman.model.modelclasses import modelclass, recordfield, serializefield
from dman.model.record import Context
from dman import tui
from dman import log
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
    


@modelclass(compact=True)
@dataclass
class Coo:
    a: str
    b: str = 'hello'

    def __serialize__(self):
        res= {'a': self.a}
        if self.b != 'hello':
            res['b'] = self.b
        return res


@modelclass
@dataclass
class Doo:
    a: Boo
    b: Boo
            


if __name__ == '__main__':

    print('\n====== model class tests =======\n')
    with TemporaryDirectory() as base:
        ctx = Context.from_directory(base)
        foo = Foo(a=Other('c'), b=TestSto('b'), c=TestSto('c'), d=TestSto('d'), e=TestSto('e'))
        foo.f['test'] = 'hello'
        ser = serialize(foo, ctx)
        log.info(sjson.dumps(ser, indent=4))

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
        tui.walk_directory(ctx.directory)

        coo = Coo(a='test')
        ser = serialize(coo, ctx)
        print(sjson.dumps(ser, indent=4))
        coo: Coo = deserialize(ser, ctx)
        print(coo.b)

        doo = Doo(
            a=Boo(a=foo, b=copy.deepcopy(foo)), 
            b=Boo(a=foo, b=copy.deepcopy(foo))
        )
        ser = serialize(doo, ctx)
        print(sjson.dumps(ser, indent=4))
        doo: Doo = deserialize(ser, ctx)
        print(doo.a)