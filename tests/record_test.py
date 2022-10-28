from dman.model.record import record, Record, Context, is_unloaded, isvalid
from dman.core.storables import storable
from dman.core.serializables import serialize, deserialize, sjson, dataclass

from tempfile import TemporaryDirectory
import os
from contextlib import contextmanager
from path_test import temporary_mount

        
@contextmanager
def temporary_context(**kwargs):
    with TemporaryDirectory() as base:
        res = Context.mount('key', base=base, **kwargs)
        yield res
        res.fs.close()


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
    with temporary_context() as ctx:
        serialize(rec, ctx)
        target = os.path.join(ctx.directory, rec.target)
        assert(os.path.exists(target))


def recreate(rec: Record, ctx: Context = None):
    t = None
    if ctx is None:
        t = temporary_context()
        ctx = t.__enter__()
    ser = serialize(rec, ctx)
    res: Record = deserialize(
        sjson.loads(sjson.dumps(ser)), 
        ctx
    )
    if t:
        t.__exit__(None, None, None)
    return res


def assert_equals(rec: Record, other: Record):
    assert(rec.content == other.content)
        


def test_auto_config():
    test = Base(value='hello world!')
    encountered_names = []
    for i in range(100):
        rec = record(test)
        assert(rec.target.name not in encountered_names)
        encountered_names.append(rec.target.name)
        assert_creates_file(rec)


def test_suffix_config():
    test = Base(value='hello world!')
    rec = record(test, suffix='.txt')
    _, suffix = rec.target.name.split('.')
    assert(suffix == 'txt')
    assert_creates_file(rec)


def test_stem_suffix_config():
    test = Base(value='hello world!')
    rec = record(test, stem='teststr', suffix='.testsuffix')
    stem, suffix = rec.target.name.split('.')
    assert(stem == 'teststr' and suffix == 'testsuffix')
    assert_creates_file(rec)


def test_name_config():
    test = Base(value='hello world!')
    rec = record(test, name='testname.other')
    stem, suffix = rec.target.name.split('.')
    assert(stem == 'testname' and suffix == 'other')
    assert_creates_file(rec)


def test_ext_stem_config():
    testext = Ext(value='hello world!.json')
    rec = record(testext, stem='morename') 
    stem, suffix = rec.target.name.split('.')
    assert(stem == 'morename' and suffix == 'requested')
    assert_creates_file(rec)


def test_ext_name_config():
    testext = Ext(value='hello world!.json')
    rec = record(testext, name='morename')
    assert(len(rec.target.name.split('.')) == 1)
    assert_creates_file(rec)


def test_ext_stem_suffix_config():
    testext = Ext(value='hello world!.json')
    rec = record(testext, stem='morename', suffix='.somesuffix')
    stem, suffix = rec.target.name.split('.')
    assert(stem == 'morename' and suffix == 'somesuffix')
    assert_creates_file(rec)


def test_re_serialize():
    test = Base(value='hello world!')
    rec = record(test, preload=True)
    res = recreate(rec)
    assert(not is_unloaded(res._content))
    assert_equals(res, rec)


def test_no_preload():
    test = Base(value='hello world!')
    rec = record(test)
    with temporary_context() as ctx:
        res = recreate(rec, ctx=ctx)
        assert(is_unloaded(res._content))
        assert_equals(res, rec)
        assert(not is_unloaded(res._content))

        res = rec
        for _ in range(10):
            res = recreate(res, ctx=ctx)
            assert(is_unloaded(res._content))
        assert_equals(res, rec)
        assert(not is_unloaded(res._content))


def test_exists():
    test = Base(value='hello world!')
    rec = record(test, name='temp.txt', preload=False)
    with temporary_context() as ctx:
        ser = serialize(rec, ctx)
        os.remove(os.path.join(ctx.directory, rec.target))
        res: Record = deserialize(ser, ctx)
        assert(res.exists())
        res.content
        assert(not res.exists())


def test_move():
    test = Base(value='hello world!')
    rec = record(test, name='temp.txt')
    with temporary_context() as ctx:
        ctx = Context(ctx.fs, 'first')
        ser = serialize(rec, ctx)
        res: Record = deserialize(ser, ctx)
        
        ctx = Context(ctx.fs, 'second')
        ser = serialize(res, ctx)
        assert(os.path.exists(os.path.join(ctx.directory, 'temp.txt')))


def test_fail_context():
    @storable(name='base')
    class Base:
        def __init__(self, value: str):
            self.value = value

        def __write__(self, path: str): ...

        @classmethod
        def __read__(cls, path: str): ...

    rec = record(Base('test'))
    ser = serialize(rec)
    dser: Record = deserialize(ser)
    assert(not isvalid(dser.exceptions.write))
    assert(not isvalid(dser.exceptions.read))
    assert(not dser.isvalid())


def test_fail_write():
    with temporary_context() as ctx:
        @storable(name='base')
        class Base:
            def __init__(self, value: str):
                self.value = value

            def __write__(self, path: str):
                raise RuntimeError('Issue.')

            @classmethod
            def __read__(cls, path: str):
                with open(path, 'r') as f:
                    return cls(f.read())

        rec = record(Base('test'))

        ser = serialize(rec, context=ctx)
        dser: Record = deserialize(ser, context=ctx)
        assert(not isvalid(dser.exceptions.write))
        assert(isvalid(dser.exceptions.read))
        assert(dser.isvalid())
        
        @storable(name='base')
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
        with open(os.path.join(ctx.directory, dser.target), 'w') as f:
            f.write('recovered')

        for _ in range(2):
            ser = serialize(dser, context=ctx)
            dser: Record = deserialize(ser, context=ctx)
            assert(isvalid(dser.exceptions.write))
            assert(isvalid(dser.exceptions.read))
            assert(dser.isvalid())
            assert(dser.content.value == 'recovered')

def test_fail_read():
    with temporary_context() as ctx:
        @storable(name='base')
        class Base:
            def __init__(self, value: str):
                self.value = value

            def __write__(self, path: str):
                with open(path, 'w') as f:
                    f.write(self.value)

            @classmethod
            def __read__(cls, path: str):
                raise RuntimeError('Invalid.')

        rec = record(Base('test'))

        ser = serialize(rec, context=ctx)
        dser: Record = deserialize(ser, context=ctx)
        assert(isvalid(dser.exceptions.write))
        assert(isvalid(dser.exceptions.read))
        assert(not dser.isvalid(load=True))
        assert(not isvalid(dser.exceptions.read))

        @storable(name='base')
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
        ser2 = serialize(dser, context=ctx)

        # we can load the content of the already loaded class
        assert(isvalid(dser.exceptions.write))
        assert(not isvalid(dser.exceptions.read))
        assert(dser.isvalid(load=True))
        assert(isvalid(dser.exceptions.read))

        # we can also deserialize
        dser: Record = deserialize(ser, context=ctx)
        assert(isvalid(dser.exceptions.write))
        assert(isvalid(dser.exceptions.read))
        assert(dser.isvalid(load=True))
        assert(isvalid(dser.exceptions.read))

        dser: Record = deserialize(ser2, context=ctx)
        assert(isvalid(dser.exceptions.write))
        assert(not isvalid(dser.exceptions.read))
        assert(dser.isvalid(load=True))
        assert(isvalid(dser.exceptions.read))
        
        



