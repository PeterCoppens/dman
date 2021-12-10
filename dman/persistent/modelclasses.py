import copy

from typing import Iterable
from dataclasses import MISSING, fields

from dman.persistent.smartdataclasses import Wrapper, wrappedclass, WrappedField, attr_wrapper, attr_wrapped_field
from dman.persistent.storeables import is_storeable, storeable
from dman.persistent.record import Record, Unloaded, is_unloaded, record
from dman.persistent.context import Context, ContextCommand
from dman.persistent.serializables import SERIALIZE, DESERIALIZE, _deserialize__dataclass__inner, _serialize__dataclass__inner, NO_SERIALIZE
from dman.persistent.serializables import BaseContext, serialize, deserialize, is_serializable, is_deserializable, serializable


STO_FIELD = '_record__fields'
RECORD_FIELD = '_record__field'


class RecordWrapper(Wrapper):
    WRAPPED_FIELDS_NAME = STO_FIELD

    def __init__(self, command: ContextCommand) -> None:
        self.command = command

    def __process__(self, obj, wrapped):
        if wrapped is None:
            return None
            
        if is_unloaded(wrapped):
            ul: Unloaded = wrapped
            wrapped = ul.__load__()
        return wrapped
    
    def __store_process__(self, obj, processed):
        return processed


def recordfield(*, default=MISSING, default_factory=MISSING, 
        init: bool = True, repr: bool = False, 
        hash: bool = False, compare: bool = False, metadata=None,
        command: ContextCommand = None
    ):

    if command is None: command = ContextCommand()

    return WrappedField(
        RecordWrapper(command=command),
        default=default, default_factory=default_factory, 
        init=init, repr=repr, hash=hash, 
        compare=compare, metadata=metadata
    )


def modelclass(cls=None, /, *, name: str = None, init=True, repr=True, eq=True, order=False,
              unsafe_hash=False, frozen=False, storeable: bool = False, command: ContextCommand = None, **kwargs):
    
    def wrap(cls):
        return _process__modelclass(cls, name, init, repr, eq, order, unsafe_hash, frozen, storeable, command, **kwargs)

    # See if we're being called as @modelclass or @modelclass().
    if cls is None:
        # We're called with parens.
        return wrap

    # We're called as @modelclass without parens.
    return wrap(cls)


def _process__modelclass(cls, name, init, repr, eq, order, unsafe_hash, frozen, as_storeable, command, **kwargs):
    if command is None:
        command = ContextCommand(**kwargs)

    annotations: dict = cls.__dict__.get('__annotations__', dict())

    for k, v in annotations.items():
        if is_storeable(v) and getattr(cls, k, None) is None:
            setattr(cls, k, recordfield(command=command))

    res = wrappedclass(cls, init=init, repr=repr, eq=eq, order=order, unsafe_hash=unsafe_hash, frozen=frozen)

    # assign serialize and deserialize methods
    if getattr(res, SERIALIZE, None) is None:
        setattr(res, SERIALIZE, _serialize__modelclass)
    if getattr(res, DESERIALIZE, None) is None:
        setattr(res, DESERIALIZE, _deserialize__modelclass)
        setattr(res, '_deserialize__dataclass__inner', _deserialize__dataclass__inner)

    result = serializable(res, name=name)
    if as_storeable:
        result = storeable(result, name=name)
    return result


def recordfields(obj):
    return getattr(obj, STO_FIELD, [])


def _serialize__modelclass(self, serializer: BaseContext = None):
    res = dict()
    for f in fields(self):
        if f.name not in getattr(self, NO_SERIALIZE, []):
            if f.name in recordfields(self):
                value = getattr(self, attr_wrapped_field(f.name))      # wrap the private value
                recwrapper: RecordWrapper = getattr(self, attr_wrapper(f.name))
                res[f.name] = {RECORD_FIELD: True, **serialize(record(value, command=recwrapper.command), serializer)}
            else:
                res[f.name] = _serialize__dataclass__inner(getattr(self, f.name), serializer)
    
    return res


@classmethod
def _deserialize__modelclass(cls, serialized: dict, serializer: BaseContext):
    processed = copy.deepcopy(serialized)
    for k, v in processed.items():
        if isinstance(v, dict) and v.get(RECORD_FIELD, False):
            rec: Record = deserialize(v, serializer)
            processed[k] = rec._content
        else:
            processed[k] = getattr(cls, '_deserialize__dataclass__inner')(v, serializer)

    return cls(**processed)



