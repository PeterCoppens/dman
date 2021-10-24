import copy
import inspect
import os
import json
import uuid
import shutil

from dataclasses import MISSING, dataclass, field, asdict, Field, fields, is_dataclass
from typing import Any, Iterable, List, Optional, Set, Tuple
from wrapped import WrappedField, Wrapper, attr_wrapper, wrappedclass

from serializables import DESERIALIZE, NO_SERIALIZE, SERIALIZE, is_deserializable, is_serializable, serializable, serialize, deserialize, Serializer
from serializables import _deserialize__dataclass__inner, _serialize__dataclass__inner

STO_TYPE = '_sto__type'
WRITE = '__write__'
READ = '__read__'
LOAD = '__load__'
STO_FIELD = '_record__fields'
RECORD_FIELD = '_record__field'
GITIGNORE = '.gitignore'
GITKEEP = '.gitkeep'

storable_types = dict()


def storable_type(obj):
    return getattr(obj, STO_TYPE, None)


def is_storable(obj):
    return storable_type(obj) in storable_types


def storable(cls=None, /, *, name: str = None, ignore_serializable: bool = None, ignore_dataclass: bool = False):
    def wrap(cls):
        local_name = name
        if local_name is None: 
            local_name = str(cls)

        setattr(cls, STO_TYPE, local_name)
        storable_types[local_name] = cls

        if not ignore_serializable and is_serializable(cls):
            if getattr(cls, WRITE, None) is None:                
                setattr(cls, WRITE, _write__serializable)
            
            if getattr(cls, READ, None) is None:
                setattr(cls, READ, _read__serializable)

        elif ignore_dataclass and is_dataclass(cls):
            if getattr(cls, WRITE, None) is None:                
                setattr(cls, WRITE, _write__dataclass)
            
            if getattr(cls, READ, None) is None:
                setattr(cls, READ, _read__dataclass)
            
        return cls

    # See if we're being called as @storable or @storable().
    if cls is None:
        # We're called with parens.
        return wrap

    # We're called as @storable without parens.
    return wrap(cls)

def _write__dataclass(self, path: str):
    with open(path, 'w') as f:
        json.dump(asdict(self), f, indent=4)

@classmethod
def _read__dataclass(cls, path: str):
    with open(path, 'r') as f:
        return cls(**json.load(f))

def _write__serializable(self, path: str, serializer: Serializer = None):
    with open(path, 'w') as f:
        serialized = serialize(self, serializer)
        json.dump(serialized, f, indent=4)
    
@classmethod
def _read__serializable(cls, path: str, serializer: Serializer = None):
    with open(path, 'r') as f:
        return deserialize(json.load(f), serializer)


def write(storable, path: str, serializer: Serializer = None):
    if isinstance(storable, Unloaded):
        return

    inner_write = getattr(storable, WRITE, None)
    if inner_write is None:
        return

    sig = inspect.signature(inner_write)
    if len(sig.parameters) == 1:
        inner_write(path)
    elif len(sig.parameters) == 2:
        if serializer is None: serializer = Serializer
        inner_write(path, serializer)
    else:
        raise ValueError(f'object has invalid signature for method {WRITE}')


def read(type: str, path: str, preload: bool = True, serializer: Serializer = None):
    if not preload:
        return Unloaded(type, path, serializer)

    storable = storable_types.get(type, None)
    if storable is None:
        raise ValueError(f'type {type} is not registered as a storable type')

    inner_read = getattr(storable, READ, None)
    if inner_read is None:
        return None
        
    sig = inspect.signature(inner_read)
    if len(sig.parameters) == 1:
        return inner_read(path)
    elif len(sig.parameters) == 2:
        if serializer is None: serializer = Serializer
        return inner_read(path, serializer)
    else:
        raise ValueError(f'object has invalid signature for method {WRITE}')


def isloaded(obj):
    if isinstance(obj, Unloaded):
        return False
    if not is_storable(obj):
        raise ValueError(f'{obj} is not registered as a storable type')
    return True


