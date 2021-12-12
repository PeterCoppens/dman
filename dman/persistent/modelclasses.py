from collections.abc import MutableMapping
from collections.abc import MutableSequence
import copy
import os

from typing import Iterable
from dataclasses import MISSING, fields

from dman.persistent.smartdataclasses import AUTO, Wrapper, wrappedclass, WrappedField, attr_wrapper, attr_wrapped_field
from dman.persistent.storeables import is_storeable, storeable
from dman.persistent.record import Record, RecordConfig, record, REMOVE, remove
from dman.persistent.serializables import SERIALIZE, DESERIALIZE, _deserialize__dataclass__inner, _serialize__dataclass__inner, NO_SERIALIZE
from dman.persistent.serializables import BaseContext, serialize, deserialize, is_serializable, is_deserializable, serializable


STO_FIELD = '_record__fields'
RECORD_FIELD = '__record__'


class RecordWrapper(Wrapper):
    WRAPPED_FIELDS_NAME = STO_FIELD

    def __init__(self, stem: str, suffix: str, name: str, subdir: os.PathLike, preload: str, options: dict):
        self.stem = stem
        self.suffix = suffix
        self.name = name
        self.subdir = subdir
        self.preload = preload
        self.options = options

    def build(self, content):
        return record(content, stem=self.stem, suffix=self.suffix, name=self.name, subdir=self.subdir, preload=self.preload, **self.options)

    def __process__(self, obj, wrapped):
        if wrapped is None:
            return None

        if isinstance(wrapped, Record):
            return wrapped.content

        return wrapped


def recordfield(*, default=MISSING, default_factory=MISSING,
                init: bool = True, repr: bool = False,
                hash: bool = False, compare: bool = False, metadata=None,
                stem: str = AUTO, suffix: str = AUTO, name: str = AUTO, subdir: os.PathLike = '', preload: str = False, **options
                ):

    return WrappedField(
        RecordWrapper(stem=stem, suffix=suffix, name=name,
                      subdir=subdir, preload=preload, options=options),
        default=default, default_factory=default_factory,
        init=init, repr=repr, hash=hash,
        compare=compare, metadata=metadata
    )


def modelclass(cls=None, /, *, name: str = None, init=True, repr=True, eq=True, order=False,
               unsafe_hash=False, frozen=False, storeable: bool = False, compact: bool = False, **kwargs):

    def wrap(cls):
        return _process__modelclass(cls, name, init, repr, eq, order, unsafe_hash, frozen, storeable, compact, **kwargs)

    # See if we're being called as @modelclass or @modelclass().
    if cls is None:
        # We're called with parens.
        return wrap

    # We're called as @modelclass without parens.
    return wrap(cls)


def _process__modelclass(cls, name, init, repr, eq, order, unsafe_hash, frozen, as_storeable, compact, **kwargs):
    annotations: dict = cls.__dict__.get('__annotations__', dict())

    for k, v in annotations.items():
        if is_storeable(v) and getattr(cls, k, None) is None:
            setattr(cls, k, recordfield())

    res = wrappedclass(cls, init=init, repr=repr, eq=eq,
                       order=order, unsafe_hash=unsafe_hash, frozen=frozen)

    # assign serialize and deserialize methods
    ser, dser = _serialize__modelclass, _deserialize__modelclass
    if compact:
        ser, dser = _serialize__modelclass_content_only, _deserialize__modelclass_content_only

    if getattr(res, REMOVE, None) is None:
        setattr(res, REMOVE, _remove__modelclass)
    if getattr(res, SERIALIZE, None) is None:
        setattr(res, SERIALIZE, ser)
    if getattr(res, DESERIALIZE, None) is None:
        setattr(res, DESERIALIZE, dser)
        setattr(res, '_deserialize__dataclass__inner',
                _deserialize__dataclass__inner)

    result = serializable(res, name=name)
    if as_storeable:
        result = storeable(result, name=name)
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
                value = getattr(self, attr_wrapped_field(
                    f.name))      # wrap the private value
                if isinstance(value, Record):
                    record = value
                else:
                    recwrapper: RecordWrapper = getattr(
                        self, attr_wrapper(f.name))
                    record = recwrapper.build(value)
                res[f.name] = {
                    RECORD_FIELD: True,
                    **serialize(record, context, content_only=True)
                }
            else:
                value = getattr(self, f.name)
                if is_serializable(value):
                    res[f.name] = serialize(value, context, content_only=True)
                else:
                    res[f.name] = _serialize__dataclass__inner(
                        getattr(self, f.name), context
                    )

    return res


@classmethod
def _deserialize__modelclass_content_only(cls, serialized: dict, context: BaseContext):
    processed = copy.deepcopy(serialized)
    for f in fields(cls):
        v = processed.get(f.name, None)
        if v is None:
            continue
        if isinstance(v, dict) and v.get(RECORD_FIELD, False):
            rec = deserialize(v, context, ser_type=Record)
            processed[f.name] = rec
        elif is_serializable(f.type):
            processed[f.name] = deserialize(v, context, ser_type=f.type)
        else:
            processed[f.name] = getattr(
                cls, '_deserialize__dataclass__inner')(v, context)

    return cls(**processed)


