import os
from tempfile import TemporaryDirectory
from dman.persistent.modelclasses import mdict, serialize, deserialize
from dman.utils import sjson
from dman.persistent.record import RecordContext, remove
from dman.utils.display import list_files
from record import TestSto

if __name__ == '__main__':
    print('\n====== dict tests =======\n')
    with TemporaryDirectory() as base:
        ctx = RecordContext(base)
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

    input('\n >>> continue?')

    # removing items
    with TemporaryDirectory() as base:
        ctx = RecordContext(base)
        dct = mdict(a=5, b=TestSto('b'), c=TestSto('c'), d=TestSto('d'), e='hello')
        ser = serialize(dct, ctx)
        print(sjson.dumps(ser, indent=4))
        list_files(ctx.path)

        print('==== delete items === ')
        print(dct.pop('d'))
        print(dct.pop('e'))
        ser = serialize(dct, ctx)
        print(sjson.dumps(ser, indent=4))
        list_files(ctx.path)

        print('==== delete dictionary === ')
        remove(dct, ctx)
        list_files(ctx.path)

    input('\n >>> continue?')

    # removing items
    with TemporaryDirectory() as base:
        ctx = RecordContext(base)
        dct = mdict(subdir='stamps', store_by_key=True)
        dct['test'] = TestSto(name='hello')
        dct.record('other', TestSto(name='other'))
        ser = serialize(dct, ctx)
        print(sjson.dumps(ser, indent=4))

        print('remove test.tst ...')
        os.remove(os.path.join(base, 'stamps', 'test.tst'))
        list_files(ctx.path)

        dct = deserialize(ser, ctx)
        print('after de-serialization: ', repr(dct.get('test', None)))
        ser = serialize(dct, ctx)
        dct = deserialize(ser, ctx)
        print('after re-serialization: ', repr(dct.get('test', None)))
        


