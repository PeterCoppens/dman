from dman.persistent.record import TemporaryContext
from dman.persistent.modelclasses import mdict, serialize, deserialize
from dman import sjson
from dman.utils import list_files
from record import TestSto

if __name__ == '__main__':
    print('\n====== dict tests =======\n')
    with TemporaryContext() as ctx:
        dct = mdict(a=5, b=TestSto('b'), c=TestSto('c'))
        ser = serialize(dct, ctx)
        print(sjson.dumps(ser, indent=4))

        dct: mdict = deserialize(ser, ctx)
        print(dct)
        print(dct['b'])
        print(dct['c'])
        print(dct)

        dct.store_by_key()
        dct.subdir = 'dct'
        dct.record('d', TestSto('d'), name='hello', subdir='test')
        ser = serialize(dct, ctx)
        print(sjson.dumps(ser, indent=4))

        dct: mdict = deserialize(ser, ctx)
        print(dct['b'])
        print(dct['c'])
        print(dct)

        print()
        list_files(ctx.path)
