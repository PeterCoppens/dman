import json
import copy

from typing import Iterable
from storables import StoragePlan, StoringConfig, isloaded, LOAD, record, is_storable, Record, storable, StoringSerializer
from serializables import SERIALIZE, DESERIALIZE, _deserialize__dataclass__inner, _serialize__dataclass__inner, NO_SERIALIZE
from serializables import Serializer, serialize, deserialize, is_serializable, is_deserializable, serializable
from dataclasses import MISSING, field, fields
from smartdataclasses import Wrapper, wrappedclass, WrappedField, attr_wrapper


STO_FIELD = '_record__fields'
RECORD_FIELD = '_record__field'





class RecordWrapper(Wrapper):
    WRAPPED_FIELDS_NAME = STO_FIELD

    def __init__(self, plan: StoragePlan) -> None:
        self.plan = plan

    def __process__(self, obj, wrapped):
        if wrapped is None:
            return None
            
        if not isloaded(wrapped):
            wrapped = getattr(wrapped, LOAD)()
        return wrapped
    
    def __store_process__(self, obj, processed):
        return processed


def recordfield(*, default=MISSING, default_factory=MISSING, 
        init: bool = True, repr: bool = False, 
        hash: bool = False, compare: bool = False, metadata=None,
        plan: StoragePlan = None,
        filename: str = None, preload: bool = False, ignored: bool = True,
        subdir: str = None, gitkeep: bool = None
    ):

    if plan is None: plan = StoragePlan(filename, preload, ignored, subdir, gitkeep)

    return WrappedField(
        RecordWrapper(plan=plan),
        default=default, default_factory=default_factory, 
        init=init, repr=repr, hash=hash, 
        compare=compare, metadata=metadata
    )


def modelclass(cls=None, /, *, name: str = None, init=True, repr=True, eq=True, order=False,
              unsafe_hash=False, frozen=False, storable: bool = False, plan: StoragePlan = None, **kwargs):
    
    def wrap(cls):
        return _process__modelclass(cls, name, init, repr, eq, order, unsafe_hash, frozen, storable, plan, **kwargs)

    # See if we're being called as @modelclass or @modelclass().
    if cls is None:
        # We're called with parens.
        return wrap

    # We're called as @modelclass without parens.
    return wrap(cls)


def _process__modelclass(cls, name, init, repr, eq, order, unsafe_hash, frozen, as_storable, plan, **kwargs):
    if plan is None:
        plan = StoragePlan(**kwargs)

    annotations: dict = cls.__dict__.get('__annotations__', dict())

    for k, v in annotations.items():
        if is_storable(v) and getattr(cls, k, None) is None:
            setattr(cls, k, recordfield(plan=plan))

    res = wrappedclass(cls, init=init, repr=repr, eq=eq, order=order, unsafe_hash=unsafe_hash, frozen=frozen)

    # assign serialize and deserialize methods
    if getattr(res, SERIALIZE, None) is None:
        setattr(res, SERIALIZE, _serialize__modelclass)
    if getattr(res, DESERIALIZE, None) is None:
        setattr(res, DESERIALIZE, _deserialize__modelclass)
        setattr(res, '_deserialize__dataclass__inner', _deserialize__dataclass__inner)

    result = serializable(res, name=name)
    if as_storable:
        result = storable(result, name=name)
    return result


def recordfields(obj):
    return getattr(obj, STO_FIELD, [])


def _serialize__modelclass(self, serializer: Serializer = None):
    res = dict()
    for f in fields(self):
        if f.name not in getattr(self, NO_SERIALIZE, []):
            value = getattr(self, f.name)
            if f.name in recordfields(self):
                recwrapper: RecordWrapper = getattr(self, attr_wrapper(f.name))
                res[f.name] = {RECORD_FIELD: True, **serialize(record(value, plan=recwrapper.plan), serializer)}
            else:
                res[f.name] = _serialize__dataclass__inner(value, serializer)
    
    return res


@classmethod
def _deserialize__modelclass(cls, serialized: dict, serializer: Serializer):
    processed = copy.deepcopy(serialized)
    for k, v in processed.items():
        if isinstance(v, dict) and v.get(RECORD_FIELD, False):
            rec = deserialize(v, serializer)
            processed[k] = getattr(rec, Record.PRIVATE_CONTENT)
        else:
            processed[k] = getattr(cls, '_deserialize__dataclass__inner')(v, serializer)

    return cls(**processed)



class _blist(list):
    def __init__(self, iterable: Iterable=None, plan: StoragePlan = None):
        if iterable is None: iterable = list()
        list.__init__(self, iterable)
        if plan is None: plan = StoragePlan()
        self.plan = plan
    
    def __getitem__(self, key):
        itm = list.__getitem__(self, key)
        if not isloaded(itm):
            itm = getattr(itm, LOAD)()
            list.__setitem__(self, key, itm)
        return itm
    
    def __serialize__(self, serializer: Serializer):
        res = {'plan': serialize(self.plan, serializer), 'list': []}
        for itm in self:
            if is_storable(itm):
                res['list'].append({RECORD_FIELD: True, **serialize(record(itm, plan=self.plan), serializer)})
            elif is_serializable(itm):
                res['list'].append(serialize(itm))
            else:
                res['list'].append(itm)
        return res
    
    @classmethod
    def __deserialize__(cls, serialized: dict, serializer: Serializer):
        plan = serialized.get('plan', StoragePlan())
        lst = serialized.get('list', list())
        res = cls(plan=plan)

        for itm in lst:
            if isinstance(itm, dict) and is_deserializable(itm):
                if itm.get(RECORD_FIELD, False):
                    rec = deserialize(itm, serializer)
                    res.append(getattr(rec, Record.PRIVATE_CONTENT))
                else:
                    res.append(deserialize(itm, serializer))
            else:
                res.append(itm)
        
        return res


