from dman import record
from dman import storable
from dman import serialize, deserialize, sjson
from dman import dataclass

from tempfile import TemporaryDirectory
import os

from dman.model.record import Record, Context, is_unloaded
import dman

@storable(name='test')
@dataclass
class Base:
    value: str


@storable(name='test-ext')
@dataclass
class Ext:
    __ext__ = '.requested'
    value: str


def assert_creates_file(rec: Record):
    with TemporaryDirectory() as base:
        ctx = Context(base)
        serialize(rec, ctx)
        target = os.path.join(base, rec.config.target)
        assert(os.path.exists(target))


def recreate(rec: Record, ctx: Context):
    ser = serialize(rec, ctx)
    res: Record = deserialize(
        sjson.loads(sjson.dumps(ser)), 
        ctx
    )
    return res


def assert_equals(rec: Record, other: Record):
    assert(rec.content == other.content)
        


def test_auto_config():
    test = Base(value='hello world!')
    encountered_names = []
    for i in range(100):
        rec = record(test)
        assert(rec.config.name not in encountered_names)
        encountered_names.append(rec.config.name)
        assert_creates_file(rec)


def test_suffix_config():
    test = Base(value='hello world!')
    rec = record(test, suffix='.txt')
    _, suffix = rec.config.name.split('.')
    assert(suffix == 'txt')
    assert_creates_file(rec)


def test_stem_suffix_config():
    test = Base(value='hello world!')
    rec = record(test, stem='teststr', suffix='.testsuffix')
    stem, suffix = rec.config.name.split('.')
    assert(stem == 'teststr' and suffix == 'testsuffix')
    assert_creates_file(rec)


def test_name_config():
    test = Base(value='hello world!')
    rec = record(test, name='testname.other')
    stem, suffix = rec.config.name.split('.')
    assert(stem == 'testname' and suffix == 'other')
    assert_creates_file(rec)


def test_ext_stem_config():
    testext = Ext(value='hello world!.json')
    rec = record(testext, stem='morename') 
    stem, suffix = rec.config.name.split('.')
    assert(stem == 'morename' and suffix == 'requested')
    assert_creates_file(rec)


def test_ext_name_config():
    testext = Ext(value='hello world!.json')
    rec = record(testext, name='morename')
    assert(len(rec.config.name.split('.')) == 1)
    assert_creates_file(rec)


def test_ext_stem_suffix_config():
    testext = Ext(value='hello world!.json')
    rec = record(testext, stem='morename', suffix='.somesuffix')
    stem, suffix = rec.config.name.split('.')
    assert(stem == 'morename' and suffix == 'somesuffix')
    assert_creates_file(rec)


def test_re_serialize():
    test = Base(value='hello world!')
    rec = record(test, preload=True)
    with TemporaryDirectory() as base:
        res = recreate(rec, Context(base))
        assert(not is_unloaded(res._content))
        assert_equals(res, rec)


def test_no_preload():
    test = Base(value='hello world!')
    rec = record(test)
    with TemporaryDirectory() as base:
        res = recreate(rec, Context(base))
        assert(is_unloaded(res._content))
        assert_equals(res, rec)
        assert(not is_unloaded(res._content))

        res = rec
        for _ in range(10):
            res = recreate(res, Context(base))
            assert(is_unloaded(res._content))
        assert_equals(res, rec)
        assert(not is_unloaded(res._content))


def test_exists():
    test = Base(value='hello world!')
    rec = record(test, name='temp.txt', preload=False)
    with TemporaryDirectory() as base:
        ctx = Context(base)
        ser = serialize(rec, ctx)
        os.remove(os.path.join(base, rec.config.target))
        res: Record = deserialize(ser, ctx)
        assert(res.exists())
        res.content
        assert(not res.exists())


def test_move():
    test = Base(value='hello world!')
    rec = record(test, name='temp.txt')
    with TemporaryDirectory() as base:
        ctx = Context(os.path.join(base, 'first'))
        ser = serialize(rec, ctx)
        res: Record = deserialize(ser, ctx)
        
        ctx = Context(os.path.join(base, 'second'))
        ser = serialize(res, ctx)
        assert(os.path.exists(os.path.join(ctx.directory, 'temp.txt')))


