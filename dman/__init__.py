from dman.persistent.modelclasses import modelclass, recordfield, mdict, smdict, mlist, smlist, mruns
from dman.persistent.modelclasses import smlist_factory, smdict_factory, mruns_factory, mdict_factory
from dman.persistent.serializables import serializable, serialize, deserialize
from dman.persistent.record import record, context, remove
from dman.persistent.storables import storable, write, read
from dman.persistent.configclasses import configclass, section
from dman.repository import track, save, load
from dman.utils import sjson
from dman.utils.smartdataclasses import idataclass

from dataclasses import field, dataclass

@dataclass
class __Defaults:
    validate: bool = False


defaults = __Defaults()