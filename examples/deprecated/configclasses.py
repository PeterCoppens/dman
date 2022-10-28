from dataclasses import field
from tempfile import TemporaryDirectory
from dman import tui
from dman.model.modelclasses import modelclass, recordfield
from dman.model.configclasses import configclass, section
from dman.core.storables import read, write
from dman.model.record import Context
import os


if __name__ == '__main__':
    @modelclass(storable=True)
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


    with TemporaryDirectory() as base:
        ctx = Context(base)
        target = os.path.join(ctx.subdir, 'test.ini')
        write(cfg, target, ctx)
        tui.walk_directory(ctx.subdir)

        res: TestConfig = read(TestConfig, target, ctx)
        print(res.info.a)
        print(''.join(res.info.c))
        print(res.second.d)
        print(res.info.b)
        

    