def test_fail_context():
    @dman.storable(name='base')
    class Base:
        def __init__(self, value: str):
            self.value = value

        def __write__(self, path: str): ...

        @classmethod
        def __read__(cls, path: str): ...

    rec = dman.record(Base('test'))
    ser = dman.serialize(rec)
    dser: Record = dman.deserialize(ser)
    assert(not dman.isvalid(dser.exceptions.write))
    assert(not dman.isvalid(dser.exceptions.read))
    assert(not dser.isvalid())


def test_fail_write():
    with TemporaryDirectory() as base:
        @dman.storable(name='base')
        class Base:
            def __init__(self, value: str):
                self.value = value

            def __write__(self, path: str):
                raise RuntimeError('Issue.')

            @classmethod
            def __read__(cls, path: str):
                with open(path, 'r') as f:
                    return cls(f.read())

        rec = dman.record(Base('test'))

        ctx = Context(base)
        ser = dman.serialize(rec, context=ctx)
        dser: Record = dman.deserialize(ser, context=ctx)
        assert(not dman.isvalid(dser.exceptions.write))
        assert(dman.isvalid(dser.exceptions.read))
        assert(dser.isvalid())
        
        @dman.storable(name='base')
        class Base:
            def __init__(self, value: str):
                self.value = value

            def __write__(self, path: str):
                with open(path, 'w') as f:
                    f.write(self.value)

            @classmethod
            def __read__(cls, path: str):
                with open(path, 'r') as f:
                    return cls(f.read())
        
        # manually create the file
        with open(os.path.join(base, dser.target), 'w') as f:
            f.write('recovered')

        for _ in range(2):
            ser = dman.serialize(dser, context=ctx)
            dser: Record = dman.deserialize(ser, context=ctx)
            assert(dman.isvalid(dser.exceptions.write))
            assert(dman.isvalid(dser.exceptions.read))
            assert(dser.isvalid())
            assert(dser.content.value == 'recovered')


def test_fail_read():
    with TemporaryDirectory() as base:
        @dman.storable(name='base')
        class Base:
            def __init__(self, value: str):
                self.value = value

            def __write__(self, path: str):
                with open(path, 'w') as f:
                    f.write(self.value)

            @classmethod
            def __read__(cls, path: str):
                raise RuntimeError('Invalid.')

        rec = dman.record(Base('test'))

        ctx = Context(base)
        ser = dman.serialize(rec, context=ctx)
        dser: Record = dman.deserialize(ser, context=ctx)
        assert(dman.isvalid(dser.exceptions.write))
        assert(dman.isvalid(dser.exceptions.read))
        assert(not dser.isvalid(load=True))
        assert(not dman.isvalid(dser.exceptions.read))

        @dman.storable(name='base')
        class Base:
            def __init__(self, value: str):
                self.value = value

            def __write__(self, path: str):
                with open(path, 'w') as f:
                    f.write(self.value)

            @classmethod
            def __read__(cls, path: str):
                with open(path, 'r') as f:
                    return cls(f.read())

        # serialize the invalid class
        ser2 = dman.serialize(dser, context=ctx)

        # we can load the content of the already loaded class
        assert(dman.isvalid(dser.exceptions.write))
        assert(not dman.isvalid(dser.exceptions.read))
        assert(dser.isvalid(load=True))
        assert(dman.isvalid(dser.exceptions.read))

        # we can also deserialize
        dser: Record = dman.deserialize(ser, context=ctx)
        assert(dman.isvalid(dser.exceptions.write))
        assert(dman.isvalid(dser.exceptions.read))
        assert(dser.isvalid(load=True))
        assert(dman.isvalid(dser.exceptions.read))

        dser: Record = dman.deserialize(ser2, context=ctx)
        assert(dman.isvalid(dser.exceptions.write))
        assert(not dman.isvalid(dser.exceptions.read))
        assert(dser.isvalid(load=True))
        assert(dman.isvalid(dser.exceptions.read))
        
        



