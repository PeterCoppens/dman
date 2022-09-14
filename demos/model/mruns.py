from dman import mruns, context, serialize, deserialize, sjson, remove
from dman.utils.display import list_files
from record import TestSto
from tempfile import TemporaryDirectory


if __name__ == '__main__':
    print('\n====== list tests =======\n')
    with TemporaryDirectory() as base:
        ctx = context(base)
        lst = mruns([1, TestSto('a')])
        ser = serialize(lst, ctx)
        print(sjson.dumps(ser, indent=4))

        lst: mruns = deserialize(ser, ctx)
        print(lst)
        print(lst[1])
        print(lst)

        lst.subdir = 'test'
        lst.record(TestSto('b'), preload=True)
        ser = serialize(lst, ctx)
        print(sjson.dumps(ser, indent=4))

        print()
        list_files(base)

    input('\n >>> continue?')

    # removing items
    with TemporaryDirectory() as base:
        ctx = context(base)
        lst = mruns([1, TestSto('a'), 2, TestSto('b')], store_subdir=False)
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
