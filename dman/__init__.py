from dman.persistent.modelclasses import modelclass, recordfield, mdict, smdict, mlist, smlist
from dman.persistent.serializables import serializable, serialize, deserialize
from dman.persistent.storeables import storeable
from dman.repository import track, save, load
from dman.utils import sjson

from dataclasses import field, dataclass

@dataclass
class __Defaults:
    validate: bool = False


defaults = __Defaults()