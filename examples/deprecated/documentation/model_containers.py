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

# ------------------------------------------------------------------------------
# mlist usage
# ------------------------------------------------------------------------------

from dman import mlist, serialize, deserialize, sjson
from dman import context
from dman import tui
from tempfile import TemporaryDirectory

lst = mlist()
lst.append('value')
lst.append(ManualFile(value='hello world!'))

with TemporaryDirectory() as base:
    ctx = context(base)
    ser = serialize(lst, ctx)

    print(sjson.dumps(ser, indent=4))
    tui.walk_directory(base)

    rec = lst.store[1]
    print(f'{rec=}')

    res = deserialize(ser, ctx)
    rec = res.store[-1]
    print(f'{rec=}')        # Record(UL[manual], target=930be22e-d120-4ae9-a3ca-bb4a31e3980e)

    print(res[1].value)     # hello world!
    print(f'{rec=}')        # Record(manual, target=8a9fa9b2-f0d7-4d56-ad6c-3d80686bc72c)

    # advanced mlist storing
    lst.append(ManualFile(value='stored in lst'))
    lst.record(ManualFile(value='stored in root'), subdir='../')
    lst.record(ManualFile(value='preloaded'), preload=True)

    res = deserialize(serialize(lst, ctx), ctx)
    print(f'{res.store[3]=}')
    print(f'{res[3].value=}')
    print(f'{res.store[3]=}')

    print(f'{res.store[4]=}')
    print(f'{res[4].value=}')
    print(f'{res.store[4]=}')

    tui.walk_directory(base)
    lst.clear()
    serialize(lst, ctx)
    tui.walk_directory(base)

# ------------------------------------------------------------------------------
# mdict usage
# ------------------------------------------------------------------------------

from dman import mdict, serialize, sjson
from dman import context
from dman import tui
from tempfile import TemporaryDirectory

dct = mdict()
dct['key'] = 'value'
dct['manual'] = ManualFile(value='hello world!')

with TemporaryDirectory() as base:
    ctx = context(base)
    ser = serialize(dct, ctx)

    print(sjson.dumps(ser, indent=4))
    tui.walk_directory(base)

    rec = dct.store['manual']
    print(f'{rec=}')

# ------------------------------------------------------------------------------
# modelclass usage
# ------------------------------------------------------------------------------

from dman import modelclass, context, serialize, sjson
from tempfile import TemporaryDirectory

@modelclass(name='model', compact=False)
class Model:
    name: str
    content: ManualFile

with TemporaryDirectory() as base:
    ctx = context(base)
    model = Model(name='test', content=ManualFile(value='hello world!'))
    ser = serialize(model, ctx)
    print(sjson.dumps(ser, indent=4))


# recordfield
from dman import recordfield

@modelclass(name='model')
class Model:
    name: str
    content: ManualFile = recordfield()


# serializefield
from dman import recordfield, modelclass, serializefield

@modelclass(name='field', storable=True)
class Field:
    value: str

@modelclass(name='model')
class Model:
    first: Field
    second: Field = serializefield()