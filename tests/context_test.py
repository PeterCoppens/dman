from tempfile import TemporaryDirectory
from dman.core.storables import FileSystem, FileSystemError
import os
from dman.numeric import barray
import numpy as np

from contextlib import contextmanager
import sys
from io import StringIO


arr = np.ones(3).view(barray)


@contextmanager
def mock_input(target: str):
    _stdin = sys.stdin
    sys.stdin = StringIO(target)
    yield
    sys.stdin = _stdin


@contextmanager
def t_fs(*paths):
    with TemporaryDirectory() as base:
        res = FileSystem(base)
        for p in paths:
            res.write(arr, p)
        yield res


def test_fs_multi():
    fs = None

    def validate(s: set):
        assert set(os.listdir(fs.directory)) == s

    with t_fs("test.npy") as fs:
        with mock_input("test-manual.npy"):
            fs.write(arr, "test.npy", choice="prompt")
        validate({"test.npy", "test-manual.npy"})

    with t_fs("test.npy") as fs:
        with mock_input("auto"):
            fs.write(arr, "test.npy", choice="prompt")
        fs.write(arr, "test.npy", choice="auto")
        fs.write(arr, "test1.npy", choice="auto")
        validate({"test.npy", "test0.npy", "test1.npy", "test2.npy"})

    with t_fs("test.npy") as fs:
        with mock_input("x"):
            fs.write(arr, "test.npy", choice="prompt")
        fs.write(arr, "test.npy", choice="x")
        fs.write(arr, "test.npy", choice="ignore")
        validate({"test.npy"})

    with t_fs("test.npy") as fs:
        try:
            with mock_input("q"):
                fs.write(arr, "test.npy", choice="prompt")
            assert False
        except FileSystemError:
            assert True

    with t_fs("test.npy") as fs:
        try:
            fs.write(arr, "test.npy", choice="q")
            assert False
        except FileSystemError:
            assert True

    with t_fs("test.npy") as fs:
        try:
            fs.write(arr, "test.npy", choice="quit")
            assert False
        except FileSystemError:
            assert True


def test_fs_remove():
    fs = None
    def validate(s: set, *args):
        assert set(os.listdir(os.path.join(fs.directory, *args))) == s

    with t_fs("test.npy") as fs:
        fs.delete("test.npy")
        validate(set())
        assert os.path.isdir(fs.directory)  # root directory not removed

        _ = lambda *p: os.path.join('inner', *p)
        fs.write(arr, _("test.npy"))
        fs.write(arr, _("other.npy"))
        validate({"test.npy", "other.npy"}, _())
        fs.delete(_("test.npy"))
        validate({"other.npy"}, _())

        fs.delete(_("other.npy"))
        assert os.path.isdir(fs.directory)
        assert not os.path.isdir(os.path.join(fs.directory, _()))  # cleaned
