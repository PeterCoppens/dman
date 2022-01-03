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


from dman import modelclass, record_context, serialize, sjson, recordfield, field
from tempfile import TemporaryDirectory


@modelclass(name='model', compact=True)
class Model:
    name: str = field()
    content: ManualFile = recordfield()

with TemporaryDirectory() as base:
    ctx = record_context(base)
    model = Model(name='test', content=ManualFile(value='hello world!'))
    ser = serialize(model, ctx)
    print(sjson.dumps(ser, indent=4))