def _serialize__modelclass(self, context: BaseContext = None):
    res = dict()
    for f in fields(self):
        if f.name not in getattr(self, NO_SERIALIZE, []):
            if f.name in recordfields(self):
                value = getattr(self, attr_wrapped_field(
                    f.name))      # wrap the private value
                if isinstance(value, Record):
                    record = value
                else:
                    recwrapper: RecordWrapper = getattr(
                        self, attr_wrapper(f.name))
                    record = recwrapper.build(value)
                res[f.name] = {
                    RECORD_FIELD: True,
                    **serialize(record, context, content_only=True)
                }
            else:
                res[f.name] = _serialize__dataclass__inner(
                    getattr(self, f.name), context
                )
                    
    return res


@classmethod
def _deserialize__modelclass(cls, serialized: dict, context: BaseContext):
    processed = copy.deepcopy(serialized)
    for k, v in processed.items():
        if isinstance(v, dict) and v.get(RECORD_FIELD, False):
            rec = deserialize(v, context, ser_type=Record)
            processed[k] = rec
        else:
            processed[k] = getattr(
                cls, '_deserialize__dataclass__inner')(v, context)

    return cls(**processed)


class _blist(MutableSequence):
    def __init__(self, iterable: Iterable = None, subdir: os.PathLike = '', preload: bool = False, options: dict = None):
        if iterable is None:
            iterable = list()
        self.store = list(iterable)

        self.subdir = subdir
        self.preload = preload
        if options is None:
            options = dict()
        self.options = options

    def __repr__(self):
        lst = []
        for i in range(len(self)):
            res = self.store.__getitem__(i)
            if isinstance(res, Record):
                res = res._content
            lst.append(res)

        return list.__repr__(lst)

    def __make_record__(self, itm):
        return record(itm, subdir=self.subdir, preload=self.preload, **self.options)

    def __remove_key(self, key, context):
        itm = self.store.__getitem__(key)
        remove(itm, context)

    def remove(self, key, context: BaseContext):
        self.__remove_key(key, context)
        self.store.__delitem__(key)

    def __remove__(self, context: BaseContext):
        for i in range(len(self.store)):
            self.__remove_key(i, context)

    def __serialize__(self, context: BaseContext):
        lst = []

        res = {'list': lst}
        if self.subdir != '':
            res['subdir'] = self.subdir
        if self.preload:
            res['preload'] = self.preload
        if len(self.options) > 0:
            res['options'] = self.options

        for itm in self:
            if isinstance(itm, Record):
                lst.append({
                    RECORD_FIELD: True, **serialize(itm, context)
                })
            elif is_serializable(itm):
                lst.append(serialize(itm))
            else:
                lst.append(itm)
        return res

    @classmethod
    def __deserialize__(cls, serialized: dict, context: BaseContext):
        subdir = serialized.get('subdir', '')
        preload = serialized.get('preload', False)
        options = serialized.get('options', {})

        lst = serialized.get('list', list())
        res = cls(subdir=subdir, preload=preload, options=options)

        for itm in lst:
            if isinstance(itm, dict) and is_deserializable(itm):
                if itm.get(RECORD_FIELD, False):
                    rec: Record = deserialize(itm, context)
                    res.append(rec)
                else:
                    res.append(deserialize(itm, context))
            else:
                res.append(itm)

        return res

    def record(self, value, idx: int = None, /, *, name: str = None, subdir: os.PathLike = AUTO, preload: bool = None, **kwargs):
        if idx is None:
            self.append(value)
            idx = -1
        else:
            self.insert(idx, value)

        if is_storeable(value):
            rec: Record = self.store.__getitem__(idx)
            if name:
                rec._config = rec._config << RecordConfig.from_name(
                    name=name, subdir=subdir)
            if preload:
                rec.preload = preload
            for k, v in kwargs.items():
                rec.context_options[k] = v

    def __getitem__(self, key):
        itm = self.store.__getitem__(key)
        if isinstance(itm, Record):
            return itm.content
        return itm

    def __setitem__(self, i, v):
        if is_storeable(v):
            v = self.__make_record__(v)
        self.store.__setitem__(i, v)

    def insert(self, i, v):
        if is_storeable(v):
            v = self.__make_record__(v)
        self.store.insert(i, v)

    def __delitem__(self, i):
        raise ValueError('use remove to delete items')

    def __iter__(self):
        return iter(self.store)

    def __len__(self):
        return len(self.store)


@serializable(name='_ser__mlist')
class mlist(_blist):
    pass


@storeable(name='_sto__mlist')
@serializable(name='_ser__smlist')
class smlist(mlist):
    pass


