"""
Defines Model Types, which are containers for storables.
"""

from collections.abc import MutableMapping
from collections.abc import MutableSequence
import copy
import os

from typing import Any, Callable, Iterable, TypeVar, Union, Type
from dataclasses import MISSING, Field, dataclass, fields, is_dataclass, field, asdict
from typing_extensions import dataclass_transform
from dman.core import log

from dman.utils.smartdataclasses import (
    wrappedclass,
    wrapfield,
    is_wrapfield,
    get_descriptor,
    configclass
)
from dman.core.storables import is_storable, storable
from dman.model.record import Record, record, REMOVE, remove, is_removable
from dman.core.serializables import (
    SERIALIZE,
    DESERIALIZE,
    NO_SERIALIZE
)
from dman.core.serializables import BaseContext, serialize, deserialize, serializable
from dman.core.path import Target, AUTO


STO_FIELD = "_record__fields"
SER_FIELD = "_serial__fields"
RECORD_FIELDS = "__record__"
UNUSED_FIELDS = "__unused__"
MODELCLASS = "__modelclass__"
RECORD_PRE = "_record_field__"


@configclass
class Config:
    """Configuration for model types.

        This class has a global instance that can be accessed as follows:

        >>> dman.model.modelclasses.config.auto_clean = True
        >>> dman.params.model.auto_clean = True  # equivalent

    Args:
        auto_clean (bool, optional): Automatically clean files associated with items that were removed from the container.
    """
    auto_clean: bool = True
config = Config()


def _record_key(key: str):
    return f"{RECORD_FIELDS}{key}"


def get_record(obj, key: str, default=MISSING):
    """Get the record for a field in a modelclass.

    Args:
        obj: The modelclass
        key (str): Key of the field
        default (optional): Default value. Defaults to MISSING.
    """
    key = _record_key(key)
    if default is MISSING:
        return getattr(obj, key)
    else:
        return getattr(obj, key, default)


def set_record(self, key: str, value: Record):
    """Set the record for a field in a modelclass.

    Args:
        obj: The modelclass
        key (str): Key of the field
        value (record): The value to set.
    """
    setattr(self, _record_key(key), value)


class RecordWrap:
    def __init__(self, target: Target, preload: str, pre: Callable[[Any], Any]):
        self.target = target
        self.preload = preload
        self.pre = pre

    def record(self, owner):
        return getattr(owner, self.private_name)

    def build(self, content):
        return Record(content, self.target, self.preload)

    def __set_name__(self, _, name):
        self.public_name = name
        self.private_name = f"_{name}"

    def __get__(self, obj, objtype=None):
        rec = getattr(obj, self.private_name)
        if isinstance(rec, Record):
            return rec.content
        return rec

    def __set__(self, obj, value):
        if not isinstance(value, Record) and self.pre is not None:
            value = self.pre(value)

        if is_storable(value):
            # change content of existing record
            rec = getattr(obj, self.private_name, None)
            if isinstance(rec, Record):
                # store old content for removal if needed
                if config.auto_clean and is_removable(rec.content):
                    unused_fields(obj).append(rec.content)

                # update content
                rec.content = value
                return
            
            # create new record
            rec = self.build(value)
            record_fields(obj)[self.public_name] = rec
            setattr(obj, self.private_name, rec)
        else:
            rec = record_fields(obj).get(self.public_name, None)
            if config.auto_clean and rec is not None:
                # store old record for removal
                unused_fields(obj).append(rec)
            setattr(obj, self.private_name, value)
            record_fields(obj)[self.public_name] = value

    # TODO add __del__ method


class SerializeWrap:
    def __init__(self, pre: Callable[[Any], Any]):
        self.pre = pre

    def __set_name__(self, owner, name):
        self.public_name = name
        self.private_name = f"_{name}"

    def __get__(self, obj, objtype=None):
        return getattr(obj, self.private_name)

    def __set__(self, obj, value):
        if self.pre is not None:
            value = self.pre(value)
        setattr(obj, self.private_name, value)


def record_fields(obj) -> dict:
    """Get all the records associated with storable fields in a modelclass."""
    res = getattr(obj, RECORD_FIELDS, None)
    if res is None:
        res = dict()
        setattr(obj, RECORD_FIELDS, res)
    return res


