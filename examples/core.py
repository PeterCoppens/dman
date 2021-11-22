from dman.core import Repository, modelclass
from dman.persistent.storeables import StoringConfig

@modelclass(storeable=True)
class Test:
    a: str

if __name__ == '__main__':
    with Repository.load() as repo:
        with repo.cachedir(
            'temp', 
            config=StoringConfig(store_on_close=True)
        ) as wdir:
            print(wdir.config)
            wdir.clean()
            fn1 = wdir.store(Test(a='hello'))
            print(wdir.load(Test, fn1))
            fn2 = wdir.store(Test(a='dat'), filename='test.dat')
            print(wdir.load(Test, fn2))
