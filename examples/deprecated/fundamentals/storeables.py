from dataclasses import dataclass
from dman.core.storables import storable, write, read
import os

from tempfile import TemporaryDirectory

@storable(name='test')
@dataclass
class TestSto:
    value: str

@storable(name='broken')
class Broken:
    def __write__(self, path: str):
        pass

    @classmethod
    def __read__(cls, path: str):
        raise ValueError('cannot read')


if __name__ == '__main__':
    tst = TestSto(value='test')
    with TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, 'test.dat')
        write(tst, path)
        res = read(TestSto, path)
        print(res)
        