def unused_fields(obj) -> list:
    """Get all the records that are no longer used since they were overwritten."""
    res = getattr(obj, UNUSED_FIELDS, None)
    if res is None:
        res = []
        setattr(obj, UNUSED_FIELDS, res)
    return res


def serializefield(
    *,
    default=MISSING,
    default_factory=MISSING,
    init: bool = True,
    repr: bool = True,
    hash: bool = False,
    compare: bool = True,
    metadata=None,
    pre: Callable[[Any], Any] = None,
) -> Field:
    """Return an object to identify serializable modelclass fields.
        All arguments of the ``field`` method from ``dataclasses`` are provided.
        Moreover, ``record`` specific options are provided

    Args:
        default (optional): is the default value of the field.
        default_factory (optional): is a 0-argument function called to initialize.
        init (bool, optional): Include in the class's __init__(). Defaults to True.
        repr (bool, optional): Include in the object's repr(). Defaults to True.
        hash (bool, optional): Include in the object's hash(). Defaults to False.
        compare (bool, optional): Include in comparison functions. Defaults to True.
        metadata (_type_, optional): Additional information. Defaults to None.
        pre (Callable[[Any], Any], optional): Call method on field before setting. Defaults to None.
    """   
    _metadata = {"__ser_field": True}
    if metadata is not None:
        _metadata["__base"] = metadata
    if pre is None:
        return field(
            default=default,
            default_factory=default_factory,
            init=init,
            repr=repr,
            hash=hash,
            compare=compare,
            metadata=_metadata,
        )
    else:
        wrap = SerializeWrap(pre)
        return wrapfield(
            wrap,
            default=default,
            default_factory=default_factory,
            init=init,
            repr=repr,
            hash=hash,
            compare=compare,
            metadata=_metadata,
        )


def is_serializable_field(fld: Field):
    """Check if a field is explicitly registered as a serializable field."""
    return fld.metadata is not None and fld.metadata.get("__ser_field", False)


def recordfield(
    *,
    default=MISSING,
    default_factory=MISSING,
    init: bool = True,
    repr: bool = False,
    hash: bool = False,
    compare: bool = False,
    metadata=None,
    stem: str = AUTO,
    suffix: str = AUTO,
    name: str = AUTO,
    subdir: os.PathLike = AUTO,
    preload: str = False,
    pre: Callable[[Any], Any] = None,
) -> Field:
    """Return an object to identify storable modelclass fields.
        All arguments of the ``field`` method from ``dataclasses`` are provided.
        Moreover, ``record`` specific options are provided

    Args:
        default (optional): The default value of the field.. Defaults to MISSING.
        default_factory (optional): A 0-argument function called to initialize. Defaults to MISSING.
        init (bool, optional): Include in the class's __init__(). Defaults to True.
        repr (bool, optional): Include in the object's repr(). Defaults to False.
        hash (bool, optional): Include in the object's hash(). Defaults to False.
        compare (bool, optional): Include in comparison functions. Defaults to False.
        metadata (_type_, optional): Additional information. Defaults to None.

        stem (str, optional): The stem of the file. Defaults to AUTO.
        suffix (str, optional): The suffix or extension of the file (e.g. ``'.json'``). Defaults to AUTO.
        name (str, optional): The full name of the file. Defaults to AUTO.
        subdir (os.PathLike, optional): The subdirectory in which to store te file. Defaults to AUTO.
        preload (str, optional): When ``True`` the file will be loaded during deserialization. Defaults to False.
        pre (Callable[[Any], Any], optional): Call method on field before setting. Defaults to None.
    """
    wrap = RecordWrap(
        target=Target(stem, suffix, subdir, name=name), preload=preload, pre=pre
    )
    return wrapfield(
        wrap,
        default=default,
        default_factory=default_factory,
        init=init,
        repr=repr,
        hash=hash,
        compare=compare,
        metadata=metadata,
    )


__pre_fields = dict()