@dataclass
class Unloaded:
    type: str
    path: str
    serializer: Serializer = field(default=None, repr=False)

    def __load__(self):
        print(f'loading {self}')
        return read(type=self.type, path=self.path, serializer=self.serializer)


@serializable(name='_sto__storage_plan')
@dataclass
class StoragePlan:
    filename: str = field(default=None)
    preload: bool = field(default=False)
    ignored: bool = field(default=True)
    subdir: str = field(default=None)
    gitkeep: bool = field(default=None)


@serializable(name='_sto__record')
@dataclass
class Record:
    RECORD_PLAN = '_record__plan'
    RECORD_CONTENT = '_record__content'
    PRIVATE_CONTENT = '_content'

    content: Any
    plan: StoragePlan = field(default_factory=StoragePlan)
    
    def __repr__(self) -> str:
        content = getattr(self, Record.PRIVATE_CONTENT, None)
        if content is None:
            return f'Record(content=None, plan={self.plan}'
        if not isloaded(content):
            return f'Record(content={content}, plan={self.plan})'
        
        return f'Record(content={storable_type(content)}, plan={self.plan})'
    
    def __serialize__(self, serializer: Serializer):
        plan = self.plan
        content = getattr(self, Record.PRIVATE_CONTENT)
        if isinstance(serializer, StoringSerializer):
            path, plan = serializer.request(plan)
            write(content, path, serializer)

        return {
            Record.RECORD_PLAN: serialize(plan, serializer),
            Record.RECORD_CONTENT: storable_type(content)
        }

    @classmethod
    def __deserialize__(cls, serialized: dict, serializer: Serializer):
        plan: StoragePlan = deserialize(serialized.get(Record.RECORD_PLAN, None), serializer)

        sto_type = serialized.get(Record.RECORD_CONTENT, None)
        if sto_type not in storable_types:
            raise ValueError('record does not contain storable type.')

        content = None
        if isinstance(serializer, StoringSerializer):
            path, plan = serializer.request(plan)
            content = read(sto_type, path, preload=plan.preload, serializer=serializer)

        return cls(plan=plan, content=content)

def _record_content_get(self: Record):
    content = getattr(self, Record.PRIVATE_CONTENT, None)
    if not isloaded(content):
        content = getattr(content, LOAD)()
        setattr(self, Record.PRIVATE_CONTENT, content)
    return content

def _record_content_set(self: Record, value):
    setattr(self, Record.PRIVATE_CONTENT, value)

setattr(Record, 'content', property(_record_content_get, _record_content_set))


def record(content: object, /, *, plan: StoragePlan = None, 
        filename: str = None, preload: bool = False, ignored: bool = True, 
        subdir: str = None, gitkeep: bool = None
    ):
    if plan is None:
        plan = StoragePlan(filename, preload, ignored, subdir, gitkeep)
    return Record(content=content, plan=plan)


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


