import os
from tempfile import TemporaryDirectory
from dman.model.modelclasses import mdict, serialize, deserialize
from dman.utils import sjson
from dman.model.record import Context, remove
from dman import tui
from record import TestSto

if __name__ == '__main__':
    print('\n====== dict tests =======\n')
    with TemporaryDirectory() as base:
        ctx = Context(base)
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
        tui.walk_directory(ctx.directory)

    input('\n >>> continue?')

    # removing items
    with TemporaryDirectory() as base:
        ctx = Context(base)
        dct = mdict(a=5, b=TestSto('b'), c=TestSto('c'), d=TestSto('d'), e='hello')
        ser = serialize(dct, ctx)
        print(sjson.dumps(ser, indent=4))
        tui.walk_directory(ctx.directory)

        print('==== delete items === ')
        print(dct.pop('d'))
        print(dct.pop('e'))
        ser = serialize(dct, ctx)
        print(sjson.dumps(ser, indent=4))
        tui.walk_directory(ctx.directory)

        print('==== delete dictionary === ')
        remove(dct, ctx)
        tui.walk_directory(ctx.directory)

    input('\n >>> continue?')

    # removing items
    with TemporaryDirectory() as base:
        ctx = Context(base)
        dct = mdict(subdir='stamps', store_by_key=True, auto_clean=True)
        dct['test'] = TestSto(name='hello')
        dct.record('other', TestSto(name='other'))
        ser = serialize(dct, ctx)
        print(sjson.dumps(ser, indent=4))

        print('remove test.tst ...')
        os.remove(os.path.join(base, 'stamps', 'test.tst'))
        tui.walk_directory(ctx.directory)

        dct = deserialize(ser, ctx)
        print('after de-serialization:\n', dct.get('test', None))
        ser = serialize(dct, ctx)
        dct = deserialize(ser, ctx)
        print('after re-serialization:\n', dct.get('test', None))
        