def register_preset(tp: Type, pre: Callable[[Any], Any]):
    """Register a preset method ``pre`` for a type ``tp``. 

        When a field with that type is defined in a modelclass, ``pre`` 
        is called before setting the field.

    Example:
        >>> register_preset(barray, lambda arg: 
        >>>    arg.view(barray) if isinstance(arg, np.ndarray) else arg
        >>> )
    """
    __pre_fields[tp] = pre


def get_preset(tp: Type):
    return __pre_fields.get(tp, None)


_T = TypeVar("_T")


@dataclass_transform(field_specifiers=(wrapfield, recordfield, serializefield, field, Field))
def modelclass(
    cls=None,
    /,
    *,
    name: str = None,
    init=True,
    repr=True,
    eq=True,
    order=False,
    unsafe_hash=False,
    frozen=False,
    storable: bool = False,
    compact: bool = False,
    store_by_field: bool = False,
    cluster: bool = False,
    subdir: str = "",
    template: Any = None,
    **kwargs,
) -> Callable[[Type[_T]], Type[_T]]:
    """Convert a class to a modelclass.

        Returns the same class as was passed in, with dunder methods added based 
        on the fields defined in the class. The class is automatically made 
        ``serializable`` by adding ``__serialize__`` and ``__deserialize__``.

        If an attribute ``__no_serialize__`` is added, then the
        field names listed as string within will not be included 
        in the serialization.

        The arguments of the ``dataclass`` decorator are provided and some
        additional arguments are also available.

    Args:
        cls: Class to convert.
        name (str, optional): Name of the serializable (and storable if required). Defaults to class name.

        init (bool, optional): Add an ``__init__`` method. Defaults to True.
        repr (bool, optional): Add a ``__repr__`` method. Defaults to True.
        eq (bool, optional): Add a ``__eq__`` method. Defaults to True.
        order (bool, optional): Add rich comparison methods. Defaults to False.
        unsafe_hash (bool, optional): Add a ``__hash__`` method. Defaults to False.
        frozen (bool, optional): Fields may not be assigned after instance creation. Defaults to False.

        storable (bool, optional): Make the class storable with a ``__write__`` and ``__read__``. Defaults to False.
        compact (bool, optional): Do not include serializable types during serialization, making the result more compact. Defaults to False.
        store_by_field (bool, optional): The stem of files is determined by the field name. Defaults to False.
        cluster (bool, optional): Each file is stored in a subfolder determined by the field name. Defaults to False.
        subdir (str, optional): Store the files in a common subfolder. Defaults to "".
        template (Any, optional): Template for serialization. Defaults to None.
    """

    def wrap(cls):
        return _process__modelclass(
            cls,
            name,
            init,
            repr,
            eq,
            order,
            unsafe_hash,
            frozen,
            storable,
            compact,
            store_by_field,
            cluster,
            subdir,
            template,
            **kwargs,
        )

    return wrap if cls is None else wrap(cls)


def is_modelclass(cls):
    """Check if a class is a modelclass."""
    return getattr(cls, MODELCLASS, False)