@serializable(name='_ser__mlist')
class mlist(_blist):
    pass


@storable(name='_sto__mlist')
@serializable(name='_ser__smlist')
class smlist(mlist):
    pass
                

class _bdict(dict):
    def __init__(self, *, plan: StoragePlan = None, **kwargs):
        dict.__init__(self, **kwargs)
        if plan is None: plan = StoragePlan()
        self.plan = plan
    
    @classmethod
    def from_dict(cls, dict: dict, plan: StoragePlan = None):
        return cls.__init__(plan=plan, **dict)
    
    def __getitem__(self, key):
        itm = dict.__getitem__(self, key)
        if not isloaded(itm):
            itm = getattr(itm, LOAD)()
            dict.__setitem__(self, key, itm)
        return itm
    
    def __serialize__(self, serializer: Serializer):
        res = {'plan': serialize(self.plan, serializer), 'dict': {}}
        for k, v in self.items():
            if is_storable(v):
                res['dict'][k] = ({RECORD_FIELD: True, **serialize(record(v, plan=self.plan), serializer)})
            elif is_serializable(v):
                res['dict'][k] = serialize(v)
            else:
                res['dict'][k] = v
        return res
    
    @classmethod
    def __deserialize__(cls, serialized: dict, serializer: Serializer):
        plan = serialized.get('plan', StoragePlan())
        dct: dict = serialized.get('dict', list())
        res = cls(plan=plan)

        for k, v in dct.items():
            if isinstance(v, dict) and is_deserializable(v):
                if v.get(RECORD_FIELD, False):
                    rec = deserialize(v, serializer)
                    res[k] = getattr(rec, Record.PRIVATE_CONTENT)
                else:
                    res[k] = deserialize(v, serializer)
            else:
                res[k] = v
        
        return res


@serializable(name='_ser__mdict')
class mdict(_bdict):
    pass


@storable(name='_sto__smdict')
@serializable(name='_ser__smdict')
class smdict(_bdict):
    pass


if __name__ == '__main__':
    @modelclass(name='_tst__test', storable=True)
    class Test:
        value: str

    with StoringSerializer('out', config=StoringConfig(clean_on_open=True)) as srmain:
        with srmain.subdirectory('first', config=StoringConfig(gitkeep=True)) as sr:
            lst = mlist([1, 2, 3, Test('a'), Test('b')], plan=StoragePlan(preload=True))
            ser = serialize(lst, sr)
            print(json.dumps(ser, indent=4))
            lst_re = deserialize(ser, sr)
            print(lst_re)
            print(lst_re[-1])

            dct = mdict(a=5, b=3, c=Test('c'), d=Test('d'), plan=StoragePlan(preload=True))
            ser2 = serialize(dct, sr)
            print(json.dumps(ser2, indent=4))
            dct_re = deserialize(ser2, sr)
            print(dct_re)
            print(dct_re['c'])

            dct2 = smdict(**dct)
            rec0 = serialize(record(dct2, plan=StoragePlan(subdir='third', config=StoringConfig(gitkeep=False, store_on_close=True))), sr) # content_d4993d5c-75e8-4607-91ef-b47d6fec60e9
            print(json.dumps(rec0, indent=4))
            print(deserialize(rec0, sr).content)
            
        import numpy as np

        @storable(name='_tst__array')
        class Array(np.ndarray):
            def __write__(self, path):
                with open(path, 'wb') as f:
                    np.save(f, self)
            
            @classmethod
            def __read__(self, path):
                with open(path, 'rb') as f:
                    return np.load(f).view(Array)


        @modelclass(storable=True)
        class Foo:
            a: str
            b: Test = recordfield(preload=True)
            c: Array  # = recordfield() is automatically added for storables
            d: Test = field()  # if a field is serializable and storable you can avoid storage by making it a normal field
        
        rec1 = record(Test('hello'), plan=StoragePlan(preload=False, ignored=False))

        with srmain.subdirectory('second', config=StoringConfig(store_on_close=True)) as sr:
            ser0 = serialize(rec1, sr) 

            print(json.dumps(ser0, indent=4))
            res1: Record = deserialize(ser0, sr)
            print(res1)
            print(res1.content)

            foo = Foo('hello', Test('you'), np.eye(4).view(Array), Test('donotstore'))
            print(foo.b)
            print(foo.c)
            ser = serialize(foo, sr)
            print(json.dumps(ser, indent=4))

            res2: Foo = deserialize(ser, sr)
            print(res2)
            print(res2.b)
            print(res2.c)

            rec2 = record(foo, plan=StoragePlan(filename='foo.json'))
            ser2 = serialize(rec2, sr)
            print(ser2)
            res3: Record = deserialize(ser2, sr)
            print('final')
            print(res3.content)

            cnt: Foo = res3.content
            print(cnt.b)
            print(cnt.c)

    with StoringSerializer.from_path('out/second/serializer.json', config=StoringConfig(clean_on_open=False)) as sr:
        print(sr.directory)