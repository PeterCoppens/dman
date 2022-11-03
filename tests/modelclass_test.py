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
from uuid import uuid4
from pathlib import Path


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
        base = Base(File("a"), File("b"), File("c"))
        ser = dman.serialize(base, ctx)
        assert os.path.exists(os.path.join(ctx.directory, "c.json"))
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
        base = Base(File("a"), File("b"), File("c"))
        ser = dman.serialize(base, ctx)
        assert os.path.exists(os.path.join(ctx.directory, "c.json"))
        assert os.path.exists(os.path.join(ctx.directory, "a.json"))
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

    @modelclass(store_by_field=True, subdir="test")
    class Base:
        a: File
        b: File = serializefield()
        c: File = recordfield(stem="c", subdir='')

    with temporary_context() as ctx:
        base = Base(File("a"), File("b"), File("c"))
        ser = dman.serialize(base, ctx)
        assert os.path.exists(os.path.join(ctx.directory, "c.json"))
        assert os.path.exists(os.path.join(ctx.directory, "test", "a.json"))
        assert len(os.listdir(os.path.join(ctx.directory, "test"))) == 1
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
        c: File = recordfield(stem="c", subdir="test")

    with temporary_context() as ctx:
        base = Base(File("a"), File("b"), File("c"))
        ser = dman.serialize(base, ctx)
        dman.tui.walk_directory(ctx.directory)
        assert os.path.exists(os.path.join(ctx.directory, "test", "c.json"))
        assert len(os.listdir(ctx.directory)) == 2
        ser = sjson.loads(sjson.dumps(ser))
        dser = dman.deserialize(ser, ctx)
        assert base.a.value == dser.a.value
        assert base.b.value == dser.b.value
        assert base.c.value == dser.c.value

        dman.remove(dser, ctx)
        ctx.close()  # clean directories
        dman.tui.walk_directory(ctx.directory)
        assert len(os.listdir(ctx.directory)) == 0

    @modelclass
    class Nested:
        a: Base = recordfield(subdir="subdir")

    with temporary_context() as ctx:
        base = Base(File("a"), File("b"), File("c"))
        nested = Nested(base)
        ser = dman.serialize(nested, ctx)
        dman.tui.walk_directory(ctx.directory)
        assert os.path.exists(os.path.join(ctx.directory, "subdir", "test", "c.json"))
        assert len(os.listdir(os.path.join(ctx.directory, "subdir"))) == 3
        ser = sjson.loads(sjson.dumps(ser))
        dser = dman.deserialize(ser, ctx)

        dman.remove(dser, ctx)
        dman.tui.walk_directory(ctx.directory)
        ctx.close()  # clean directories
        assert len(os.listdir(ctx.directory)) == 0
test_advanced()

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


def test_unused():
    @storable
    class Removable:
        __ext__ = ""

        def __init__(self, paths=None, path=None):
            self.paths = (str(uuid4()), str(uuid4())) if paths is None else paths
            self.path = path

        def __repr__(self):
            return f'Removable({self.paths})'

        def __write__(self, path: os.PathLike):
            if not os.path.isdir(path):
                os.mkdir(path)
            with open(os.path.join(path, "content"), "w") as f:
                f.write(", ".join(self.paths))
            for p in self.paths:
                with open(os.path.join(path, p), "w") as f:
                    f.write(f"test")
            self.path = path

        @classmethod
        def __read__(cls, path: os.PathLike):
            with open(os.path.join(path, "content"), "r") as f:
                paths = f.read().split(", ")
            return cls(paths=paths, path=path)

        def __remove__(self, ctx):
            print('removing', self.path)
            if os.path.exists(os.path.join(self.path, 'content')):
                os.remove(os.path.join(self.path, 'content'))
            for p in self.paths:
                if os.path.exists(os.path.join(self.path, p)):
                    os.remove(os.path.join(self.path, p))
        
        def exists(self):
            for p in ['content', *self.paths]:
                if not os.path.exists(os.path.join(self.path, p)):
                    return False
            return True

    @modelclass(store_by_field=True)
    class Base:
        rem: Removable = recordfield(default_factory=Removable)
        unu: Removable = recordfield(default_factory=Removable)

    with temporary_context() as ctx:
        base = Base()
        rem, unu = base.rem, base.unu
        ser = dman.serialize(base, ctx) 
        assert rem.exists()
        assert unu.exists()
        dser = dman.deserialize(ser, ctx)
        dser.unu = Removable()
        ser = dman.serialize(dser, ctx)
        assert not unu.exists()
        assert rem.exists()
        assert dser.unu.exists()