def _process__modelclass(
    cls,
    name,
    init,
    repr,
    eq,
    order,
    unsafe_hash,
    frozen,
    as_storable,
    compact,
    store_by_field,
    cluster,
    subdir,
    template,
    **kwargs,
):
    # convert to dataclass
    res = dataclass(
        cls,
        init=init,
        repr=repr,
        eq=eq,
        order=order,
        unsafe_hash=unsafe_hash,
        frozen=frozen,
    )

    # auto convert fields if necessary
    for f in fields(res):
        pre = get_preset(f.type)
        if is_wrapfield(f):
            descr = get_descriptor(f)
            if isinstance(descr, (RecordWrap, SerializeWrap)):
                if descr.pre is None:
                    descr.pre = pre
            if isinstance(descr, RecordWrap):
                if store_by_field and descr.target.stem is AUTO:
                    descr.target.stem = f.name
                if descr.target.subdir is AUTO:
                    descr.target.subdir = os.path.join(subdir, f.name) if cluster else subdir
        elif is_serializable_field(f):
            ser_field: Field = serializefield(
                metadata=f.metadata.get("__base", None), pre=pre
            )
            f.metadata = ser_field.metadata
        elif is_storable(f.type):
            wrapped_field: Field = recordfield(
                metadata=f.metadata,
                pre=pre,
                stem=f.name if store_by_field else AUTO,
                subdir=os.path.join(subdir, f.name) if cluster else subdir,
            )
            f.metadata = wrapped_field.metadata
        elif pre is not None:
            ser_field: Field = serializefield(
                metadata=f.metadata.get("__base", None), pre=pre
            )
            f.metadata = ser_field.metadata

    # wrap the fields
    res = wrappedclass(res)

    # set modelclass flag
    setattr(res, MODELCLASS, True)

    # assign remove method if not pre-defined
    if getattr(res, REMOVE, None) is None:
        setattr(res, REMOVE, _remove__modelclass)

    # assign serialize and deserialize methods
    if template:
        result = serializable(res, name=name, template=template)
    else:
        ser, dser = _serialize__modelclass, _deserialize__modelclass
        if compact:
            ser, dser = (
                _serialize__modelclass_content_only,
                _deserialize__modelclass_content_only,
            )
        if getattr(res, SERIALIZE, None) is None:
            setattr(res, SERIALIZE, ser)
        if getattr(res, DESERIALIZE, None) is None:
            setattr(res, DESERIALIZE, dser)

        result = serializable(res, name=name)

    if as_storable:
        result = storable(result, name=name)
    return result


def _remove__modelclass(self, context: BaseContext = None):
    if context is None:
        context = BaseContext()

    if config.auto_clean:
        for v in unused_fields(self):
            remove(v, context)

    _rfields = record_fields(self)
    for f in fields(self):
        if f.name not in getattr(self, NO_SERIALIZE, []):
            log.info(f'removing field: "{f.name}"', "modelclass")
            if f.name in _rfields:
                remove(_rfields[f.name], context)
            else:
                value = getattr(self, f.name)
                remove(value, context)


def _serialize__modelclass(self, context: BaseContext = None):
    res = dict()
    log.info(
        f"serializing modelclass with fields {[f.name for f in fields(self)]}.",
        "modelclass",
    )

    # remove unused fields   
    if config.auto_clean:        
        for v in unused_fields(self):
            remove(v, context)

    # serialize used fields
    _rfields = record_fields(self)
    for f in fields(self):
        if f.name not in getattr(self, NO_SERIALIZE, []):
            if f.name in _rfields:
                value = _rfields[f.name]
                if value is None:
                    value = getattr(self, f.name)
            else:
                value = getattr(self, f.name)

            if value is not None:
                log.info(
                    f'serializing {f.name} of type: "{type(value).__name__}"',
                    "modelclass",
                )
                res[f.name] = serialize(value, context)

    return res


@classmethod
def _deserialize__modelclass(cls, serialized: dict, context: BaseContext):
    processed = dict()
    for f in fields(cls):
        v = serialized.get(f.name, None)
        if v is not None:
            log.info(
                f'deserializing field: "{f.name}" of type: "{getattr(f.type, "__name__", str(f.type))}"',
                "modelclass",
            )
            processed[f.name] = deserialize(v, context)
        elif f.default is MISSING and f.default_factory is MISSING:
            processed[f.name] = v

    return cls(**processed)


def _serialize__modelclass_content_only(self, context: BaseContext = None):
    if context is None:
        context = BaseContext()

    # remove unused fields 
    if config.auto_clean:         
        for v in unused_fields(self):
            remove(v, context)

    # serialize the rest
    res = dict()
    _rfields = record_fields(self)
    for f in fields(self):
        if f.name not in getattr(self, NO_SERIALIZE, []):
            if f.name in _rfields:
                value = _rfields[f.name]
            else:
                value = getattr(self, f.name)

            if value is not None:
                log.info(f'serializing field: "{f.name}"', "modelclass")
                res[f.name] = serialize(value, context, content_only=True)

    return res


