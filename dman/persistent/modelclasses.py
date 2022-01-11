from collections.abc import MutableMapping
from collections.abc import MutableSequence
import copy
import os

from typing import Iterable, Union
from dataclasses import MISSING, Field, dataclass, fields, is_dataclass, field

from dman.utils.smartdataclasses import WrapField, wrappedclass, wrappedfields, wrapfield, AUTO, is_wrapfield
from dman.persistent.storables import is_storable, storable
from dman.persistent.record import Record, RecordConfig, record, REMOVE, remove, recordconfig
from dman.persistent.serializables import SERIALIZE, DESERIALIZE, NO_SERIALIZE, is_serializable
from dman.persistent.serializables import BaseContext, serialize, deserialize, serializable


STO_FIELD = '_record__fields'
RECORD_FIELD = '__record__'
MODELCLASS = '__modelclass__'
RECORD_PRE = '_record_field__'



def _record_key(key: str):
    return f'{RECORD_FIELD}{key}'

def get_record(self, key: str, default= MISSING):
    key = _record_key(key)
    if default is MISSING:
        return getattr(self, key)
    else:
        return getattr(self, key, default)

def set_record(self, key: str, value):
    setattr(self, _record_key(key), value)


class RecordField(WrapField):
    def __init__(self, stem: str, suffix: str, name: str, subdir: os.PathLike, preload: str):
        self.stem = stem
        self.suffix = suffix
        self.name = name
        self.subdir = subdir
        self.preload = preload

    def build(self, content):
        return record(content, stem=self.stem, suffix=self.suffix, name=self.name, subdir=self.subdir, preload=self.preload)
    
    def __call__(self, key: str):
        def _get_record(obj):
            rec = get_record(obj, key)
            if isinstance(rec, Record):
                return rec.content
            return rec

        def _set_record(obj, value):
            if is_storable(value):
                rec = get_record(obj, key, None)
                if isinstance(rec, Record):
                    rec.content = value
                else:
                    rec = self.build(value)
                set_record(obj, key, rec)
            else:
                set_record(obj, key, value)
        
        return property(fget=_get_record, fset=_set_record)


def serializefield(*, default=MISSING, default_factory=MISSING,
                   init: bool = True, repr: bool = True,
                   hash: bool = False, compare: bool = False, metadata=None) -> Field:
    """
    Return an object to identify serializable modelclass fields.
        All arguments of the ``field`` method from ``dataclasses`` are provided.
        Moreover, ``record`` specific options are provided

    :param default: is the default value of the field.
    :param default_factory: is a 0-argument function called to initialize.
    :param bool init:       Include in the class's __init__().
    :param bool repr:       Include in the object's repr().
    :param bool hash:       Include in the object's hash().
    :param bool compare:    Include in comparison functions.
    :param metadata:        Additional information.

    :raises ValueError: if both default and default_factory are specified.
    """
    _metadata = {'__ser_field': True}
    if metadata is not None:
        _metadata['__base'] = metadata
    return field(default=default, default_factory=default_factory, 
        init=init, repr=repr, hash=hash, compare=compare, metadata=_metadata)


def is_serializable_field(fld: Field):
    return fld.metadata.get('__ser_field', False)


def recordfield(*, default=MISSING, default_factory=MISSING,
                init: bool = True, repr: bool = False,
                hash: bool = False, compare: bool = False, metadata=None,
                stem: str = AUTO, suffix: str = AUTO, name: str = AUTO, subdir: os.PathLike = '', preload: str = False
                ) -> Field:
    """
    Return an object to identify storable modelclass fields.
        All arguments of the ``field`` method from ``dataclasses`` are provided.
        Moreover, ``record`` specific options are provided

    :param default: is the default value of the field.
    :param default_factory: is a 0-argument function called to initialize.
    :param bool init:       Include in the class's __init__().
    :param bool repr:       Include in the object's repr().
    :param bool hash:       Include in the object's hash().
    :param bool compare:    Include in comparison functions.
    :param metadata:        Additional information.

    :param str stem:        The stem of the file.
    :param str suffix:      The suffix or extension of the file (e.g. ``'.json'``).
    :param str name:        The full name of the file.
    :param str subdir:      The subdirectory in which to store te file. 
    :param bool preload:    When ``True`` the file will be loaded during deserialization.

    :raises ValueError: if both default and default_factory are specified.
    :raises ValueError:     if a name and a stem and/or suffix are specified. 
    """

    wrap = RecordField(stem=stem, suffix=suffix, name=name, subdir=subdir, preload=preload)
    return wrapfield(wrap, label=STO_FIELD, default=default, default_factory=default_factory, 
        init=init, repr=repr, hash=hash, compare=compare, metadata=metadata)


