from dman.core.serializables import BaseContext, serializable, serialize, deserialize
from dataclasses import dataclass
from typing import List, Dict
from dman.utils import sjson
from enum import Enum
from dman.core import log

if __name__ == '__main__':
    log.setLevel(log.INFO)
    @serializable
    class Mode(Enum):
        RED = 1
        BLUE = 2

    @serializable
    @dataclass
    class Test:
        a: str
        b: int
    
    @serializable
    @dataclass
    class Foo:
        a: str
        b: Test
        c: List[Test]
        d: Dict[str, Test]
    
    class Unusable:
        pass

    @serializable
    class UnusableError:
        def __serialize__(self):
            self.wrong()

        def wrong(self):
            raise ValueError('unusable')

    @serializable
    @dataclass
    class Broken:
        a: str
        b: Unusable

    class PrintContext(BaseContext):
        def error(self, msg: str):
            print(msg)

    print('basic str:', deserialize(serialize('a')))
    print('basic int:', deserialize(serialize(25)))
    print('list: ', deserialize(serialize([1, 'hello'])))
    print('dict: ', deserialize(serialize({'a': 1, 'b': 'hello'})))
    print('enum: ', deserialize(serialize(Mode.RED)))
    
    test = Test('a', 5)
    print('dataclass serialized:', serialize(test))
    print('dataclass deserialized:', deserialize(serialize(test)))

    foo = Foo('b', test, [test, test], {'a': test, 'b': test})
    print(sjson.dumps(serialize(foo), indent=4))
    print(deserialize(serialize(foo)))

    print('\n'*3)
    broken = Unusable()
    print(sjson.dumps(serialize(broken, context=PrintContext()), indent=4))

    print('\n'*3)
    broken = Broken(a='a', b=Unusable())
    res = sjson.dumps(serialize(broken, context=PrintContext()), indent=4)
    print(res)
    res = sjson.loads(res)
    res: Broken = deserialize(res)
    print(res)

    print('\n'*3)
    broken = Broken(a='a', b=UnusableError())
    res = sjson.dumps(serialize(broken, context=PrintContext()), indent=4)
    print(res)
    res = sjson.loads(res)
    res: Broken = deserialize(res)
    print(res)
    print(res.b)
