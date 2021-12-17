from dman.persistent.serializables import BaseContext, serializable, serialize, deserialize
from dataclasses import dataclass
from typing import List, Dict, Tuple
from dman.utils import sjson

if __name__ == '__main__':
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
        e: Tuple[Test]
    
    class Unusable:
        pass

    @serializable
    class UnusableError:
        def __serialize__(self):
            raise ValueError('unusable')

    @serializable
    @dataclass
    class Broken:
        a: str
        b: Unusable

    class PrintContext(BaseContext):
        def error(self, msg: str):
            print('error:')
            print(msg)
    
    test = Test('a', 5)
    print(serialize(test))
    print(deserialize(serialize(test)))

    foo = Foo('b', test, [test, test], {'a': test, 'b': test}, (test, test))
    print(sjson.dumps(serialize(foo), indent=4))
    print(deserialize(serialize(foo)))

    broken = Unusable()
    print(serialize(broken, context=PrintContext()))

    broken = Broken(a='a', b=Unusable())
    res = sjson.dumps(serialize(broken, context=PrintContext()), indent=4)
    print(res)
    res = sjson.loads(res)
    res: Broken = deserialize(res)
    print(res)

    broken = Broken(a='a', b=UnusableError())
    res = sjson.dumps(serialize(broken, context=PrintContext()), indent=4)
    print(res)
    res = sjson.loads(res)
    res: Broken = deserialize(res)
    print(res)