class _bdict(MutableMapping):
    def __init__(self, *, subdir: os.PathLike = '', preload: bool = False, store_by_key: bool = False, store_subdir: bool = False, options: dict = None, **kwargs):
        self.subdir = subdir
        self.preload = preload
        if options is None:
            options = dict()
        self.options = options

        self._store_by_key = store_by_key
        self._store_subdir = store_subdir

        self.store = dict()
        self.update(dict(**kwargs))

    @classmethod
    def from_dict(cls, dict: dict, subdir: os.PathLike = '', preload: bool = False, options: dict = None):
        return cls.__init__(subdir=subdir, preload=preload, options=options, **dict)

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

    def __remove_key(self, key, context: BaseContext):
        itm = self.store.__getitem__(key)
        remove(itm, context)

    def __remove__(self, context: BaseContext):
        for k in self.keys():
            self.__remove_key(k, context)

    def remove(self, key, context: BaseContext):
        self.__remove_key(key, context)
        del self.store[key]

    def __serialize__(self, context: BaseContext):
        dct = dict()

        res = {'dict': dct}
        if self.subdir != '':
            res['subdir'] = self.subdir
        if self.preload:
            res['preload'] = self.preload
        if len(self.options) > 0:
            res['options'] = self.options
        if self._store_by_key:
            res['store_by_key'] = self._store_by_key
        if self._store_subdir:
            res['store_subdir'] = self._store_subdir

        for k in self.keys():
            v = self.store.__getitem__(k)
            if isinstance(v, Record):
                dct[k] = (
                    {RECORD_FIELD: True, **serialize(v, context, content_only=True)})
            elif is_serializable(v):
                dct[k] = serialize(v, context)
            else:
                dct[k] = v
        return res

    @classmethod
    def __deserialize__(cls, serialized: dict, context: BaseContext):
        dct: dict = serialized.get('dict', list())

        res = cls(
            subdir=serialized.get('subdir', ''),
            preload=serialized.get('preload', False),
            options=serialized.get('options', {}),
            store_by_key=serialized.get('store_by_key', False),
            store_subdir=serialized.get('store_subdir', False)
        )

        for k, v in dct.items():
            if isinstance(v, dict):
                if v.get(RECORD_FIELD, False):
                    res[k] = Record.__deserialize__(v, context)
                else:
                    res[k] = deserialize(v, context)
            else:
                res[k] = v

        return res

    def __key_command__(self, k):
        config = RecordConfig()
        if self._store_by_key:
            config = config << RecordConfig(stem=k)
        if self._store_subdir:
            config = config << RecordConfig(
                subdir=os.path.join(self.subdir, k))
        return config

    def __make_record__(self, k, v=None):
        if v is None:
            v = dict.__getitem__(k)
        config = self.config << self.__key_command__(k)
        return Record(v, config, self.preload, context_options=copy.deepcopy(self.options))

    def __getitem__(self, key):
        itm = self.store.__getitem__(key)
        if isinstance(itm, Record):
            itm = itm.content
            return itm
        return itm

    def __setitem__(self, key, value):
        if is_storeable(value):
            value = self.__make_record__(key, value)
        self.store.__setitem__(key, value)

    def record(self, key, value, /, *, name: str = None, subdir: os.PathLike = AUTO, preload: bool = None, **kwargs):
        self.__setitem__(key, value)
        if is_storeable(value):
            rec: Record = self.store.__getitem__(key)
            if name:
                rec._config = rec._config << RecordConfig.from_name(name=name)
            if subdir:
                rec._config = rec._config << RecordConfig(subdir=os.path.join(rec._config.subdir, subdir))
            if preload:
                rec.preload = preload
            for k, v in kwargs.items():
                rec.context_options[k] = v

    def __delitem__(self, key):
        raise ValueError('use remove to delete items')

    def __iter__(self):
        return iter(self.store)

    def __len__(self):
        return len(self.store)


@serializable(name='_ser__mdict')
class mdict(_bdict):
    pass


@storeable(name='_sto__smdict')
@serializable(name='_ser__smdict')
class smdict(_bdict):
    pass


def smlist_factory(subdir: os.PathLike = '', preload: bool = False, **kwargs):
    def factory():
        return smlist(subdir=subdir, preload=preload, options=kwargs)
    return factory


def mdict_factory(subdir: os.PathLike = '', preload: bool = False, store_by_key: bool = False, store_subdir: bool = False, **kwargs):
    def factory():
        return mdict(subdir=subdir, preload=preload, store_by_key=store_by_key, store_subdir=store_subdir, options=kwargs)
    return factory


def smdict_factory(subdir: os.PathLike = '', preload: bool = False, store_by_key: bool = False, store_subdir: bool = False, **kwargs):
    def factory():
        return smdict(subdir=subdir, preload=preload, store_by_key=store_by_key, store_subdir=store_subdir, options=kwargs)
    return factory
