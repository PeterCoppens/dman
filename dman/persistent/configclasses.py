from collections.abc import MutableMapping
from dataclasses import dataclass, field, is_dataclass, fields
import inspect
from typing import Dict

from dman.persistent.storeables import WRITE, READ, storeable
from dman.persistent.modelclasses import modelclass
from dman.persistent.serializables import BaseContext, serialize, deserialize
from dman.persistent.record import Record

import configparser
import json

SECTION_ATTR = '__sec__type'
SECTION_NAME = '__sec__name'


def is_section(obj):
    if not inspect.isclass(obj):
        return False
    return getattr(obj, SECTION_ATTR, False)


def get_sections(cls):
    if not is_dataclass(cls):
        return {}

    res = {}
    for fld in fields(cls):
        res[fld.name] = getattr(cls, fld.name)

    return res


def get_section_types(cls):
    if not is_dataclass(cls):
        return {}

    res = {}
    for fld in fields(cls):
        res[fld.name] = getattr(cls, fld.name)

    return res


def section(cls=None, /, *, name: str = None, **kwargs):
    def wrap(cls):
        setattr(cls, SECTION_ATTR, True)
        return modelclass(cls, name=name, **kwargs)

    # See if we're being called as @section or @section().
    if cls is None:
        # We're called with parens.
        return wrap

    # We're called as @section without parens.
    return wrap(cls)


def configclass(cls=None, /, *, name: str = None):
    def wrap(cls):
        setattr(cls, Record.EXTENSION, getattr(cls, Record.EXTENSION, '.ini'))

        annotations: dict = cls.__dict__.get('__annotations__', dict())
        for sect, obj in annotations.items():
            if is_section(obj):
                setattr(cls, sect, field(default_factory=obj))

        if getattr(cls, WRITE, None) is None:
            setattr(cls, WRITE, _write__config)

        if getattr(cls, READ, None) is None:
            setattr(cls, READ, _read__config)

        return storeable(dataclass(cls), name=name)

    # See if we're being called as @configclass or @configclass().
    if cls is None:
        # We're called with parens.
        return wrap

    # We're called as @configclass without parens.
    return wrap(cls)


def _write__config(self, path: str, serializer: BaseContext = None):
    cfg = configparser.ConfigParser()
    for section in get_sections(self):
        cfg.add_section(section)
        content: dict = serialize(getattr(self, section), serializer, content_only=True)
        processed = {}
        for k, v in content.items():
            processed[k] = json.dumps(v)

        cfg[section] = processed

    with open(path, 'w') as f:
        cfg.write(f)


@classmethod
def _read__config(cls, path: str, context: BaseContext = None):
    cfg = configparser.ConfigParser()
    cfg.read(path)

    res = cls()

    section_types = get_sections(res)
    for k, v in section_types.items():
        if k not in cfg.sections():
            continue

        content = dict(cfg[k])

        processed = {}
        for kk, vv in content.items():
            processed[kk] = json.loads(vv)

        setattr(res, k, deserialize(processed, context, ser_type=v))

    return res


@section(name='_sec__dict')
class dictsection(MutableMapping):
    def __init__(self, content: dict):
        self.store = content

    def __getitem__(self, key):
        return self.store.__getitem__(key)

    def __setitem__(self, key, value: str):
        self.store.__setitem__(self.store, key, value)

    def __delitem__(self, value) -> None:
        return self.store.__delitem__(value)

    def __iter__(self):
        return iter(self.store)

    def __len__(self):
        return len(self.store)

    def __serialize__(self):
        return self.store

    @classmethod
    def __deserialize__(cls, serialized: dict):
        return cls(serialized)
