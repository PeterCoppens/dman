from dman.persistent.record import TemporaryContext
from dman.persistent.modelclasses import mlist, serialize, deserialize
from dman import sjson
from dman.utils import list_files
from record import TestSto

if __name__ == '__main__':
    print('\n====== list tests =======\n')
    with TemporaryContext() as ctx:
        lst = mlist([1, TestSto('a')])
        ser = serialize(lst, ctx)
        print(sjson.dumps(ser, indent=4))
        
        lst: mlist = deserialize(ser, ctx)
        print(lst)
        print(lst[1])
        print(lst)

        lst.subdir = 'test'
        lst.record(TestSto('b'), name='b', preload=True, test='value')
        ser = serialize(lst, ctx)
        print(sjson.dumps(ser, indent=4))

        print()
        list_files(ctx.path)