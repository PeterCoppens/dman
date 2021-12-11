import os
from dman.persistent.modelclasses import modelclass
from dman.repository import Repository, persistent
from dman.persistent.record import record, remove, serialize
from dman.persistent.serializables import deserialize
from example_record import TestSto


@persistent(name='tst.txt')
@modelclass(name='persistent', storeable=True)
class TestPersistent:
    a: str


if __name__ == '__main__':
    with Repository() as repo:
        rec = record(TestSto(name='hello'), name='test.txt', gitignore=True)
        ser = serialize(rec, repo.cache.join('examples'))
        test = deserialize(ser, repo.cache.join('examples')).content
        print(test)

        repo.cache.clear()

    with TestPersistent(a='5') as t:
        print(t)

    with TestPersistent(a='25') as t:
        print(t)
    
    input()
    remove(TestPersistent())