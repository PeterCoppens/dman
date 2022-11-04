from dman.model.modelclasses import mdict, config
from dman.core.storables import storable
from dman.core.serializables import serializable, serialize, deserialize
from uuid import uuid4

from record_test import temporary_context
import os


class Item:
    def __init__(self, value: str = None):
        self.value = str(uuid4()) if value is None else value
    
    def __eq__(self, other):
        if not isinstance(other, Item):
            return False
        return self.value == other.value

@storable
class Storable(Item):
    def __write__(self, path: str):
        with open(path, 'w') as f:
            f.write(self.value)
    
    @classmethod
    def __read__(cls, path: str):
        with open(path, 'r') as f:
            return cls(f.read())


@serializable
class Serializable(Item):
    def __serialize__(self):
        return self.value
    
    @classmethod
    def __deserialize__(cls, sto: str):
        return cls(sto)
    

def test_basic():
    ref = {'k1': 'a', 'k2': Storable(), 'k3': Serializable()}
    dct = mdict.from_dict(ref)

    with temporary_context() as ctx:
        ser = serialize(dct, context=ctx)
        assert len(os.listdir(ctx.directory)) == 1
        dser: mdict = deserialize(ser, context=ctx)
        assert dser == ref
        dser.pop('k2')
        assert dser == {'k1': 'a', 'k3': ref['k3']}
        ser = serialize(dser, context=ctx)
        assert len(os.listdir(ctx.directory)) == 0  # file is cleaned
        dser: mdict = deserialize(ser, context=ctx)
        assert dser == {'k1': 'a', 'k3': ref['k3']}

    config.auto_clean = False

    with temporary_context() as ctx:
        ser = serialize(dct, context=ctx)
        assert len(os.listdir(ctx.directory)) == 1
        dser: mdict = deserialize(ser, context=ctx)
        assert dser == ref
        dser.pop('k2')
        assert dser == {'k1': 'a', 'k3': ref['k3']}
        ser = serialize(dser, context=ctx)
        assert len(os.listdir(ctx.directory)) == 1  # file is not cleaned
        dser: mdict = deserialize(ser, context=ctx)
        assert dser == {'k1': 'a', 'k3': ref['k3']}

    config.auto_clean = True


def test_replace():
    ref = {'k': Storable()}
    lst = mdict.from_dict(ref)

    with temporary_context() as ctx:
        ser = serialize(lst, context=ctx)
        assert len(os.listdir(ctx.directory)) == 1
        dser: mdict = deserialize(ser, context=ctx)
        assert dser == ref

        ref['k'] = Storable()
        dser['k'] = ref['k']
        ser = serialize(dser, context=ctx)
        assert len(os.listdir(ctx.directory)) == 1
        dser: mdict = deserialize(ser, context=ctx)
        assert dser == ref

        ref['k'] = 'a'
        dser['k'] = ref['k']
        ser = serialize(dser, context=ctx)
        assert len(os.listdir(ctx.directory)) == 0
        dser: mdict = deserialize(ser, context=ctx)
        assert dser == ref

    config.auto_clean = False
    ref = {'k': Storable()}
    lst = mdict.from_dict(ref)

    with temporary_context() as ctx:
        ser = serialize(lst, context=ctx)
        assert len(os.listdir(ctx.directory)) == 1
        dser: mdict = deserialize(ser, context=ctx)
        assert dser == ref

        ref['k'] = Storable()
        dser['k'] = ref['k']
        ser = serialize(dser, context=ctx)
        assert len(os.listdir(ctx.directory)) == 1  # recycling records still happens
        dser: mdict = deserialize(ser, context=ctx)
        assert dser == ref

        ref['k'] = 'a'
        dser['k'] = ref['k']
        ser = serialize(dser, context=ctx)
        assert len(os.listdir(ctx.directory)) == 1
        dser: mdict = deserialize(ser, context=ctx)
        assert dser == ref

    config.auto_clean = True

