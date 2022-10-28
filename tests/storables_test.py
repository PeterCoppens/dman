from dataclasses import dataclass, field
import pytest
from dman.core.storables import storable, write, read
from dman.core.serializables import serializable
from tempfile import TemporaryDirectory
import os


class TextFile:
    def __init__(self, value: str):
        self.value = value
    
    def __eq__(self, other):
        if not isinstance(other, type(self)):
            return False
        return self.value == other.value
    
    def __write__(self, path: str):
        with open(path, 'w') as f:
            f.write(self.value)

    @classmethod
    def __read__(cls, path: str):
        with open(path, 'r') as f:
            return cls(value=f.read())


@dataclass
class DCLFile:
    value: str
    a: int = 25
    b: list = field(default_factory=lambda: [1, 2, 3])
    c: dict = field(default_factory=lambda: {'a': 25, 'b': 33})


def recreate(obj):
    with TemporaryDirectory() as base:
        path = os.path.join(base, 'test.txt')
        write(obj, path)
        return read(type(obj), path)



@pytest.mark.parametrize('cls', [TextFile, DCLFile])
def test_basic(cls):
    cls = storable(cls, name='__test')
    instance = cls(value='test')
    assert(recreate(instance) == instance)


@pytest.mark.parametrize('cls', [DCLFile])
def test_ser(cls):
    cls = serializable(cls, name='__test')
    cls = storable(cls, name='__test')
    instance = cls(value='test')
    assert(recreate(instance) == instance)