def modelclass(cls=None, /, *, name: str = None, init=True, repr=True, eq=True, order=False,
               unsafe_hash=False, frozen=False, storable: bool = False, compact: bool = False, **kwargs):
    """
    Convert a class to a modelclass.
        Returns the same class as was passed in, with dunder methods added based on the fields
        defined in the class.
        The class is automatically made ``serializable`` by adding ``__serialize__``
        and ``__deserialize__``.

        The arguments of the ``dataclass`` decorator are provided. Two additional 
        arguments are also available.

    :param bool init: add an ``__init__`` method. 
    :param bool repr: add a ``__repr__`` method. 
    :param bool order: rich comparison dunder methods are added. 
    :param bool unsafe_hash: add a ``__hash__`` method function.
    :param bool frozen: fields may not be assigned to after instance creation.
    :param bool storable: make the class storable with a ``__write__`` and ``__read__``.
    :param bool compact: do not include serializable types during serialization (results in more compact serializations).
    """

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
    # convert to dataclass
    res = cls
    if not is_dataclass(cls):
        res = dataclass(cls, init=init, repr=repr, eq=eq,
                        order=order, unsafe_hash=unsafe_hash, frozen=frozen)

    # auto convert fields if necessary
    for f in fields(res):
        if is_wrapfield(f):
            continue

        if is_serializable_field(f):
            ser_field: Field = field(metadata=f.metadata.get('__base', None))
            f.metadata = ser_field.metadata            
        elif is_storable(f.type):
            wrapped_field: Field = recordfield(metadata=f.metadata)
            f.metadata = wrapped_field.metadata

    # wrap the fields
    res = wrappedclass(res)

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
    return wrappedfields(obj, label=STO_FIELD)


def _remove__modelclass(self, context: BaseContext = None):
    for f in fields(self):
        if f.name not in getattr(self, NO_SERIALIZE, []):
            if f.name in recordfields(self):
                value = getattr(self, _record_key(f.name))
                remove(value, context)
            else:
                value = getattr(self, f.name)
                remove(value, context)


def _serialize__modelclass_content_only(self, context: BaseContext = None):
    res = dict()
    for f in fields(self):
        if f.name not in getattr(self, NO_SERIALIZE, []):
            if f.name in recordfields(self):
                value = getattr(self, _record_key(f.name))
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
        if f.name in recordfields(cls):
            processed[f.name] = deserialize(value, context, ser_type=Record)
        else:
            processed[f.name] = deserialize(value, context, ser_type=f.type)

    return cls(**processed)


def _serialize__modelclass(self, context: BaseContext = None):
    res = dict()
    for f in fields(self):
        if f.name not in getattr(self, NO_SERIALIZE, []):
            if f.name in recordfields(self):
                value = getattr(self, _record_key(f.name))
            else:
                value = getattr(self, f.name)
            res[f.name] = serialize(value, context)
                    
    return res


@classmethod
def _deserialize__modelclass(cls, serialized: dict, context: BaseContext):
    processed = dict()
    for f in fields(cls):
        v = serialized.get(f.name, None)
        if v is not None:
            processed[f.name] = deserialize(v, context)

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

        for itm in self.store:
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

    def record(self, value, idx: int = None, /, *, stem: str = AUTO, suffix: str = AUTO, name: str = AUTO, subdir: os.PathLike = '', preload: str = False):
        """
        Record a storable into this list.

        :param value:           The value to store.
        :param int:             The index at which to store it (if not specified, the value is appended).
        :param str stem:        The stem of a file.
        :param str suffix:      The suffix or extension of the file (e.g. ``'.json'``).
        :param str name:        The full name of the file.
        :param str subdir:      The subdirectory in which to store te file. 
        :param bool preload:    When ``True`` the file will be loaded during deserialization.

        :raises ValueError:     if a name and a stem and/or suffix are specified. 
        """
        if idx is None:
            self.append(value)
            idx = -1
        else:
            self.insert(idx, value)

        if is_storable(value):
            rec: Record = self.store.__getitem__(idx)
            cfg = recordconfig(stem=stem, suffix=suffix, name=name, subdir=os.path.join(rec._config.subdir, subdir))
            rec._config = rec._config << cfg
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
        return (itm.content if isinstance(itm, Record) else itm for itm in self.store)

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
        """
        Create an instance of this model dictionary.

        :param str subdir: Specify the default sub-subdirectory for storables.
        :param bool preload: Specify whether storables should be preloaded.
        :param bool store_by_key: Sets the stem to the key in the dictionary. 
        :param bool store_subdir: Stores files in dedicated subdir based on key. 
        :param bool auto_clean: Automatically remove records with dangling pointers on serialization.
        :param kwargs: Initial content of the dict.
        """
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

    def record(self, key, value, /, *, stem: str = AUTO, suffix: str = AUTO, name: str = AUTO, subdir: os.PathLike = '', preload: str = False):  
        """
        Record a storable into this dict.
    
        :param key: The key at which to store the value.
        :param value: The value to store.
        :param str stem:        The stem of a file.
        :param str suffix:      The suffix or extension of the file (e.g. ``'.json'``).
        :param str name:        The full name of the file.
        :param str subdir:      The subdirectory in which to store te file. 
        :param bool preload:    When ``True`` the file will be loaded during deserialization.

        :raises ValueError:     if a name and a stem and/or suffix are specified. 
        """
        self.__setitem__(key, value)
        if is_storable(value):
            rec: Record = self.store.__getitem__(key)
            cfg = recordconfig(stem=stem, suffix=suffix, name=name, subdir=os.path.join(rec._config.subdir, subdir))
            rec._config = rec._config << cfg
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


