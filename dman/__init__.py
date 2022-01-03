from dman.persistent.modelclasses import modelclass, recordfield, mdict, smdict, mlist, smlist
from dman.persistent.modelclasses import smlist_factory, smdict_factory
from dman.persistent.serializables import serializable, serialize, deserialize
from dman.persistent.record import record, record_context
from dman.persistent.storables import storable, write, read
from dman.repository import track, save, load
from dman.utils import sjson

from dataclasses import field, dataclass

@dataclass
class __Defaults:
    validate: bool = False


defaults = __Defaults()