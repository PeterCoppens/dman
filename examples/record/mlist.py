from tempfile import TemporaryDirectory
from dman.persistent.record import Context, remove
from dman.persistent.modelclasses import mlist, serialize, deserialize
from dman.utils import sjson
from dman.utils.display import list_files
from record import TestSto

if __name__ == '__main__':
    print('\n====== list tests =======\n')
    with TemporaryDirectory() as base:
        ctx = Context(base)
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
        list_files(base)
    
    input('\n >>> continue?')

    # removing items
    with TemporaryDirectory() as base:
        ctx = Context(base)
        lst = mlist([1, TestSto('a'), 2, TestSto('b')])
        lst.record(TestSto(name='hello'))
        ser = serialize(lst, ctx)
        print(sjson.dumps(ser, indent=4))
        list_files(base)

        print(lst.pop())
        print(lst.pop())
        ser = serialize(lst, ctx)
        print('popped:')
        print(sjson.dumps(ser, indent=4))
        list_files(base)

        print('removed:')
        remove(lst, ctx)
        list_files(base)

