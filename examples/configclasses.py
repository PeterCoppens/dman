from dman.persistent.modelclasses import modelclass, recordfield
from dman.persistent.configclasses import configclass, section
from dman.persistent.storeables import StoringConfig, storeable_type, read, StoragePlan, StoringSerializer, write

import os

BASE_DIR = os.path.join(os.path.dirname(__file__), '_configclasses')

if __name__ == '__main__':
    @modelclass(storeable=True)
    class TestModel:
        a: str = 25

    @configclass
    class TestConfig:
        @section(name='first')
        class FirstSection:
            b: int = 3
            a: str = 'wow'
        info: FirstSection     
        
        @section(name='second')
        class SecondSection:
            c: str = 'hello'
            d: TestModel = recordfield(default_factory=TestModel)
        second: SecondSection 
    
    cfg = TestConfig()
    cfg.info.a = 'yo'
    print(cfg.info.a)
    cfg2 = TestConfig()
    print(cfg2.info.a)
    with StoringSerializer(directory=BASE_DIR) as sr:
        sr.clean()
        req = sr.request(StoragePlan(filename='test.ini', preload=True))
        req.write(cfg)
        res: TestConfig = req.read(storeable_type(TestConfig))
        print(res.info.a)
        print(res.second.d)
        print(res.info.b)
        

    