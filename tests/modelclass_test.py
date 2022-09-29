import dman
from contextlib import suppress


def test_compact():
    with suppress(TypeError):
        @dman.modelclass
        class Base:
            a: str
            b: list[str]
            
        base = Base('a', [1, 2])
        ser = dman.sjson.dumps(dman.serialize(base))
        dser = dman.deserialize(dman.sjson.loads(ser))
        assert(isinstance(dser, Base))
        assert(base == dser)

    from typing import List
    @dman.modelclass
    class Base:
        a: str
        b: List[str]
            
    base = Base('a', [1, 2])
    ser = dman.sjson.dumps(dman.serialize(base))
    dser = dman.deserialize(dman.sjson.loads(ser))
    assert(isinstance(dser, Base))
    assert(base == dser)
    
