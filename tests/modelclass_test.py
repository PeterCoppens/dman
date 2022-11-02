import dman
from contextlib import suppress
from dman.model.modelclasses import (
    modelclass,
    serializefield,
    recordfield,
)
from dataclasses import dataclass
from dman.core.storables import storable
from dman.core.serializables import serializable
from dman.utils import sjson
from record_test import temporary_context
import os


def test_basic():
    @modelclass
    class Base:
        a: str = "a"
        b: int = 1
        c: float = 0.5
        d: bool = True

    base = Base("b", 3, 0.2, False)
    ser = dman.serialize(base)
    ser = sjson.loads(sjson.dumps(ser))
    dser = dman.deserialize(ser)
    assert base.a == dser.a
    assert base.b == dser.b
    assert base.c == dser.c
    assert base.d == dser.d


def test_records():
    @storable(name="test-ext")
    @serializable
    @dataclass
    class File:
        value: str

    @modelclass
    class Base:
        a: File
        b: File = serializefield()
        c: File = recordfield(stem="c")

    with temporary_context() as ctx:
        base = Base(File('a'), File('b'), File('c'))
        ser = dman.serialize(base, ctx)
        assert os.path.exists(os.path.join(ctx.directory, 'c.json'))
        assert len(os.listdir(ctx.directory)) == 2
        ser = sjson.loads(sjson.dumps(ser))
        dser = dman.deserialize(ser, ctx)
        assert base.a.value == dser.a.value
        assert base.b.value == dser.b.value
        assert base.c.value == dser.c.value


def test_stem_fields():
    @storable(name="test-ext")
    @serializable
    @dataclass
    class File:
        value: str

    @modelclass(store_by_field=True)
    class Base:
        a: File
        b: File = serializefield()
        c: File = recordfield(stem="c")

    with temporary_context() as ctx:
        base = Base(File('a'), File('b'), File('c'))
        ser = dman.serialize(base, ctx)
        assert os.path.exists(os.path.join(ctx.directory, 'c.json'))
        assert os.path.exists(os.path.join(ctx.directory, 'a.json'))
        assert len(os.listdir(ctx.directory)) == 2
        ser = sjson.loads(sjson.dumps(ser))
        dser = dman.deserialize(ser, ctx)
        assert base.a.value == dser.a.value
        assert base.b.value == dser.b.value
        assert base.c.value == dser.c.value


def test_subdir():
    @storable(name="test-ext")
    @serializable
    @dataclass
    class File:
        value: str

    @modelclass(store_by_field=True, subdir='test')
    class Base:
        a: File
        b: File = serializefield()
        c: File = recordfield(stem="c")

    with temporary_context() as ctx:
        base = Base(File('a'), File('b'), File('c'))
        ser = dman.serialize(base, ctx)
        assert os.path.exists(os.path.join(ctx.directory, 'c.json'))
        assert os.path.exists(os.path.join(ctx.directory, 'test', 'a.json'))
        assert len(os.listdir(os.path.join(ctx.directory, 'test'))) == 1
        assert len(os.listdir(ctx.directory)) == 2
        ser = sjson.loads(sjson.dumps(ser))
        dser = dman.deserialize(ser, ctx)
        assert base.a.value == dser.a.value
        assert base.b.value == dser.b.value
        assert base.c.value == dser.c.value


def test_advanced():
    @storable(name="test-ext")
    @serializable
    @dataclass
    class File:
        value: str

    @modelclass(storable=True)
    class Base:
        a: File
        b: File = serializefield()
        c: File = recordfield(stem="c", subdir='test')

    with temporary_context() as ctx:
        base = Base(File('a'), File('b'), File('c'))
        ser = dman.serialize(base, ctx)
        assert os.path.exists(os.path.join(ctx.directory, 'test', 'c.json'))
        assert len(os.listdir(ctx.directory)) == 2
        ser = sjson.loads(sjson.dumps(ser))
        dser = dman.deserialize(ser, ctx)
        assert base.a.value == dser.a.value
        assert base.b.value == dser.b.value
        assert base.c.value == dser.c.value

        dman.remove(dser, ctx)
        ctx.close()   # clean directories
        assert len(os.listdir(ctx.directory)) == 0

    @modelclass
    class Nested:
        a: Base = recordfield(subdir='subdir')

    with temporary_context() as ctx:
        base = Base(File('a'), File('b'), File('c'))
        nested = Nested(base)
        ser = dman.serialize(nested, ctx)
        assert os.path.exists(os.path.join(ctx.directory, 'subdir', 'test', 'c.json'))
        assert len(os.listdir(os.path.join(ctx.directory, 'subdir'))) == 3
        ser = sjson.loads(sjson.dumps(ser))
        dser = dman.deserialize(ser, ctx)

        dman.remove(dser, ctx)
        ctx.close()   # clean directories
        assert len(os.listdir(ctx.directory)) == 0


def test_compact():
    with suppress(TypeError):
        @modelclass
        class Base:
            a: str
            b: list[str]

        base = Base("a", [1, 2])
        ser = sjson.dumps(dman.serialize(base))
        dser = dman.deserialize(sjson.loads(ser))
        assert isinstance(dser, Base)
        assert base == dser

    from typing import List

    @modelclass
    class Base:
        a: str
        b: List[str]

    base = Base("a", [1, 2])
    ser = sjson.dumps(dman.serialize(base))
    dser = dman.deserialize(sjson.loads(ser))
    assert isinstance(dser, Base)
    assert base == dser