def test_record_field():
    @storable
    class Touch:
        def __init__(self, path = None):
            self.path = path

        def __write__(self, path):
            self.path = path
            Path(path).touch()

        @classmethod
        def __read__(cls, path):
            return cls(path)

    @modelclass
    class Model:
        t0: Touch = dman.field(default_factory=Touch)
        t1: Touch = dman.recordfield(default_factory=Touch, stem='test')
        t2: Touch = dman.recordfield(default_factory=Touch)
        t3: Touch = dman.recordfield(default_factory=Touch, subdir='changed')
        t4: Touch = dman.recordfield(default_factory=Touch, subdir='changed', stem='other')

    with temporary_context() as ctx:
        sdir = Model()
        dman.serialize(sdir, ctx)   # evaluate records
        assert dman.record_fields(sdir)['t0'].target.subdir == ''
        assert dman.record_fields(sdir)['t1'].target.stem == 'test'
        assert dman.record_fields(sdir)['t1'].target.subdir == ''
        assert dman.record_fields(sdir)['t2'].target.subdir == ''
        assert dman.record_fields(sdir)['t3'].target.subdir == 'changed'
        assert dman.record_fields(sdir)['t4'].target.stem == 'other'
        assert dman.record_fields(sdir)['t4'].target.subdir == 'changed'
    
    @modelclass(subdir='sdir')
    class Model:
        t0: Touch = dman.field(default_factory=Touch)
        t1: Touch = dman.recordfield(default_factory=Touch, stem='test')
        t2: Touch = dman.recordfield(default_factory=Touch)
        t3: Touch = dman.recordfield(default_factory=Touch, subdir='changed')
        t4: Touch = dman.recordfield(default_factory=Touch, subdir='changed', stem='other')

    with temporary_context() as ctx:
        sdir = Model()
        dman.serialize(sdir, ctx)   # evaluate records
        assert dman.record_fields(sdir)['t0'].target.subdir == 'sdir'
        assert dman.record_fields(sdir)['t1'].target.stem == 'test'
        assert dman.record_fields(sdir)['t1'].target.subdir == 'sdir'
        assert dman.record_fields(sdir)['t2'].target.subdir == 'sdir'
        assert dman.record_fields(sdir)['t3'].target.subdir == 'changed'
        assert dman.record_fields(sdir)['t4'].target.stem == 'other'
        assert dman.record_fields(sdir)['t4'].target.subdir == 'changed'

    @modelclass(subdir='sdir', cluster=True)
    class Model:
        t0: Touch = dman.field(default_factory=Touch)
        t1: Touch = dman.recordfield(default_factory=Touch, stem='test')
        t2: Touch = dman.recordfield(default_factory=Touch)
        t3: Touch = dman.recordfield(default_factory=Touch, subdir='changed')
        t4: Touch = dman.recordfield(default_factory=Touch, subdir='changed', stem='other')

    with temporary_context() as ctx:
        sdir = Model()
        dman.serialize(sdir, ctx)   # evaluate records
        assert dman.record_fields(sdir)['t0'].target.subdir == os.path.join('sdir', 't0')
        assert dman.record_fields(sdir)['t1'].target.stem == 'test'
        assert dman.record_fields(sdir)['t1'].target.subdir == os.path.join('sdir', 't1')
        assert dman.record_fields(sdir)['t2'].target.subdir == os.path.join('sdir', 't2')
        assert dman.record_fields(sdir)['t3'].target.subdir == 'changed'
        assert dman.record_fields(sdir)['t4'].target.stem == 'other'
        assert dman.record_fields(sdir)['t4'].target.subdir == 'changed'

    @modelclass(cluster=True)
    class Model:
        t0: Touch = dman.field(default_factory=Touch)
        t1: Touch = dman.recordfield(default_factory=Touch, stem='test')
        t2: Touch = dman.recordfield(default_factory=Touch)
        t3: Touch = dman.recordfield(default_factory=Touch, subdir='changed')
        t4: Touch = dman.recordfield(default_factory=Touch, subdir='changed', stem='other')

    with temporary_context() as ctx:
        sdir = Model()
        dman.serialize(sdir, ctx)   # evaluate records
        assert dman.record_fields(sdir)['t0'].target.subdir == 't0'
        assert dman.record_fields(sdir)['t1'].target.stem == 'test'
        assert dman.record_fields(sdir)['t1'].target.subdir == 't1'
        assert dman.record_fields(sdir)['t2'].target.subdir == 't2'
        assert dman.record_fields(sdir)['t3'].target.subdir == 'changed'
        assert dman.record_fields(sdir)['t4'].target.stem == 'other'
        assert dman.record_fields(sdir)['t4'].target.subdir == 'changed'

    @modelclass(store_by_field=True)
    class Model:
        t0: Touch = dman.field(default_factory=Touch)
        t1: Touch = dman.recordfield(default_factory=Touch, stem='test')
        t2: Touch = dman.recordfield(default_factory=Touch)
        t3: Touch = dman.recordfield(default_factory=Touch, subdir='changed')
        t4: Touch = dman.recordfield(default_factory=Touch, subdir='changed', stem='other')

    with temporary_context() as ctx:
        sdir = Model()
        dman.serialize(sdir, ctx)   # evaluate records
        assert dman.record_fields(sdir)['t0'].target.stem == 't0'
        assert dman.record_fields(sdir)['t0'].target.subdir == ''
        assert dman.record_fields(sdir)['t1'].target.stem == 'test'
        assert dman.record_fields(sdir)['t1'].target.subdir == ''
        assert dman.record_fields(sdir)['t2'].target.stem == 't2'
        assert dman.record_fields(sdir)['t2'].target.subdir == ''
        assert dman.record_fields(sdir)['t3'].target.stem == 't3'
        assert dman.record_fields(sdir)['t3'].target.subdir == 'changed'
        assert dman.record_fields(sdir)['t4'].target.stem == 'other'
        assert dman.record_fields(sdir)['t4'].target.subdir == 'changed'