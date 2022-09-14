# ------------------------------------------------------------------------------
# direct record usage
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


# record interaction
from dman import record, serialize, deserialize, sjson, context
from tempfile import TemporaryDirectory
from dman import tui

instance = ManualFile(value='hello world!')
rec = record(instance)

with TemporaryDirectory() as base:
    ctx = context(base)
    ser = serialize(rec, context=ctx)

    # show the serialization
    print(sjson.dumps(ser, indent=4))

    # list existing files
    tui.walk_directory(base)

    # deserialize record
    res = deserialize(ser, ctx)
    print(f'{res=}')

    # load the content
    content: ManualFile = res.content
    print(f'{content.value=}')
    print(f'{res=}')