@modelclass(name='_sto__storing_serializer', storable=True)
class StoringSerializer(Serializer):
    DEFAULT_FILENAME = 'serializer.json'

    directory: str
    clean_on_open: bool = field(default=False)
    store_on_close: bool = field(default=False)
    plan: StoragePlan = field(default=None)
    gitkeep: bool = field(default=False)

    _parent: 'StoringSerializer' = field(default=None, repr=False)
    _is_open: bool = field(default=False, init=False)
    _opened_parent: bool = field(default= False, init=False)

    _gitignore: Set[str] = field(default_factory=set, init=False, repr=False)

    __no_serialize__ = ['_is_open', '_opened_parent', '_gitignore']

    @classmethod
    def from_path(cls, path, clean_on_open: bool = None, store_on_close: bool = None, plan: StoragePlan = None):
        res: cls = read(getattr(cls, STO_TYPE), path)
        if clean_on_open is not None: res.clean_on_open = clean_on_open
        if store_on_close is not None: res.store_on_close = store_on_close
        if plan is not None: res.plan = plan

        return res
    
    def subdirectory(self, subdirectory: str, ignored: bool = None, clean_on_open: bool = None, store_on_close: bool = None, gitkeep: bool = None, plan: StoragePlan = None):
        if clean_on_open is None: clean_on_open = self.clean_on_open
        if store_on_close is None: store_on_close = self.store_on_close
        if plan is None: plan = self.plan
        if gitkeep is None: gitkeep = self.gitkeep

        target, _ = self.request(StoragePlan(filename=subdirectory, ignored=ignored))
        return type(self)(
            directory=target, 
            clean_on_open=clean_on_open, 
            store_on_close=store_on_close, 
            plan=plan,
            gitkeep=gitkeep,
            _parent=self
        )

    def request(self, plan: StoragePlan) -> Tuple[str, StoragePlan]:
        if plan.subdir is not None:
            sub_plan = copy.deepcopy(plan)
            subdir, sub_plan.subdir = sub_plan.subdir, None
            with self.subdirectory(subdir, clean_on_open=False, gitkeep=sub_plan.gitkeep) as sr:
                path, res_plan = sr.request(sub_plan)
                res_plan.subdir = subdir
                return path, res_plan

        plan = copy.deepcopy(plan)
        filename = plan.filename
        if filename is None:
            filename = f'content_{uuid.uuid4()}'
            plan.filename = filename
        
        if plan.ignored:
            self._gitignore.add(filename)
        elif filename in self._gitignore:
            self._gitignore.remove(filename)

        return os.path.join(self.directory, filename), plan
    
    @property
    def ignore_path(self):
        return os.path.join(self.directory, GITIGNORE)
    
    @property
    def keep_path(self):
        return os.path.join(self.directory, GITKEEP)
    
    def clean(self):
        shutil.rmtree(self.directory)
        os.makedirs(self.directory)
    
    def open(self):
        if self._is_open:
            return 

        if self._parent is not None and not self._parent._is_open:
            self._parent.clean_on_open = self.clean_on_open
            self._parent.open()
            self._opened_parent = True

        if not os.path.exists(self.directory):
            os.makedirs(self.directory)
        
        if self.clean_on_open:
            self.clean()

        if os.path.exists(self.ignore_path):
            with open(self.ignore_path, 'r') as f:
                self._gitignore = set([line[:-1] for line in f.readlines()])
        
        self._is_open = True
        
    def close(self):
        if not self._is_open: 
            return

        if self.store_on_close:
            if self.plan is None:
                self.plan = StoragePlan(filename=self.DEFAULT_FILENAME)
            path, self.plan = self.request(self.plan)
            write(self, path, self)
        
        if len(self._gitignore) > 0:
            self._gitignore.add('.gitignore')
            with open(self.ignore_path, 'w') as f:
                f.writelines((line + '\n' for line in self._gitignore))
            
        if self.gitkeep and not os.path.exists(self.keep_path):
            with open(self.keep_path, 'w') as f:
                pass
        
        self._is_open = False
        
        if self._opened_parent:
            self._parent.close()

    def __enter__(self):
        self.open()
        return self
    
    def __exit__(self, exception_type, exception_value, traceback):
        self.close()


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

    with StoringSerializer('out', clean_on_open=True) as srmain:
        with srmain.subdirectory('first', gitkeep=True) as sr:
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
            rec0 = serialize(record(dct2, subdir='third', gitkeep=False), sr)
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
        
        rec1 = record(Test('hello'), preload=False, ignored=False)

        with srmain.subdirectory('second', store_on_close=True) as sr:
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

            rec2 = record(foo, filename='foo.json')
            ser2 = serialize(rec2, sr)
            print(ser2)
            res3: Record = deserialize(ser2, sr)
            print('final')
            print(res3.content)

            cnt: Foo = res3.content
            print(cnt.b)
            print(cnt.c)

    with StoringSerializer.from_path('out/second/serializer.json', clean_on_open=False) as sr:
        print(sr.directory)