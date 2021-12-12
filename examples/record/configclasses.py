from dataclasses import field
from dman.persistent.modelclasses import modelclass, recordfield
from dman.persistent.configclasses import configclass, section
from dman.persistent.storeables import read, write
from dman.persistent.record import TemporaryContext
from dman.utils import list_files

import os


if __name__ == '__main__':
    @modelclass(storeable=True)
    class TestModel:
        a: str = 25

    @configclass
    class TestConfig:
        @section
        class FirstSection:
            b: int = 3
            a: str = 'wow'
            c: list = field(default_factory=list)
        info: FirstSection     
        
        @section
        class SecondSection:
            c: str = 'hello'
            d: TestModel = recordfield(default_factory=TestModel)
        second: SecondSection 
    
    cfg = TestConfig()
    cfg.info.a = 'yo'
    cfg.info.c = ['h','e','l','l','o']
    print(cfg.info.a)
    cfg2 = TestConfig()
    print(cfg2.info.a)


    with TemporaryContext() as ctx:
        target = os.path.join(ctx.path, 'test.ini')
        write(cfg, target, ctx)
        list_files(ctx.path)

        res: TestConfig = read(TestConfig, target, ctx)
        print(res.info.a)
        print(''.join(res.info.c))
        print(res.second.d)
        print(res.info.b)
        

    