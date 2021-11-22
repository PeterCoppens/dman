from dman.persistent.storeables import storeable, storeable_type, write, read
import os

from pathlib import Path

BASE_DIR = Path(__file__).joinpath('_storeables')

@storeable(name='test')
class TestSto:
    def __write__(self, path: str):
        print(f'writing {os.path.basename(path)}')
    
    @classmethod
    def __read__(cls, path: str):
        print(f'reading {os.path.basename(path)}')

if __name__ == '__main__':
    tst = TestSto()
    write(tst, BASE_DIR.joinpath('test.dat'))
    read(storeable_type(TestSto), BASE_DIR.joinpath('test.dat'))