@classmethod
def _deserialize__modelclass_content_only(cls, serialized: dict, context: BaseContext):
    processed = dict()
    _rfields = record_fields(cls)
    for f in fields(cls):
        value = serialized.get(f.name, None)
        if value is None:
            if f.default is MISSING and f.default_factory is MISSING:
                processed[f.name] = None
            continue

        log.info(f'deserializing field: "{f.name}"', "modelclass")
        if f.name in _rfields:
            processed[f.name] = deserialize(value, context, expected=Record)
        else:
            processed[f.name] = deserialize(value, context, expected=f.type)

    return cls(**processed)


def is_model(cls):
    """Check if the provided class is a model type."""
    return (
        isinstance(cls, (_blist, _bdict, _bruns))
        or is_modelclass(cls)
        or isinstance(cls, Record)
    )


class _blist(MutableSequence):
    """Base Type for Model Lists."""
    def __init__(
        self,
        iterable: Iterable = None,
        subdir: os.PathLike = "",
        preload: bool = False,
    ):
        """
        Create an instance of this model list.

        :param iterable: Initial content of the list.
        :param str subdir: Specify the default sub-subdirectory for storables.
        :param bool preload: Specify whether storables should be preloaded.
        """
        self.subdir = subdir
        self.preload = preload

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
    
    def __eq__(self, other):
        if isinstance(other, _blist):
            other = list(other)
        return list(self) == other

    def __make_record__(self, itm):
        return record(itm, subdir=self.subdir, preload=self.preload)

    def __serialize__(self, context: BaseContext):
        lst = []

        res = {"store": lst}
        if self.subdir != "":
            res["subdir"] = self.subdir
        if self.preload:
            res["preload"] = self.preload

        if config.auto_clean and len(self.unused) > 0:
            log.info(f"removing unused items ...", f"{type(self).__name__}")
            for itm in self.unused:
                remove(itm, context)
            self.unused = []

        log.info(f"serializing store ...", f"{type(self).__name__}")
        for i, itm in enumerate(self.store):
            log.info(
                f'serializing index: "{i}" of type: "{type(itm).__name__}" ...',
                f"{type(self).__name__}",
            )
            if isinstance(itm, Record):
                if not config.auto_clean or itm.exists():
                    lst.append(serialize(itm, context))
                else:
                    self.unused.append(itm)
            else:
                lst.append(serialize(itm, context))

        if config.auto_clean and len(self.unused) > 0:
            log.info(f"clean dangling pointers ...", f"{type(self).__name__}")
            for itm in self.unused:
                remove(itm, context)
            self.unused = []

        return res

    @classmethod
    def __deserialize__(cls, serialized: dict, context: BaseContext):
        subdir = serialized.get("subdir", "")
        preload = serialized.get("preload", False)

        lst = serialized.get("store", list())
        res = cls(subdir=subdir, preload=preload)

        log.info(f"deserializing list ...", f"{cls.__name__}")
        for i, itm in enumerate(lst):
            log.info(
                f'deserializing index: "{i}" of type: "{type(itm).__name__}" ...',
                f"{cls.__name__}",
            )
            res.append(deserialize(itm, context))

        return res

    def record(
        self,
        value,
        idx: int = None,
        /,
        *,
        stem: str = AUTO,
        suffix: str = AUTO,
        name: str = AUTO,
        subdir: os.PathLike = "",
        preload: str = False,
    ):
        """Record a storable into this list.

        Args:
            value: The value to store.
            idx (int, optional): The index at which to store it (if not specified, the value is appended). Defaults to None.
            stem (str, optional): The stem of a file. Defaults to AUTO.
            suffix (str, optional): The suffix or extension of the file (e.g. ``'.json'``). Defaults to AUTO.
            name (str, optional): The full name of the file. Defaults to AUTO.
            subdir (os.PathLike, optional): The subdirectory in which to store te file. Defaults to "".
            preload (str, optional): When ``True`` the file will be loaded during deserialization. Defaults to False.
        """
        if idx is None:
            self.append(value)
            idx = -1
        else:
            self.insert(idx, value)

        if is_storable(value):
            rec: Record = self.store.__getitem__(idx)
            cfg = Target(
                stem=stem,
                suffix=suffix,
                name=name,
                subdir=os.path.join(rec._target.subdir, subdir),
            )
            rec._target = rec._target.merge(cfg)
            if preload:
                rec.preload = preload

    def __remove__(self, context: BaseContext):
        log.info(f"removing items ...", f"{type(self).__name__}")
        for itm in self.store:
            remove(itm, context)

    def clear(self):
        for i in reversed(range(len(self))):
            del self[i]
        return self

    def __getitem__(self, key):
        itm = self.store.__getitem__(key)
        if isinstance(itm, Record):
            return itm.content
        return itm

    def __setitem__(self, key, value):
        if key < self.__len__():
            itm = self.store.__getitem__(key)
            if isinstance(itm, Record) and is_storable(value):
                if config.auto_clean and is_removable(itm.content):
                    self.unused.append(itm.content)
                itm.content = value
                value = itm
            elif config.auto_clean and is_removable(itm):
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
        if config.auto_clean and is_removable(itm):
            self.unused.append(itm)

    def __iter__(self):
        return (itm.content if isinstance(itm, Record) else itm for itm in self.store)

    def __len__(self):
        return len(self.store)


