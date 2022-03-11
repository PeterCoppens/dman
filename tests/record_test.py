from dman import context, record
from dman import storable
from dman import serialize, deserialize, sjson
from dman import dataclass

from tempfile import TemporaryDirectory
import os

from dman.persistent.record import Record, Context, is_unloaded


@storable(name='test')
@dataclass
class Test:
    value: str


@storable(name='test-ext')
@dataclass
class TestExt:
    __ext__ = '.requested'
    value: str


def assert_creates_file(rec: Record):
    with TemporaryDirectory() as base:
        ctx = context(base)
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
    test = Test(value='hello world!')
    encountered_names = []
    for i in range(100):
        rec = record(test)
        assert(rec.config.name not in encountered_names)
        encountered_names.append(rec.config.name)
        assert_creates_file(rec)


def test_suffix_config():
    test = Test(value='hello world!')
    rec = record(test, suffix='.txt')
    _, suffix = rec.config.name.split('.')
    assert(suffix == 'txt')
    assert_creates_file(rec)


def test_stem_suffix_config():
    test = Test(value='hello world!')
    rec = record(test, stem='teststr', suffix='.testsuffix')
    stem, suffix = rec.config.name.split('.')
    assert(stem == 'teststr' and suffix == 'testsuffix')
    assert_creates_file(rec)


def test_name_config():
    test = Test(value='hello world!')
    rec = record(test, name='testname.other')
    stem, suffix = rec.config.name.split('.')
    assert(stem == 'testname' and suffix == 'other')
    assert_creates_file(rec)


def test_ext_stem_config():
    testext = TestExt(value='hello world!.json')
    rec = record(testext, stem='morename') 
    stem, suffix = rec.config.name.split('.')
    assert(stem == 'morename' and suffix == 'requested')
    assert_creates_file(rec)


def test_ext_name_config():
    testext = TestExt(value='hello world!.json')
    rec = record(testext, name='morename')
    assert(len(rec.config.name.split('.')) == 1)
    assert_creates_file(rec)


def test_ext_stem_suffix_config():
    testext = TestExt(value='hello world!.json')
    rec = record(testext, stem='morename', suffix='.somesuffix')
    stem, suffix = rec.config.name.split('.')
    assert(stem == 'morename' and suffix == 'somesuffix')
    assert_creates_file(rec)


def test_re_serialize():
    test = Test(value='hello world!')
    rec = record(test, preload=True)
    with TemporaryDirectory() as base:
        res = recreate(rec, context(base))
        assert(not is_unloaded(res._content))
        assert_equals(res, rec)


def test_no_preload():
    test = Test(value='hello world!')
    rec = record(test)
    with TemporaryDirectory() as base:
        res = recreate(rec, context(base))
        assert(is_unloaded(res._content))
        assert_equals(res, rec)
        assert(not is_unloaded(res._content))

        res = rec
        for _ in range(10):
            res = recreate(res, context(base))
            assert(is_unloaded(res._content))
        assert_equals(res, rec)
        assert(not is_unloaded(res._content))


def test_exists():
    test = Test(value='hello world!')
    rec = record(test, name='temp.txt', preload=False)
    with TemporaryDirectory() as base:
        ctx = context(base)
        ser = serialize(rec, ctx)
        os.remove(os.path.join(base, rec.config.target))
        res: Record = deserialize(ser, ctx)
        assert(res.exists())
        res.content
        assert(not res.exists())


def test_move():
    test = Test(value='hello world!')
    rec = record(test, name='temp.txt')
    with TemporaryDirectory() as base:
        ctx = context(os.path.join(base, 'first'))
        ser = serialize(rec, ctx)
        res: Record = deserialize(ser, ctx)
        
        ctx = context(os.path.join(base, 'second'))
        ser = serialize(res, ctx)
        assert(os.path.exists(os.path.join(ctx.path, 'temp.txt')))