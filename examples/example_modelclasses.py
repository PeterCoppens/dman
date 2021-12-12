import copy
from dman.persistent.serializables import serialize, deserialize
from dman.persistent.modelclasses import modelclass, mlist,  mdict, recordfield
from dman.persistent.record import TemporaryContext

from example_record import TestSto

from dataclasses import field

import json
    
@modelclass(storeable=True)
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
            json.dump(serialize(self, context, content_only=True), f, indent=4)

    @classmethod
    def __read__(cls, path, context):
        print(f'..writing foo to {path}')
        with open(path, 'r') as f:
            return deserialize(json.load(f), context, ser_type=cls)

@modelclass(storeable=True)
class Boo:
    a: Foo = recordfield(name='file.a', subdir='foo')
    b: Foo = field()

if __name__ == '__main__':
    print('\n====== list tests =======\n')
    with TemporaryContext() as ctx:
        lst = mlist([1, TestSto('a')])
        ser = serialize(lst, ctx)
        print(json.dumps(ser, indent=4))
        
        lst: mlist = deserialize(ser, ctx)
        print(lst)
        print(lst[1])
        print(lst)

        lst.subdir = 'test'
        lst.record(TestSto('b'), name='b', preload=True, test='value')
        ser = serialize(lst, ctx)
        print(json.dumps(ser, indent=4))
    
    print('\n====== dict tests =======\n')
    with TemporaryContext() as ctx:
        dct = mdict(a=5, b=TestSto('b'), c=TestSto('c'))
        ser = serialize(dct, ctx)
        print(json.dumps(ser, indent=4))

        dct: mdict = deserialize(ser, ctx)
        print(dct)
        print(dct['b'])
        print(dct['c'])
        print(dct)

        dct.store_by_key()
        dct.subdir = 'dct'
        dct.record('d', TestSto('d'), name='hello', subdir = 'test')
        ser = serialize(dct, ctx)
        print(json.dumps(ser, indent=4))
        
        dct: mdict = deserialize(ser, ctx)
        print(dct['b'])
        print(dct['c'])
        print(dct)

    print('\n====== model class tests =======\n')
    with TemporaryContext() as ctx:
        foo = Foo(a='a', b=TestSto('b'), c=TestSto('c'), d=TestSto('d'))
        ser = serialize(foo, ctx)
        print(json.dumps(ser, indent=4))

        foo: Foo = deserialize(ser, ctx)
        print(foo)
        print(foo.b)
        print(foo.c)

        print('=== processing boo ===')
        boo = Boo(a=foo, b=copy.deepcopy(foo))
        ser = serialize(boo, ctx)
        print(json.dumps(ser, indent=4))

        boo: Boo = deserialize(ser, ctx)
        print(boo.a.c)
        print(boo.b.c)