@serializable(name="_ser__mlist")
class mlist(_blist):
    """Serializable Model List."""
    pass


@storable(name="_sto__mlist")
@serializable(name="_ser__smlist")
class smlist(mlist):
    """Storable Model List."""
    pass


class _bdict(MutableMapping):
    """Base type for Model Dictionaries"""
    def __init__(
        self,
        *,
        subdir: os.PathLike = "",
        preload: bool = False,
        store_by_key: bool = False,
        store_subdir: bool = False
    ):
        """
        Create an instance of this model dictionary.

        :param str subdir: Specify the default sub-subdirectory for storables.
        :param bool preload: Specify whether storables should be preloaded.
        :param bool store_by_key: Sets the stem to the key in the dictionary.
        :param bool store_subdir: Stores files in dedicated subdir based on key.
        :param kwargs: Initial content of the dict.
        """
        self.subdir = subdir
        self.preload = preload

        self._store_by_key = store_by_key
        self._store_subdir = store_subdir

        self.store = dict()
        self.unused = list()

    @classmethod
    def from_dict(
        cls,
        content: dict,
        /,
        *,
        subdir: os.PathLike = "",
        preload: bool = False,
        store_by_key: bool = False,
        store_subdir: bool = False,
    ):
        res = cls(
            subdir=subdir,
            preload=preload,
            store_by_key=store_by_key,
            store_subdir=store_subdir
        )
        res.update(content)
        return res

    def store_by_key(self, subdir: bool = False):
        self._store_by_key = True
        self._store_subdir = subdir

    @property
    def config(self):
        return Target(subdir=self.subdir)

    def __repr__(self):
        dct = {}
        for k in self.keys():
            res = self.store.__getitem__(k)
            if isinstance(res, Record):
                res = res._content
            dct[k] = res

        return dict.__repr__(dct)
    
    def __eq__(self, other):
        if isinstance(other, _bdict):
            other = dict(**other)
        return dict(**self) == other

    def __serialize__(self, context: BaseContext):
        dct = dict()

        res = {"store": dct}
        if self.subdir != "":
            res["subdir"] = self.subdir
        if self.preload:
            res["preload"] = self.preload
        if self._store_by_key:
            res["store_by_key"] = self._store_by_key
        if self._store_subdir:
            res["store_subdir"] = self._store_subdir

        if len(self.unused) > 0:
            log.info(f"removing unused items ...", f"{type(self).__name__}")
            for itm in self.unused:
                remove(itm, context)
            self.unused = []

        log.info(f"serializing store ...", f"{type(self).__name__}")
        for k, itm in self.store.items():
            log.info(
                f'serializing at key: "{k}" of type: "{type(itm).__name__}" ...',
                f"{type(self).__name__}",
            )
            if isinstance(itm, Record):
                if not config.auto_clean or itm.exists():
                    dct[k] = serialize(itm, context)
                else:
                    self.unused.append(itm)
            else:
                dct[k] = serialize(itm, context)

        if config.auto_clean and len(self.unused) > 0:
            log.info(f"clean dangling pointers ...", f"{type(self).__name__}")
            for itm in self.unused:
                remove(itm, context)
            self.unused = []

        return res

    @classmethod
    def __deserialize__(cls, serialized: dict, context: BaseContext):
        dct: dict = serialized.get("store", dict())

        res = cls(
            subdir=serialized.get("subdir", ""),
            preload=serialized.get("preload", False),
            store_by_key=serialized.get("store_by_key", False),
            store_subdir=serialized.get("store_subdir", False)
        )

        log.info(f"deserializing dict ...", f"{cls.__name__}")
        for k, v in dct.items():
            log.info(
                f'deserializing at key: "{k}" of type: "{type(v).__name__}" ...',
                f"{cls.__name__}",
            )
            res[k] = deserialize(v, context)

        return res

    def __make_record__(self, k, v=None):
        key_config = Target()
        if self._store_by_key:
            key_config = key_config.update(stem=k)
        if self._store_subdir:
            key_config = key_config.update(subdir=os.path.join(self.subdir, k))

        if v is None:
            v = dict.__getitem__(k)
        config = self.config.merge(key_config)
        return Record(v, config, self.preload)

    def __remove__(self, context: BaseContext):
        log.info(f"removing items ...", f"{type(self).__name__}")
        for itm in self.store.values():
            remove(itm, context)

    def clear(self):
        for k in list(self.store.keys()):
            del self[k]
        return self

    def __getitem__(self, key):
        itm = self.store.__getitem__(key)
        if isinstance(itm, Record):
            itm = itm.content
            return itm
        return itm

    def __setitem__(self, key, value):
        itm = self.store.pop(key, None)
        if isinstance(itm, Record) and is_storable(value):
            if config.auto_clean and is_removable(itm.content):
                self.unused.append(itm.content)
            itm.content = value
            value = itm  
        elif config.auto_clean and is_removable(itm):
            self.unused.append(itm)
        if is_storable(value):
            value = self.__make_record__(key, value)
        self.store.__setitem__(key, value)

    def record(
        self,
        key,
        value,
        /,
        *,
        stem: str = AUTO,
        suffix: str = AUTO,
        name: str = AUTO,
        subdir: os.PathLike = "",
        preload: str = False,
    ):
        """Record a storable into this dict.

        Args:
            key: The key at which to store the value.
            value: The value to store.
            idx (int, optional): The index at which to store it (if not specified, the value is appended). Defaults to None.
            stem (str, optional): The stem of a file. Defaults to AUTO.
            suffix (str, optional): The suffix or extension of the file (e.g. ``'.json'``). Defaults to AUTO.
            name (str, optional): The full name of the file. Defaults to AUTO.
            subdir (os.PathLike, optional): The subdirectory in which to store te file. Defaults to "".
            preload (str, optional): When ``True`` the file will be loaded during deserialization. Defaults to False.
        """
        self.__setitem__(key, value)
        if is_storable(value):
            rec: Record = self.store.__getitem__(key)
            cfg = Target(
                stem=stem,
                suffix=suffix,
                name=name,
                subdir=os.path.join(rec._target.subdir, subdir),
            )
            rec._target = rec._target.merge(cfg)
            if preload:
                rec.preload = preload

    def __delitem__(self, key):
        itm = self.store.pop(key)
        if config.auto_clean and is_removable(itm):
            self.unused.append(itm)

    def __iter__(self):
        return iter(self.store)

    def __len__(self):
        return len(self.store)


