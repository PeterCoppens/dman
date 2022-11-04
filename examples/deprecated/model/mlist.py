from tempfile import TemporaryDirectory
from dman.model.record import Context, context, remove
from dman.model.modelclasses import mlist, serialize, deserialize
from dman.utils import sjson
from dman import tui
from record import TestSto

if __name__ == '__main__':
    print('\n====== list tests =======\n')
    with TemporaryDirectory() as base:
        ctx = context(base, verbose=True)
        lst = mlist([1, TestSto('a')])
        ser = serialize(lst, ctx)
        print(sjson.dumps(ser, indent=4))
        
        lst: mlist = deserialize(ser, ctx)
        print(lst)
        print(lst[1])
        print(lst)

        lst.subdir = 'test'
        lst.record(TestSto('b'), name='b', preload=True)
        ser = serialize(lst, ctx)
        print(sjson.dumps(ser, indent=4))

        print()
        tui.walk_directory(base)
    
    input('\n >>> continue?')

    # removing items
    with TemporaryDirectory() as base:
        ctx = context(base, verbose=True)
        lst = mlist([1, TestSto('a'), 2, TestSto('b')])
        lst.record(TestSto(name='hello'))
        ser = serialize(lst, ctx)
        print(sjson.dumps(ser, indent=4))
        tui.walk_directory(base)

        print(lst.pop())
        print(lst.pop())
        ser = serialize(lst, ctx)
        print('popped:')
        print(sjson.dumps(ser, indent=4))
        tui.walk_directory(base)

        print('removed:')
        remove(lst, ctx)
        tui.walk_directory(base)