class _bruns(_blist):
    def __init__(self, iterable: Iterable = None, stem: str = 'run', subdir: os.PathLike = '', preload: bool = False, store_subdir: bool = True, auto_clean: bool = False):
        """
        Create an instance of this labeled model list.

        :param iterable: Initial content of the list.
        :param str stem: The stem used to determine file keys (e.g. stem-0, stem-1, ...).
        :param str subdir: Specify the default sub-subdirectory for storables.
        :param bool preload: Specify whether storables should be preloaded.
        :param bool store_subdir: Specify whether each item should be stored in a separate directory.
        :param bool auto_clean: Automatically remove records with dangling pointers on serialization.
        """
        self.stem = stem
        self.run_count = 0
        self.store_subdir = store_subdir

        super().__init__(iterable=iterable, subdir=subdir, preload=preload, auto_clean=auto_clean)
        
    @property
    def config(self):
        return RecordConfig(subdir=self.subdir)

    def __make_record__(self, itm):
        key = f'{self.stem}-{self.run_count}'
        self.run_count += 1
        key_config = RecordConfig(stem=key)
        if self.store_subdir:
            key_config = key_config << RecordConfig(
                stem=self.stem,
                subdir=os.path.join(self.subdir, key)
            )

        config = self.config << key_config
        return Record(itm, config, self.preload)

    def __serialize__(self, context: BaseContext):
        res = {'stem': self.stem, 'run_count': self.run_count}
        if not self.store_subdir: res['store_subdir'] = False
        return res | super().__serialize__(context)

    @classmethod
    def __deserialize__(cls, serialized: dict, context: BaseContext):
        res: _bruns = super(_bruns, cls).__deserialize__(serialized, context)
        res.stem = serialized.get('stem')
        res.run_count = serialized.get('run_count')
        res.store_subdir = serialized.get('store_subdir', True)
        return res

    def record(self, value, idx: int = None, /, *, suffix: str = AUTO, subdir: os.PathLike = '', preload: str = False):
        """
        Record a storable into this list.

        :param value:           The value to store.
        :param int:             The index at which to store it (if not specified, the value is appended).
        :param str suffix:      The suffix or extension of the file (e.g. ``'.json'``).
        :param str subdir:      The subdirectory in which to store te file. 
        :param bool preload:    When ``True`` the file will be loaded during deserialization.

        :raises ValueError:     if a name and a stem and/or suffix are specified. 
        """
        if idx is None:
            self.append(value)
            idx = -1
        else:
            self.insert(idx, value)

        if is_storable(value):
            rec: Record = self.store.__getitem__(idx)
            cfg = recordconfig(
                suffix=suffix, 
                subdir=os.path.join(rec._config.subdir, subdir)
            )
            rec._config = rec._config << cfg
            if preload:
                rec.preload = preload

    def clear(self):
        super().clear()
        self.run_count = 0


@serializable(name='_ser__mruns')
class mruns(_bruns):
    pass


@storable(name='_sto__smruns')
@serializable(name='_ser__smruns')
class smruns(_bruns):
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


def mruns_factory(stem: str = None, subdir: os.PathLike = '', preload: bool = False, store_subdir: bool = True):
    def factory():
        return mruns(stem=stem, subdir=subdir, preload=preload, store_subdir=store_subdir)
    return factory


def smruns_factory(stem: str = None, subdir: os.PathLike = '', preload: bool = False, store_subdir: bool = True):
    def factory():
        return mruns(stem=stem, subdir=subdir, preload=preload, store_subdir=store_subdir)
    return factory
