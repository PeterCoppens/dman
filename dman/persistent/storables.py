import inspect
import os
import json
import uuid
import shutil

from dataclasses import dataclass, field, asdict, is_dataclass
from typing import Any, Set, Tuple
from smartdataclasses import wrappedclass, AUTO, overrideable, overridefield

from serializables import is_serializable, serializable, serialize, deserialize, Serializer

STO_TYPE = '_sto__type'
WRITE = '__write__'
READ = '__read__'
LOAD = '__load__'
GITIGNORE = '.gitignore'
GITKEEP = '.gitkeep'
PLAN_FIELD = '__plan__'

storable_types = dict()


def storable_type(obj):
    return getattr(obj, STO_TYPE, None)


def is_storable(obj):
    return storable_type(obj) in storable_types


def _default_serializable_plan():
    return StoragePlan(extension='.json')


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
            
            setattr(cls, PLAN_FIELD, 
                getattr(cls, PLAN_FIELD, _default_serializable_plan() << StoragePlan())
            )

        elif ignore_dataclass and is_dataclass(cls):
            if getattr(cls, WRITE, None) is None:                
                setattr(cls, WRITE, _write__dataclass)
            
            if getattr(cls, READ, None) is None:
                setattr(cls, READ, _read__dataclass)
            
            setattr(cls, PLAN_FIELD, 
                getattr(cls, PLAN_FIELD, _default_serializable_plan() << StoragePlan())
            )
            
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
@overrideable(frozen=True)
class StoragePlan:
    filename: str
    preload: bool
    ignored: bool
    subdir: str
    config: 'StoringConfig'
    extension: str


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


def record(content: object, /, *, plan: StoragePlan = None):
    if plan is None:
        plan = StoragePlan()
    
    suggested_plan = getattr(content, PLAN_FIELD, StoragePlan())
    return Record(content=content, plan=suggested_plan << plan)


@serializable(name='_sto__storing_config')
@overrideable
class StoringConfig:
    clean_on_open: bool
    store_on_close: bool
    gitkeep: bool

def _store_config_default():
    return StoringConfig(clean_on_open=False, store_on_close=False, gitkeep=False)

def _store_plan_default():
    return StoragePlan(
        filename='serializer', 
        preload=False,
        ignored=False,
        subdir=None,
        config=StoringConfig(),
        extension='.json'
    )

def _request_plan_default():
    return StoragePlan(
        filename=AUTO, 
        preload=False,
        ignored=False,
        subdir=None,
        config=StoringConfig(),
        extension='.dat'
    )


@storable(name='_sto__storing_serializer')
@serializable(name='_ser__storing_serializer')
@wrappedclass
class StoringSerializer(Serializer):
    directory: str = field(init=True, repr=True)

    config: StoringConfig = overridefield(default_factory=_store_config_default, repr=False)
    default_plan: StoragePlan = overridefield(default_factory=_request_plan_default, repr=False)
    parent: 'StoringSerializer' = field(default=None, repr=False)

    __plan__: StoragePlan = overridefield(default_factory=_store_plan_default, repr=False, init=False)

    __subdir_config__: StoringConfig = overridefield(default_factory=_store_config_default, repr=False)

    _is_open: bool = field(default=False, init=False)
    _opened_parent: bool = field(default= False, init=False)

    _gitignore: Set[str] = field(default_factory=set, init=False, repr=False)

    __no_serialize__ = ['_is_open', '_opened_parent', '_gitignore', '__plan__', '__subdir_config__']

    @classmethod
    def from_path(cls, path, config: StoringConfig = None, default_plan: StoragePlan = None):
        res: cls = read(getattr(cls, STO_TYPE), path)
        if config is not None:
            res.config = res.config << config
        if default_plan is not None:
            res.default_plan = res.default_plan << default_plan

        return res
    
    def subdirectory(self, subdirectory: str, *, plan: StoragePlan = None, default_plan: StoragePlan = None, config: StoringConfig = None):
        if default_plan is None: default_plan = StoragePlan()
        if config is None: config = StoringConfig()
        if plan is None: plan = StoragePlan()

        target, _ = self.request(self.default_plan << plan << StoragePlan(filename=subdirectory, extension=''))
        return type(self)(
            directory=target, 
            parent=self, 
            config=self.config << config << StoringConfig(clean_on_open=False), 
            default_plan=self.default_plan << default_plan
        )

    def request(self, plan: StoragePlan) -> Tuple[str, StoragePlan]:
        fplan: StoragePlan = self.default_plan << StoragePlan(filename=f'content_{uuid.uuid4()}') << plan

        if fplan.subdir is not None:
            subplan: StoragePlan = StoragePlan(config=StoringConfig()) << plan << StoragePlan(subdir=None)
            
            with self.subdirectory(plan.subdir, config=subplan.config) as sr:
                path, resplan = sr.request(subplan)
                return path, resplan << StoragePlan(subdir=plan.subdir)
        
        path = fplan.filename + fplan.extension
        if fplan.ignored:
            self._gitignore.add(path)
        elif fplan.filename in self._gitignore:
            self._gitignore.remove(path)

        return os.path.join(self.directory, path), fplan
    
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

        if self.parent is not None and not self.parent._is_open:
            self.parent.config = self.parent.config << StoringConfig(clean_on_open=self.config.clean_on_open)
            self.parent.open()
            self._opened_parent = True

        if not os.path.exists(self.directory):
            os.makedirs(self.directory)
        
        if self.config.clean_on_open:
            self.clean()

        if os.path.exists(self.ignore_path):
            with open(self.ignore_path, 'r') as f:
                self._gitignore = set([line[:-1] for line in f.readlines()])
        
        self._is_open = True
        
    def close(self):
        if not self._is_open: 
            return

        if self.config.store_on_close:
            rec = record(self)
            serialize(rec, self)
        
        if len(self._gitignore) > 0:
            self._gitignore.add('.gitignore')
            with open(self.ignore_path, 'w') as f:
                f.writelines((line + '\n' for line in self._gitignore))
            
        if self.config.gitkeep and not os.path.exists(self.keep_path):
            with open(self.keep_path, 'w') as f:
                pass
        
        self._is_open = False
        
        if self._opened_parent:
            self.parent.close()

    def __enter__(self):
        self.open()
        return self
    
    def __exit__(self, exception_type, exception_value, traceback):
        self.close()