import copy
from dman.persistent.serializables import SER_CONTENT, SER_TYPE, serialize, deserialize
from dman.persistent.modelclasses import modelclass, mlist,  mdict, smdict, recordfield
from dman.persistent.record import TemporaryContext
from dman.persistent.storeables import _read__serializable, _write__serializable, storeable

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
        _write__serializable(self, path, context)

    @classmethod
    def __read__(cls, path, context):
        print(f'..writing foo to {path}')
        with open(path, 'r') as f:
            serialized = {SER_TYPE: getattr(cls, SER_TYPE), SER_CONTENT: json.load(f)}
            return deserialize(serialized, context)

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
    


        

    # lst = mlist([1, 2, 3, Test('a'), Test('b')])
    # ser = serialize(lst, ctx)
    # print(json.dumps(ser, indent=4))
    # lst_re = deserialize(ser, ctx)
    # print(lst_re)
    # print(lst_re[-1])

    # dct = mdict(a=5, b=3, c=Test('c'), d=Test('d'))
    # ser2 = serialize(dct, sr)
    # print(json.dumps(ser2, indent=4))
    # dct_re = deserialize(ser2, sr)
    # print(dct_re)
    # print(dct_re['c'])

    # dct2 = smdict(**dct)
    # rec0 = serialize(record(dct2, plan=StoragePlan(subdir='third', config=StoringConfig(gitkeep=False, store_on_close=True))), sr) # content_d4993d5c-75e8-4607-91ef-b47d6fec60e9
    # print(json.dumps(rec0, indent=4))
    # print(deserialize(rec0, sr).content)
            
    
    

    # with StoringSerializer(BASE_DIR) as srmain:
    #     srmain.clean()
    #     with srmain.subdirectory('first', config=StoringConfig(gitkeep=True)) as sr:
    #         lst = mlist([1, 2, 3, Test('a'), Test('b')], plan=StoragePlan(preload=True))
    #         ser = serialize(lst, sr)
    #         print(json.dumps(ser, indent=4))
    #         lst_re = deserialize(ser, sr)
    #         print(lst_re)
    #         print(lst_re[-1])

    #         dct = mdict(a=5, b=3, c=Test('c'), d=Test('d'), plan=StoragePlan(preload=True))
    #         ser2 = serialize(dct, sr)
    #         print(json.dumps(ser2, indent=4))
    #         dct_re = deserialize(ser2, sr)
    #         print(dct_re)
    #         print(dct_re['c'])

    #         dct2 = smdict(**dct)
    #         rec0 = serialize(record(dct2, plan=StoragePlan(subdir='third', config=StoringConfig(gitkeep=False, store_on_close=True))), sr) # content_d4993d5c-75e8-4607-91ef-b47d6fec60e9
    #         print(json.dumps(rec0, indent=4))
    #         print(deserialize(rec0, sr).content)
            
    #     import numpy as np

    #     @storeable(name='_tst__array')
    #     class Array(np.ndarray):
    #         def __write__(self, path):
    #             with open(path, 'wb') as f:
    #                 np.save(f, self)
            
    #         @classmethod
    #         def __read__(self, path):
    #             with open(path, 'rb') as f:
    #                 return np.load(f).view(Array)


    #     @modelclass(storeable=True)
    #     class Foo:
    #         a: str
    #         b: Test = recordfield(plan=StoragePlan(preload=True))
    #         c: Array  # = recordfield() is automatically added for storeables
    #         d: Test = field()  # if a field is serializable and storeable you can avoid storage by making it a normal field
        
    #     rec1 = record(Test('hello'), plan=StoragePlan(preload=False, ignored=False))

    #     with srmain.subdirectory('second', config=StoringConfig(store_on_close=True)) as sr:
    #         ser0 = serialize(rec1, sr) 

    #         print(json.dumps(ser0, indent=4))
    #         res1: Record = deserialize(ser0, sr)
    #         print(res1)
    #         print(res1.content)

    #         foo = Foo('hello', Test('you'), np.eye(4).view(Array), Test('donotstore'))
    #         print(foo.b)
    #         print(foo.c)
    #         ser = serialize(foo, sr)
    #         print(json.dumps(ser, indent=4))

    #         res2: Foo = deserialize(ser, sr)
    #         print(res2)
    #         print(res2.b)
    #         print(res2.c)

    #         rec2 = record(foo, plan=StoragePlan(filename='foo.json'))
    #         ser2 = serialize(rec2, sr)
    #         print(ser2)
    #         res3: Record = deserialize(ser2, sr)
    #         print('final')
    #         print(res3.content)

    #         cnt: Foo = res3.content
    #         print(cnt.b)
    #         print(cnt.c)

    # with StoringSerializer.from_path(os.path.join(BASE_DIR, 'second/serializer.json')) as sr:
    #     print(sr.directory)