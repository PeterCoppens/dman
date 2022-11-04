from dman.model.modelclasses import mlist, config
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
    ref = ['a', Storable(), Serializable()]
    lst = mlist(ref)

    with temporary_context() as ctx:
        ser = serialize(lst, context=ctx)
        assert len(os.listdir(ctx.directory)) == 1
        dser: mlist = deserialize(ser, context=ctx)
        assert dser == ref
        dser.pop(1)
        assert dser == [ref[0], ref[2]]
        ser = serialize(dser, context=ctx)
        assert len(os.listdir(ctx.directory)) == 0  # file is cleaned
        dser: mlist = deserialize(ser, context=ctx)
        assert dser == [ref[0], ref[2]]

    config.auto_clean = False

    with temporary_context() as ctx:
        ser = serialize(lst, context=ctx)
        assert len(os.listdir(ctx.directory)) == 1
        dser: mlist = deserialize(ser, context=ctx)
        assert dser == ref
        dser.pop(1)
        assert dser == [ref[0], ref[2]]
        ser = serialize(dser, context=ctx)
        assert len(os.listdir(ctx.directory)) == 1  # file is not cleaned
        dser: mlist = deserialize(ser, context=ctx)
        assert dser == [ref[0], ref[2]]

    config.auto_clean = True


def test_replace():
    ref = [Storable()]
    lst = mlist(ref)

    with temporary_context() as ctx:
        ser = serialize(lst, context=ctx)
        assert len(os.listdir(ctx.directory)) == 1
        dser: mlist = deserialize(ser, context=ctx)
        assert dser == ref

        ref[0] = Storable()
        dser[0] = ref[0]
        ser = serialize(dser, context=ctx)
        assert len(os.listdir(ctx.directory)) == 1
        dser: mlist = deserialize(ser, context=ctx)
        assert dser == ref

        ref[0] = 'a'
        dser[0] = ref[0]
        ser = serialize(dser, context=ctx)
        assert len(os.listdir(ctx.directory)) == 0
        dser: mlist = deserialize(ser, context=ctx)
        assert dser == ref

    config.auto_clean = False
    ref = [Storable()]
    lst = mlist(ref)

    with temporary_context() as ctx:
        ser = serialize(lst, context=ctx)
        assert len(os.listdir(ctx.directory)) == 1
        dser: mlist = deserialize(ser, context=ctx)
        assert dser == ref

        ref[0] = Storable()
        dser[0] = ref[0]
        ser = serialize(dser, context=ctx)
        assert len(os.listdir(ctx.directory)) == 1  # recycling records still happens
        dser: mlist = deserialize(ser, context=ctx)
        assert dser == ref

        ref[0] = 'a'
        dser[0] = ref[0]
        ser = serialize(dser, context=ctx)
        assert len(os.listdir(ctx.directory)) == 1
        dser: mlist = deserialize(ser, context=ctx)
        assert dser == ref

    config.auto_clean = True