class _blist(list):
    def __init__(self, iterable: Iterable=None, command: ContextCommand = None):
        if iterable is None: iterable = list()
        list.__init__(self, iterable)
        if command is None: command = ContextCommand()
        self.command = command
    
    def __repr__(self):
        lst = []
        for i in range(len(self)):
            lst.append(list.__getitem__(self, i))
        
        return list.__repr__(lst)
    
    def __getitem__(self, key):
        itm = list.__getitem__(self, key)
        if is_unloaded(itm):
            ul: Unloaded = itm
            itm = ul.__load__()
            list.__setitem__(self, key, itm)
        return itm
    
    def __serialize__(self, serializer: BaseContext):
        res = {'command': serialize(self.command, serializer), 'list': []}
        for itm in self:
            if is_storeable(itm):
                res['list'].append({RECORD_FIELD: True, **serialize(record(itm, command=self.command), serializer)})
            elif is_serializable(itm):
                res['list'].append(serialize(itm))
            else:
                res['list'].append(itm)
        return res
    
    @classmethod
    def __deserialize__(cls, serialized: dict, serializer: BaseContext):
        command = serialized.get('command', ContextCommand())
        if isinstance(command, dict):
            command = deserialize(command, serializer)

        lst = serialized.get('list', list())
        res = cls(command=command)

        for itm in lst:
            if isinstance(itm, dict) and is_deserializable(itm):
                if itm.get(RECORD_FIELD, False):
                    rec: Record = deserialize(itm, serializer)
                    res.append(rec._content)
                else:
                    res.append(deserialize(itm, serializer))
            else:
                res.append(itm)
        
        return res


@serializable(name='_ser__mlist')
class mlist(_blist):
    pass


@storeable(name='_sto__mlist')
@serializable(name='_ser__smlist')
class smlist(mlist):
    pass
                

class _bdict(dict):
    def __init__(self, *, command: ContextCommand = None, **kwargs):
        dict.__init__(self, **kwargs)
        if command is None: command = ContextCommand()
        self.command = command
        self._store_by_key = False
    
    def store_by_key(self, in_subfolder: bool = False):
        self._store_by_key = True
        self._store_in_subfolder = in_subfolder
    
    def __repr__(self):
        dct = {}
        for k in self.keys():
            dct[k] = dict.__getitem__(self, k)
        
        return dict.__repr__(dct)
    
    @classmethod
    def from_dict(cls, dict: dict, command: ContextCommand = None):
        return cls.__init__(command=command, **dict)
    
    def __getitem__(self, key):
        itm = dict.__getitem__(self, key)
        if is_unloaded(itm):
            ul: Unloaded = itm
            itm = ul.__load__()
            dict.__setitem__(self, key, itm)
        return itm
    
    def store_by_key(self):
        self._store_by_key = True

    def __key_command__(self, k):
        if self._store_by_key:
            return ContextCommand(filename=k)
        return ContextCommand()
    
    def __serialize__(self, serializer: BaseContext):
        res = {'command': serialize(self.command, serializer), 'dict': {}}
        for k in self.keys():
            v = dict.__getitem__(self, k)
            if is_unloaded(v) or is_storeable(v):
                key_command = self.__key_command__(k)
                res['dict'][k] = ({RECORD_FIELD: True, **serialize(record(v, command=self.command << key_command), serializer)})
            elif is_serializable(v):
                res['dict'][k] = serialize(v)
            else:
                res['dict'][k] = v
        return res
    
    @classmethod
    def __deserialize__(cls, serialized: dict, serializer: BaseContext):
        command = serialized.get('command', ContextCommand())
        if isinstance(command, dict):
            command = deserialize(command, serializer)

        dct: dict = serialized.get('dict', list())
        res = cls(command=command)

        for k, v in dct.items():
            if isinstance(v, dict) and is_deserializable(v):
                if v.get(RECORD_FIELD, False):
                    rec: Record = deserialize(v, serializer)
                    res[k] = rec._content
                else:
                    res[k] = deserialize(v, serializer)
            else:
                res[k] = v
        
        return res


@serializable(name='_ser__mdict')
class mdict(_bdict):
    pass


@storeable(name='_sto__smdict')
@serializable(name='_ser__smdict')
class smdict(_bdict):
    pass