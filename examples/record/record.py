from dman.persistent.record import Record, record, TemporaryContext
from dman.persistent.serializables import serializable, serialize, deserialize
from dman.persistent.storeables import storeable

from dman import sjson
from dman.utils import list_files

@storeable
@serializable
class TestSto:
    __ext__ = '.tst'

    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return f'TestSto({self.name})'

    def __serialize__(self):
        return {'name': self.name}

    @classmethod
    def __deserialize__(cls, ser):
        return cls(**ser)

    def __write__(self, path):
        print(f'[teststo] writing to path {path}')
        with open(path, 'w') as f:
            f.write(self.name)

    @classmethod
    def __read__(cls, path):
        print(f'[teststo] reading from path {path}')
        with open(path, 'r') as f:
            return cls(f.read())


if __name__ == '__main__':
    with TemporaryContext() as ctx:
        rec = record(TestSto(name='hello'), preload=False)
        ser = serialize(rec, ctx)
        print('== first serialization ==')
        print(sjson.dumps(ser, indent=4))

        rec: Record = deserialize(ser, ctx)
        ser = serialize(rec, ctx)
        print('== second serialization ==')
        print(sjson.dumps(ser, indent=4))

        rec: Record = deserialize(ser, ctx)
        print('content: ', rec.content)
        ser = serialize(rec, ctx)
        print('== third serialization ==')
        print(sjson.dumps(ser, indent=4))

        print()
        list_files(ctx.path)

    with TemporaryContext() as ctx:
        rec = record(TestSto(name='test'), preload=True, subdir='test')
        ser = serialize(rec, ctx)
        print(sjson.dumps(ser, indent=4))

        rec = deserialize(ser, ctx)
        print(rec.content)

        print()
        list_files(ctx.path)
