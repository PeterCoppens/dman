import dman
from contextlib import suppress
from dman.model.modelclasses import modelclass
from dman.utils import sjson


def test_compact():
    with suppress(TypeError):
        @modelclass
        class Base:
            a: str
            b: list[str]
            
        base = Base('a', [1, 2])
        ser = sjson.dumps(dman.serialize(base))
        dser = dman.deserialize(sjson.loads(ser))
        assert(isinstance(dser, Base))
        assert(base == dser)

    from typing import List
    @modelclass
    class Base:
        a: str
        b: List[str]
            
    base = Base('a', [1, 2])
    ser = sjson.dumps(dman.serialize(base))
    dser = dman.deserialize(sjson.loads(ser))
    assert(isinstance(dser, Base))
    assert(base == dser)
    
