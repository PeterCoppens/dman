# ------------------------------------------------------------------------------
# manual definition of storable
# ------------------------------------------------------------------------------

from dman import storable

@storable(name='manual')
class ManualFile:
    def __init__(self, value: str):
        self.value = value

    def __write__(self, path: str):
        with open(path, 'w') as f:
            f.write(self.value)

    @classmethod
    def __read__(cls, path: str):
        with open(path, 'r') as f:
            value = f.read()
            return cls(value)

# storing files
import os
from tempfile import TemporaryDirectory
from dman import write, read

with TemporaryDirectory() as base:
    path = os.path.join(base, 'obj.out')
    write(ManualFile(value='test'), path)
    result: ManualFile = read('manual', path)
    print(result.value)
