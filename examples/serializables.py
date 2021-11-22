from dman.persistent.serializables import serializable, serialize, deserialize
from dataclasses import dataclass
from typing import List, Dict, Tuple
import json

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
    
    test = Test('a', 5)
    print(serialize(test))

    foo = Foo('b', test, [test, test], {'a': test, 'b': test}, (test, test))
    print(json.dumps(serialize(foo), indent=4))
    
    print(deserialize(serialize(foo)))