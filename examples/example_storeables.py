from dataclasses import dataclass
from dman.persistent.storeables import storeable, write, read
import os

from tempfile import TemporaryDirectory


@storeable(name='test')
@dataclass
class TestSto:
    value: str


if __name__ == '__main__':
    tst = TestSto(value='test')
    with TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, 'test.dat')
        write(tst, path)
        res = read(TestSto, path)
        print(res)
