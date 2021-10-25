from dataclasses import dataclass
from storables import STO_FIELD, StoragePlan, modelclass, WRITE, READ, read, recordfield, storable, write, StoringSerializer, storable_type
from serializables import SER_CONTENT, SER_TYPE, Serializer, serialize, deserialize
import inspect

import configparser
import json

SECTION_ATTR = '__sec__type'
SECTION_NAME = '__sec__name'
TYPE_SECTION = '__section_types__'

def is_section(obj):
    if not inspect.isclass(obj):
        return False
    return getattr(obj, SECTION_ATTR, False)


def getsections(cls):
    res = {}
    for name, obj in inspect.getmembers(cls):
        if is_section(obj):
            name = getattr(obj, SECTION_NAME, name)
            res[name] = obj
    return res


def section(cls=None, /, *, name: str = None, sto_name: str = None, **kwargs):
    def wrap(cls):
        local_name = name
        setattr(cls, SECTION_ATTR, True)
        
        if local_name is None:
            local_name = cls.__name__

        setattr(cls, SECTION_NAME, local_name)
        return modelclass(cls, name=sto_name, **kwargs)

    # See if we're being called as @section or @section().
    if cls is None:
        # We're called with parens.
        return wrap

    # We're called as @section without parens.
    return wrap(cls)


def configclass(cls=None, /, *, name: str = None, **kwargs):
    def wrap(cls):
        for k, v in getsections(cls).items():
            value = None
            try:
                value = v()
            except TypeError as err:
                raise err from TypeError(f'section "{k}" does not has a default initializer.')


            setattr(cls, k, value)

        if getattr(cls, WRITE, None) is None:                
            setattr(cls, WRITE, _write__config)
        
        if getattr(cls, READ, None) is None:
            setattr(cls, READ, _read__config)

        return storable(cls, name=name, **kwargs)

    # See if we're being called as @configclass or @configclass().
    if cls is None:
        # We're called with parens.
        return wrap

    # We're called as @configclass without parens.
    return wrap(cls)


def _write__config(self, path: str, serializer: Serializer = None):
    cfg = configparser.ConfigParser()
    section_types = {}
    for section in getsections(self):
        cfg.add_section(section)
        value: dict = serialize(getattr(self, section), serializer)
        type, content = value.get(SER_TYPE), value.get(SER_CONTENT)
        processed = {}
        for k, v in content.items():
            processed[k] = json.dumps(v)
        
        cfg[section] = processed
        section_types[section] = type
    
    cfg.add_section(TYPE_SECTION)
    cfg[TYPE_SECTION] = section_types
    
    with open(path, 'w') as f:
        cfg.write(f)       


@classmethod
def _read__config(cls, path: str, serializer: Serializer = None):
    cfg = configparser.ConfigParser()
    cfg.read(path)

    res = cls()

    if TYPE_SECTION not in cfg.sections():
        return res
        
    section_types = cfg[TYPE_SECTION]
    for k, v in section_types.items():
        type = v
        
        if k not in cfg.sections():
            continue

        content = dict(cfg[k])

        processed = {}
        for kk, vv in content.items():
            processed[kk] = json.loads(vv)

        serialized = {SER_TYPE: type, SER_CONTENT: processed}
        setattr(res, k, deserialize(serialized, serializer))
    
    return res
        

if __name__ == '__main__':
    @modelclass(storable=True)
    class TestModel:
        a: str = 25

    @configclass
    class TestConfig:
        @section(name='first')
        class FirstSection:
            b: int = 3
            a: str = 'wow'
        first: FirstSection     # (use these, not the local classes, turn into field and then dataclass)
        
        @section(name='second')
        class SecondSection:
            c: str = 'hello'
            d: TestModel = recordfield(default_factory=TestModel)
        second: SecondSection   # optional
    
    cfg = TestConfig()
    cfg.first.a = 'yo'
    with StoringSerializer('out/fourth', clean_on_open=False) as sr:
        path, _ = sr.request(StoragePlan(filename='test.ini'))
        write(cfg, path, sr)
        res: TestConfig = read(storable_type(TestConfig), path, serializer=sr)
        print(res.first.a)
        print(res.second.d)
        print(res.first.b)
        

    