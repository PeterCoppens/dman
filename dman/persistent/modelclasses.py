from collections.abc import MutableMapping
from collections.abc import MutableSequence
import copy
import os

from typing import Iterable
from dataclasses import MISSING, fields

from dman.utils.smartdataclasses import AUTO, NO_STORE, Wrapper, wrappedclass, WrappedField, attr_wrapper, attr_wrapped_field
from dman.persistent.storables import is_storable, storable
from dman.persistent.record import Record, RecordConfig, record, REMOVE, remove
from dman.persistent.serializables import SERIALIZE, DESERIALIZE, NO_SERIALIZE
from dman.persistent.serializables import BaseContext, serialize, deserialize, is_serializable, is_deserializable, serializable


STO_FIELD = '_record__fields'
RECORD_FIELD = '__record__'
MODELCLASS = '__modelclass__'


class RecordWrapper(Wrapper):
    WRAPPED_FIELDS_NAME = STO_FIELD

    def __init__(self, stem: str, suffix: str, name: str, subdir: os.PathLike, preload: str):
        self.stem = stem
        self.suffix = suffix
        self.name = name
        self.subdir = subdir
        self.preload = preload

    def build(self, content):
        return record(content, stem=self.stem, suffix=self.suffix, name=self.name, subdir=self.subdir, preload=self.preload)

    def __process__(self, obj, wrapped):
        if wrapped is None:
            return None

        if isinstance(wrapped, Record):
            return wrapped.content

        return wrapped

    def __store__(self, obj, value, currentvalue):
        if is_storable(value):
            if isinstance(currentvalue, Record):
                currentvalue.content = value
                return NO_STORE
            return self.build(value)
        else:
            return value


def recordfield(*, default=MISSING, default_factory=MISSING,
                init: bool = True, repr: bool = False,
                hash: bool = False, compare: bool = False, metadata=None,
                stem: str = AUTO, suffix: str = AUTO, name: str = AUTO, subdir: os.PathLike = '', preload: str = False
                ):

    return WrappedField(
        RecordWrapper(stem=stem, suffix=suffix, name=name,
                      subdir=subdir, preload=preload),
        default=default, default_factory=default_factory,
        init=init, repr=repr, hash=hash,
        compare=compare, metadata=metadata
    )


def modelclass(cls=None, /, *, name: str = None, init=True, repr=True, eq=True, order=False,
               unsafe_hash=False, frozen=False, storable: bool = False, compact: bool = False, **kwargs):

    def wrap(cls):
        return _process__modelclass(cls, name, init, repr, eq, order, unsafe_hash, frozen, storable, compact, **kwargs)

    # See if we're being called as @modelclass or @modelclass().
    if cls is None:
        # We're called with parens.
        return wrap

    # We're called as @modelclass without parens.
    return wrap(cls)


def is_modelclass(cls):
    return getattr(cls, MODELCLASS, False)


def _process__modelclass(cls, name, init, repr, eq, order, unsafe_hash, frozen, as_storable, compact, **kwargs):
    annotations: dict = cls.__dict__
    annotations: dict = annotations.get('__annotations__', dict())

    for k, v in annotations.items():
        if is_storable(v) and getattr(cls, k, None) is None:
            setattr(cls, k, recordfield())

    res = wrappedclass(cls, init=init, repr=repr, eq=eq,
                       order=order, unsafe_hash=unsafe_hash, frozen=frozen)

    # assign serialize and deserialize methods
    ser, dser = _serialize__modelclass, _deserialize__modelclass
    if compact:
        ser, dser = _serialize__modelclass_content_only, _deserialize__modelclass_content_only

    setattr(res, MODELCLASS, True)
    if getattr(res, REMOVE, None) is None:
        setattr(res, REMOVE, _remove__modelclass)
    if getattr(res, SERIALIZE, None) is None:
        setattr(res, SERIALIZE, ser)
    if getattr(res, DESERIALIZE, None) is None:
        setattr(res, DESERIALIZE, dser)

    result = serializable(res, name=name)
    if as_storable:
        result = storable(result, name=name)
    return result


def recordfields(obj):
    return getattr(obj, STO_FIELD, [])


def _remove__modelclass(self, context: BaseContext = None):
    for f in fields(self):
        if f.name not in getattr(self, NO_SERIALIZE, []):
            if f.name in recordfields(self):
                value = getattr(self, attr_wrapped_field(f.name))
                remove(value, context)
            else:
                value = getattr(self, f.name)
                remove(value, context)


def _serialize__modelclass_content_only(self, context: BaseContext = None):
    res = dict()
    for f in fields(self):
        if f.name not in getattr(self, NO_SERIALIZE, []):
            if f.name in recordfields(self):
                value = getattr(self, attr_wrapped_field(f.name))
            else:
                value = getattr(self, f.name)        
            res[f.name] = serialize(value, context, content_only=True)

    return res


