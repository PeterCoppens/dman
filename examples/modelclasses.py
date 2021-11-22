from dman.persistent.context import ContextCommand, RootContext, clear
from dman.persistent.serializables import serialize, deserialize
from dman.persistent.modelclasses import modelclass, mlist,  mdict, smdict, recordfield

from dataclasses import field

import json
import os

rt = RootContext.at_script().joinpath('_modelclasses')

if __name__ == '__main__':
    clear(rt)

    @modelclass(name='_tst__test', storeable=True)
    class Test:
        value: str

    ctx = rt.joinpath('first')
    ctx.resolve().mkdir()

    lst = mlist([1, 2, 3, Test('a'), Test('b')])
    ser = serialize(lst, ctx)
    print(json.dumps(ser, indent=4))
    lst_re = deserialize(ser, ctx)
    print(lst_re)
    print(lst_re[-1])

    dct = mdict(a=5, b=3, c=Test('c'), d=Test('d'))
    ser2 = serialize(dct, sr)
    print(json.dumps(ser2, indent=4))
    dct_re = deserialize(ser2, sr)
    print(dct_re)
    print(dct_re['c'])

    dct2 = smdict(**dct)
    rec0 = serialize(record(dct2, plan=StoragePlan(subdir='third', config=StoringConfig(gitkeep=False, store_on_close=True))), sr) # content_d4993d5c-75e8-4607-91ef-b47d6fec60e9
    print(json.dumps(rec0, indent=4))
    print(deserialize(rec0, sr).content)
            
    
    

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