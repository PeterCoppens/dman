import inspect
import json

from dataclasses import asdict, is_dataclass
from os import PathLike
from typing import Any

from dman.persistent.serializables import is_serializable, serialize, deserialize, BaseContext

STO_TYPE = '_sto__type'
WRITE = '__write__'
READ = '__read__'
LOAD = '__load__'

storeable_types = dict()


def storeable_type(obj):
    return getattr(obj, STO_TYPE, None)


def is_storeable(obj):
    return storeable_type(obj) in storeable_types


def is_storeable_type(type: str):
    return type in storeable_types


def storeable(cls=None, /, *, name: str = None, ignore_serializable: bool = None, ignore_dataclass: bool = False):
    def wrap(cls):
        local_name = name
        if local_name is None: 
            local_name = str(cls)

        setattr(cls, STO_TYPE, local_name)
        storeable_types[local_name] = cls

        if not ignore_serializable and is_serializable(cls):
            if getattr(cls, WRITE, None) is None:                
                setattr(cls, WRITE, _write__serializable)
            
            if getattr(cls, READ, None) is None:
                setattr(cls, READ, _read__serializable)

        elif not ignore_dataclass and is_dataclass(cls):
            if getattr(cls, WRITE, None) is None:                
                setattr(cls, WRITE, _write__dataclass)
            
            if getattr(cls, READ, None) is None:
                setattr(cls, READ, _read__dataclass)
            
        return cls

    # See if we're being called as @storeable or @storeable().
    if cls is None:
        # We're called with parens.
        return wrap

    # We're called as @storeable without parens.
    return wrap(cls)


def _write__dataclass(self, path: PathLike):
    with open(path, 'w') as f:
        json.dump(asdict(self), f, indent=4)


@classmethod
def _read__dataclass(cls, path: PathLike):
    with open(path, 'r') as f:
        return cls(**json.load(f))


def _write__serializable(self, path: PathLike, context: BaseContext = None):
    with open(path, 'w') as f:
        serialized = serialize(self, context)
        json.dump(serialized, f, indent=4)
    
    
@classmethod
def _read__serializable(_, path: PathLike, context: BaseContext = None):
    with open(path, 'r') as f:
        serialized = json.load(f)
        return deserialize(serialized, context)


def write(storeable, path: PathLike, context: BaseContext = None):
    inner_write = getattr(storeable, WRITE, None)
    if inner_write is None:
        return

    sig = inspect.signature(inner_write)
    if len(sig.parameters) == 1:
        inner_write(path)
    elif len(sig.parameters) == 2:
        if context is None: context = BaseContext
        inner_write(path, context)
    else:
        raise ValueError(f'object has invalid signature for method {WRITE}')


def read(type: str, path: PathLike, context: BaseContext = None):
    # if not preload:
    #     return Unloaded(type, path, context)

    storeable = storeable_types.get(type, None)
    if storeable is None:
        raise ValueError(f'type {type} is not registered as a storeable type')

    inner_read = getattr(storeable, READ, None)
    if inner_read is None:
        return None
        
    sig = inspect.signature(inner_read)
    if len(sig.parameters) == 1:
        return inner_read(path)
    elif len(sig.parameters) == 2:
        if context is None: context = BaseContext
        return inner_read(path, context)
    else:
        raise ValueError(f'object has invalid signature for method {WRITE}')


# def isunloaded(obj):
#     return isinstance(obj, Unloaded)


# @dataclass
# class Unloaded:
#     type: str
#     context: 'StoringContext' = field(default=None, repr=False)

#     def __load__(self):
#         print(f'loading {self}')
#         return self.context.read(storeable_type=self.type)
    
#     @property
#     def path(self):
#         return self.context.path



# @serializable(name='_sto__record')
# @dataclass
# class Record:
#     RECORD_PLAN = '_record__plan'
#     RECORD_CONTENT = '_record__content'
#     PRIVATE_CONTENT = '_content'

#     content: Any
#     plan: StoragePlan = field(default_factory=StoragePlan)
    
#     def __repr__(self) -> str:
#         content = getattr(self, Record.PRIVATE_CONTENT, None)
#         if content is None:
#             return f'Record(content=None, plan={self.plan}'
#         if isunloaded(content):
#             return f'Record(content={content}, plan={self.plan})'
        
#         return f'Record(content={storeable_type(content)}, plan={self.plan})'
    
#     def __serialize__(self, serializer: BaseContext):
#         plan = self.plan
#         content = getattr(self, Record.PRIVATE_CONTENT)
#         content_type = storeable_type(content)
#         if not isunloaded(content) and isinstance(serializer, StoringSerializer):
#             req = serializer.request(plan)
#             plan = req.plan
#             req.write(content)
        
#         if isunloaded(content):
#             unloaded: Unloaded = content
#             plan = plan << StoragePlan(unloaded.path)
#             content_type = unloaded.type

#         return {
#             Record.RECORD_PLAN: serialize(plan, serializer),
#             Record.RECORD_CONTENT: content_type
#         }

#     @classmethod
#     def __deserialize__(cls, serialized: dict, serializer: BaseContext):
#         plan: StoragePlan = deserialize(serialized.get(Record.RECORD_PLAN, None), serializer)

#         sto_type = serialized.get(Record.RECORD_CONTENT, None)
#         if sto_type not in storeable_types:
#             raise ValueError('record does not contain storeable type.')

#         content = None
#         if isinstance(serializer, StoringSerializer):
#             req = serializer.request(plan)
#             content = req.read(sto_type)

#         return cls(plan=plan, content=content)

# def _record_content_get(self: Record):
#     content = getattr(self, Record.PRIVATE_CONTENT, None)
#     if isunloaded(content):
#         content = getattr(content, LOAD)()
#         setattr(self, Record.PRIVATE_CONTENT, content)
#     return content

# def _record_content_set(self: Record, value):
#     setattr(self, Record.PRIVATE_CONTENT, value)

# setattr(Record, 'content', property(_record_content_get, _record_content_set))


# def record(content: object, /, *, plan: StoragePlan = None):
#     if plan is None:
#         plan = StoragePlan()
    
#     suggested_plan = getattr(content, PLAN_FIELD, StoragePlan())
#     return Record(content=content, plan=suggested_plan << plan)