@classmethod
def _deserialize__modelclass_content_only(cls, serialized: dict, context: BaseContext):
    processed = dict()
    for f in fields(cls):
        value = serialized.get(f.name, None)
        if value is None:
            continue
        processed[f.name] = deserialize(value, context, ser_type=f.type)

    return cls(**processed)


def _serialize__modelclass(self, context: BaseContext = None):
    res = dict()
    for f in fields(self):
        if f.name not in getattr(self, NO_SERIALIZE, []):
            if f.name in recordfields(self):
                value = getattr(self, attr_wrapped_field(f.name))
            else:
                value = getattr(self, f.name)
            res[f.name] = serialize(value, context)
                    
    return res


@classmethod
def _deserialize__modelclass(cls, serialized: dict, context: BaseContext):
    processed = dict()
    for k, v in serialized.items():
        processed[k] = deserialize(v, context)

    return cls(**processed)


def is_model(cls):
    return isinstance(cls, (_blist, _bdict)) or is_modelclass(cls) or isinstance(cls, Record)


class _blist(MutableSequence):
    def __init__(self, iterable: Iterable = None, subdir: os.PathLike = '', preload: bool = False, auto_clean: bool = False):
        """
        Create an instance of this model list.

        :param iterable: Initial content of the list.
        :param str subdir: Specify the default sub-subdirectory for storables.
        :param bool preload: Specify whether storables should be preloaded.
        :param bool auto_clean: Automatically remove records with dangling pointers on serialization.
        """
        self.subdir = subdir
        self.preload = preload
        self.auto_clean = auto_clean

        if iterable is None:
            iterable = list()
        
        self.store = list()
        for itm in iterable:
            self.append(itm)
        self.unused = list()

    def __repr__(self):
        lst = []
        for i in range(len(self)):
            res = self.store.__getitem__(i)
            if isinstance(res, Record):
                res = res._content
            lst.append(res)

        return list.__repr__(lst)

    def __make_record__(self, itm):
        return record(itm, subdir=self.subdir, preload=self.preload)

    def __serialize__(self, context: BaseContext):
        lst = []

        res = {'store': lst}
        if self.subdir != '':
            res['subdir'] = self.subdir
        if self.preload:
            res['preload'] = self.preload
        if self.auto_clean:
            res['auto_clean'] = self.auto_clean

        for itm in self.unused:
            remove(itm, context)
        self.unused = []

        for itm in self:
            if isinstance(itm, Record):
                if not self.auto_clean or itm.exists():
                    lst.append(serialize(itm, context))
                else:
                    self.unused.append(itm)
            else:
                lst.append(serialize(itm, context))

        for itm in self.unused:
            remove(itm, context)
        self.unused = []

        return res

    @classmethod
    def __deserialize__(cls, serialized: dict, context: BaseContext):
        subdir = serialized.get('subdir', '')
        preload = serialized.get('preload', False)
        auto_clean = serialized.get('auto_clean', False)

        lst = serialized.get('store', list())
        res = cls(subdir=subdir, preload=preload, auto_clean=auto_clean)

        for itm in lst:
            res.append(deserialize(itm, context))

        return res

    def record(self, value, idx: int = None, /, *, name: str = None, subdir: os.PathLike = AUTO, preload: bool = None):
        """
        Record a storable into this list.

        :param value: The value to store.
        :param int: The index at which to store it (if not specified, the value is appended).
        :param str name: The file name to write the storable to during serialization.
        :param str subdir: The subdirectory to store the file in.
        :param bool preload: Preload the value during deserialization.
        """
        if idx is None:
            self.append(value)
            idx = -1
        else:
            self.insert(idx, value)

        if is_storable(value):
            rec: Record = self.store.__getitem__(idx)

            if name:
                name_cfg = RecordConfig.from_name(name=name)
                rec._config = rec._config << name_cfg
            rec._config = rec._config << RecordConfig(subdir=subdir)
                    
            if preload:
                rec.preload = preload

    def __remove__(self, context: BaseContext):
        for itm in self.store:
            remove(itm, context)
        
    def clear(self):
        for _ in range(len(self)):
            self.pop()

    def __getitem__(self, key):
        itm = self.store.__getitem__(key)
        if isinstance(itm, Record):
            return itm.content
        return itm

    def __setitem__(self, key, value):
        if key < self.__len__():
            itm = self.store.__getitem__(key)
            if is_model(itm):
                self.unused.append(itm)

        if is_storable(value):
            value = self.__make_record__(value)
        self.store.__setitem__(key, value)
    
    def insert(self, key, value):
        if is_storable(value):
            value = self.__make_record__(value)
        self.store.insert(key, value)

    def __delitem__(self, key):
        itm = self.store.pop(key)
        if is_model(itm):
            self.unused.append(itm)

    def __iter__(self):
        return iter(self.store)

    def __len__(self):
        return len(self.store)


@serializable(name='_ser__mlist')
class mlist(_blist):
    pass


@storable(name='_sto__mlist')
@serializable(name='_ser__smlist')
class smlist(mlist):
    pass


