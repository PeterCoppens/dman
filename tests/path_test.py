import os
import sys
from contextlib import contextmanager
from io import StringIO
from tempfile import TemporaryDirectory
from pathlib import Path

from dman.core.path import mount, target, TargetException, script_label


@contextmanager
def mock_input(target: str):
    _stdin = sys.stdin
    sys.stdin = StringIO(target)
    yield
    sys.stdin = _stdin

        
@contextmanager
def temporary_mount(*paths, **kwargs):
    with TemporaryDirectory() as base:
        res = mount('key', base=base, **kwargs)
        for p in paths:
            res.open(p)
        yield res


def test_target():
    ref = os.path.join('folder', 'test.npy')
    t1 = target(stem='test', suffix='.npy', subdir='folder')
    t2 = target(name='test.npy', subdir='folder')
    assert(t1 == t2)
    assert(t1 == ref)

    t1 = target(stem='test', subdir='folder')
    t2 = t1.update(suffix='.npy')
    assert(t2 == ref)

    t1 = target(stem='test', subdir='folder')
    t2 = t1.update(name='test.npy')
    assert(t2 == ref)

    try:
        os.path.abspath(target(stem='test', subdir='folder'))
        assert False
    except TargetException:
        assert True

    lst = [target(name='test.npy')]
    assert('test.npy' in lst)
    assert(target(stem='test', suffix='.npy') in lst)


def test_mount():
    with TemporaryDirectory() as base:
        label = script_label(base)
        ref = os.path.join(base, 'cache', label, 'folder', 'key')
        mnt = mount('key', subdir='folder', base=base)
        assert mnt == ref


def test_open():
    with temporary_mount('test.npy') as mnt:
        with mock_input("test-manual.npy"):
            t = mnt.open('test.npy', choice='prompt')
        assert t == 'test-manual.npy'
        with mock_input("test-manual.npy\ntest-second.npy"):
            t = mnt.open('test.npy', choice='prompt')
        assert t == 'test-second.npy'
        
    with temporary_mount('test.npy') as mnt:
        with mock_input("auto"):
            t = mnt.open('test.npy', choice='prompt')
        assert t == 'test0.npy'
        with mock_input("\n"):
            t = mnt.open('test.npy', choice='prompt')
        assert t == 'test1.npy'
        with mock_input("auto"):
            t = mnt.open('test1.npy', choice='prompt')
        assert t == 'test2.npy'
        
    with temporary_mount('test.npy') as mnt:
        with mock_input("x"):
            t = mnt.open('test.npy', choice='prompt')
        assert t == 'test.npy'
        
    with temporary_mount('test.npy') as mnt:
        try:
            with mock_input("q"):
                t = mnt.open('test.npy', choice='prompt')
            assert False
        except TargetException:
            assert True
        
    with temporary_mount('test.npy') as mnt:
        t = mnt.open('test.npy', choice='auto')
        assert t == 'test0.npy'
        t = mnt.open('test.npy', choice='auto')
        assert t == 'test1.npy'
        t = mnt.open('test1.npy', choice='auto')
        assert t == 'test2.npy'
        
    with temporary_mount('test.npy') as mnt:
        t = mnt.open('test.npy', choice='ignore')
        assert t == 'test.npy'
        
    with temporary_mount('test.npy') as mnt:
        try:
            t = mnt.open('test.npy', choice='quit')
            assert False
        except TargetException:
            assert True


def test_gitignore():
    with temporary_mount('test.npy', cluster=True) as mnt:
        mnt.close()
        assert not os.path.exists(os.path.join(os.path.dirname(mnt), '.gitignore'))
    with temporary_mount('test.npy', cluster=True) as mnt:    
        Path(os.path.join(mnt, 'test.npy')).touch()
        mnt.close()
        with open(os.path.join(os.path.dirname(mnt), '.gitignore'), 'r') as f:
            ignored = f.read().splitlines()
        assert set(ignored) == {'.gitignore', 'key'}
        mnt.close()
        with open(os.path.join(os.path.dirname(mnt), '.gitignore'), 'r') as f:
            ignored = f.read().splitlines()
        assert set(ignored) == {'.gitignore', 'key'}
    with temporary_mount('test.npy', cluster=False) as mnt:
        Path(os.path.join(mnt, 'test.npy')).touch()
        with open(os.path.join(os.path.dirname(mnt), '.gitignore'), 'w') as f:
            f.write('\n'.join(['some', 'other']))
        mnt.close()
        with open(os.path.join(os.path.dirname(mnt), '.gitignore'), 'r') as f:
            ignored = f.read().splitlines()
        assert set(ignored) == {'.gitignore', 'test.npy', 'some', 'other'}


def test_prune():
    with temporary_mount(cluster=True) as mnt:
        t1 = mnt.open(target(name='test.npy', subdir='dir1'))
        mnt.open(target(name='test.npy', subdir='dir2'))
        mnt.open(target(name='test.npy', subdir=os.path.join('dir3', 'dir4')))
        t2 = mnt.open(target(name='test.npy', subdir=os.path.join('dir3', 'dir5')))
        Path(os.path.join(mnt, t1)).touch()
        Path(os.path.join(mnt, t2)).touch()
        mnt.close()
        assert set(os.listdir(mnt)) == {'dir1', 'dir3'}
        assert set(os.listdir(os.path.join(mnt, 'dir1'))) == {'test.npy',}
        assert set(os.listdir(os.path.join(mnt, 'dir3',))) == {'dir5',}
        assert set(os.listdir(os.path.join(mnt, 'dir3', 'dir5'))) == {'test.npy',}