@serializable(name="_ser__mdict")
class mdict(_bdict):
    """Serializable Model Dictionary."""
    pass


@storable(name="_sto__smdict")
@serializable(name="_ser__smdict")
class smdict(_bdict):
    """Storable Model Dictionary."""
    pass


class _bruns(_blist):
    """Base type for Runs."""
    def __init__(
        self,
        iterable: Iterable = None,
        stem: str = "run",
        subdir: os.PathLike = "",
        preload: bool = False,
        store_subdir: bool = True,
    ):
        """
        Create an instance of this labeled model list.

        :param iterable: Initial content of the list.
        :param str stem: The stem used to determine file keys (e.g. stem-0, stem-1, ...).
        :param str subdir: Specify the default sub-subdirectory for storables.
        :param bool preload: Specify whether storables should be preloaded.
        :param bool store_subdir: Specify whether each item should be stored in a separate directory.
        """
        self.stem = stem
        self.run_count = 0
        self.store_subdir = store_subdir

        super().__init__(
            iterable=iterable, subdir=subdir, preload=preload
        )

    @property
    def config(self):
        return Target(subdir=self.subdir)

    def __make_record__(self, itm):
        key = f"{self.stem}-{self.run_count}"
        self.run_count += 1
        key_config = Target(stem=key)
        if self.store_subdir:
            key_config = key_config.update(
                stem=self.stem, subdir=os.path.join(self.subdir, key)
            )
        else:
            key_config = key_config.update(subdir=self.subdir)

        config = self.config.merge(key_config)
        return Record(itm, config, self.preload)

    def __serialize__(self, context: BaseContext):
        res = {"stem": self.stem, "run_count": self.run_count}
        if not self.store_subdir:
            res["store_subdir"] = False
        res.update(super().__serialize__(context))
        return res

    @classmethod
    def __deserialize__(cls, serialized: dict, context: BaseContext):
        res: _bruns = super(_bruns, cls).__deserialize__(serialized, context)
        res.stem = serialized.get("stem")
        res.run_count = serialized.get("run_count")
        res.store_subdir = serialized.get("store_subdir", True)
        return res

    def record(
        self,
        value,
        idx: int = None,
        /,
        *,
        stem: str = AUTO,
        suffix: str = AUTO,
        name: str = AUTO,
        subdir: os.PathLike = "",
        preload: str = False,
    ):
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
            cfg = Target(
                stem=stem,
                suffix=suffix,
                name=name,
                subdir=os.path.join(rec._target.subdir, subdir),
            )
            rec._target = rec._target.merge(cfg)
            if preload:
                rec.preload = preload

    def clear(self):
        _blist.clear(self)
        self.run_count = 0
        return self