class _bdict(MutableMapping):
    def __init__(self, *, subdir: os.PathLike = '', preload: bool = False, 
            store_by_key: bool = False, store_subdir: bool = False, 
            auto_clean: bool = False, **kwargs):
        self.subdir = subdir
        self.preload = preload
        self.auto_clean = auto_clean

        self._store_by_key = store_by_key
        self._store_subdir = store_subdir

        self.store = dict()
        self.update(kwargs)

        self.unused = list()

    @classmethod
    def from_dict(cls, content: dict, /, *, subdir: os.PathLike = '', preload: bool = False, 
            store_by_key: bool = False, store_subdir: bool = False, auto_clean: bool = False):
        return cls.__init__(subdir=subdir, preload=preload, 
            store_by_key=store_by_key, store_subdir=store_subdir, 
            auto_clean=auto_clean, **content)

    def store_by_key(self, subdir: bool = False):
        self._store_by_key = True
        self._store_subdir = subdir

    @property
    def config(self):
        return RecordConfig(subdir=self.subdir)

    def __repr__(self):
        dct = {}
        for k in self.keys():
            res = self.store.__getitem__(k)
            if isinstance(res, Record):
                res = res._content
            dct[k] = res

        return dict.__repr__(dct)

    def __serialize__(self, context: BaseContext):
        dct = dict()

        res = {'store': dct}
        if self.subdir != '':
            res['subdir'] = self.subdir
        if self.preload:
            res['preload'] = self.preload
        if self._store_by_key:
            res['store_by_key'] = self._store_by_key
        if self._store_subdir:
            res['store_subdir'] = self._store_subdir
        if self.auto_clean:
            res['auto_clean'] = self.auto_clean

        for itm in self.unused:
            remove(itm, context)
        self.unused = []

        for k, itm in self.store.items():
            if isinstance(itm, Record):
                if not self.auto_clean or itm.exists():
                    dct[k] = serialize(itm, context)
                else:
                    self.unused.append(itm)
            else:
                dct[k] = serialize(itm, context)

        for itm in self.unused:
            remove(itm, context)
        self.unused = []

        return res

    @classmethod
    def __deserialize__(cls, serialized: dict, context: BaseContext):
        dct: dict = serialized.get('store', dict())

        res = cls(
            subdir=serialized.get('subdir', ''),
            preload=serialized.get('preload', False),
            store_by_key=serialized.get('store_by_key', False),
            store_subdir=serialized.get('store_subdir', False),
            auto_clean=serialized.get('auto_clean', False)
        )

        for k, v in dct.items():
            res[k] = deserialize(v, context)

        return res

    def __make_record__(self, k, v=None):
        key_config = RecordConfig()
        if self._store_by_key:
            key_config = key_config << RecordConfig(stem=k)
        if self._store_subdir:
            key_config = key_config << RecordConfig(
                subdir=os.path.join(self.subdir, k))

        if v is None:
            v = dict.__getitem__(k)
        config = self.config << key_config
        return Record(v, config, self.preload)
    
    def __remove__(self, context: BaseContext):
        for itm in self.store.values():
            remove(itm, context)
        
    def clear(self):
        for k in list(self.store.keys()):
            del self[k]

    def __getitem__(self, key):
        itm = self.store.__getitem__(key)
        if isinstance(itm, Record):
            itm = itm.content
            return itm
        return itm

    def __setitem__(self, key, value):
        itm = self.store.pop(key, None)
        if is_model(itm):
            self.unused.append(itm)

        if is_storable(value):
            value = self.__make_record__(key, value)
        self.store.__setitem__(key, value)

    def record(self, key, value, /, *, name: str = None, subdir: os.PathLike = '', preload: bool = None):
        self.__setitem__(key, value)
        if is_storable(value):
            rec: Record = self.store.__getitem__(key)
            if name:
                rec._config = rec._config << RecordConfig.from_name(name=name)
            if subdir:
                rec._config = rec._config << RecordConfig(subdir=os.path.join(rec._config.subdir, subdir))
            if preload:
                rec.preload = preload

    def __delitem__(self, key):
        itm = self.store.pop(key)
        if is_model(itm):
            self.unused.append(itm)

    def __iter__(self):
        return iter(self.store)

    def __len__(self):
        return len(self.store)


@serializable(name='_ser__mdict')
class mdict(_bdict):
    pass


@storable(name='_sto__smdict')
@serializable(name='_ser__smdict')
class smdict(_bdict):
    pass


def smlist_factory(subdir: os.PathLike = '', preload: bool = False):
    def factory():
        return smlist(subdir=subdir, preload=preload)
    return factory


def mdict_factory(subdir: os.PathLike = '', preload: bool = False, store_by_key: bool = False, store_subdir: bool = False):
    def factory():
        return mdict(subdir=subdir, preload=preload, store_by_key=store_by_key, store_subdir=store_subdir)
    return factory


def smdict_factory(subdir: os.PathLike = '', preload: bool = False, store_by_key: bool = False, store_subdir: bool = False):
    def factory():
        return smdict(subdir=subdir, preload=preload, store_by_key=store_by_key, store_subdir=store_subdir)
    return factory
