import copy
from dman.persistent.serializables import serialize, deserialize
from dman.persistent.modelclasses import modelclass, recordfield
from dman.persistent.record import RecordContext
from dman.utils.display import list_files
from tempfile import TemporaryDirectory

from record import TestSto
from dataclasses import field

from dman.utils import sjson


@modelclass(storeable=True, compact=True)
class Foo:
    __ext__ = '.foo'

    a: str
    b: TestSto = recordfield(preload=True, repr=True)
    c: TestSto = recordfield(stem='field_c')
    # if a field is serializable and storeable you can avoid storage by making it a normal field
    d: TestSto = field()

    def __write__(self, path, context):
        print(f'..writing foo to {path}')
        with open(path, 'w') as f:
            sjson.dump(serialize(self, context, content_only=True), f, indent=4)

    @classmethod
    def __read__(cls, path, context):
        print(f'..writing foo to {path}')
        with open(path, 'r') as f:
            return deserialize(sjson.load(f), context, ser_type=cls)


@modelclass(storeable=True)
class Boo:
    a: Foo = recordfield(name='file.a', subdir='foo')
    b: Foo = field()


if __name__ == '__main__':

    print('\n====== model class tests =======\n')
    with TemporaryDirectory() as base:
        ctx = RecordContext(base)
        foo = Foo(a='a', b=TestSto('b'), c=TestSto('c'), d=TestSto('d'))
        ser = serialize(foo, ctx)
        print(sjson.dumps(ser, indent=4))

        foo: Foo = deserialize(ser, ctx)
        print(foo)
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