@serializable(name="_ser__mruns")
class mruns(_bruns):
    """Serializable Model Runs."""
    pass


@storable(name="_sto__smruns")
@serializable(name="_ser__smruns")
class smruns(_bruns):
    """Storable Model Runs."""
    pass


def mlist_factory(subdir: os.PathLike = "", preload: bool = False):
    """Factory for Model List. Useful in combination with modelclass fields."""
    def factory():
        return mlist(subdir=subdir, preload=preload)

    return factory


def smlist_factory(subdir: os.PathLike = "", preload: bool = False):
    """Factory for Storable Model List. Useful in combination with modelclass fields."""
    def factory():
        return smlist(subdir=subdir, preload=preload)

    return factory


def mdict_factory(
    subdir: os.PathLike = "",
    preload: bool = False,
    store_by_key: bool = False,
    store_subdir: bool = False,
):
    """Factory for Model Dict. Useful in combination with modelclass fields."""
    def factory():
        return mdict(
            subdir=subdir,
            preload=preload,
            store_by_key=store_by_key,
            store_subdir=store_subdir,
        )

    return factory


def smdict_factory(
    subdir: os.PathLike = "",
    preload: bool = False,
    store_by_key: bool = False,
    store_subdir: bool = False,
):
    """Factory for Storable Model Dict. Useful in combination with modelclass fields."""
    def factory():
        return smdict(
            subdir=subdir,
            preload=preload,
            store_by_key=store_by_key,
            store_subdir=store_subdir,
        )

    return factory


def mruns_factory(
    stem: str = "run",
    subdir: os.PathLike = "",
    preload: bool = False,
    store_subdir: bool = True,
):
    """Factory for Model Runs. Useful in combination with modelclass fields."""
    def factory():
        return mruns(
            stem=stem, subdir=subdir, preload=preload, store_subdir=store_subdir
        )

    return factory


def smruns_factory(
    stem: str = None,
    subdir: os.PathLike = "",
    preload: bool = False,
    store_subdir: bool = True,
):
    """Factory for Storable Model Runs. Useful in combination with modelclass fields."""
    def factory():
        return smruns(
            stem=stem, subdir=subdir, preload=preload, store_subdir=store_subdir
        )

    return factory
