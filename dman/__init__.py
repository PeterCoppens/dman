"""
Toolbox for experimental data management in Python.
"""

__version__ = '1.0'

from dman.core.serializables import serializable, serialize, deserialize, BaseContext, is_serializable
from dman.core.serializables import ser_type2str, ser_str2type, register_serializable, register_instance
from dman.core.serializables import isvalid, ValidationError, SerializationError
from dman.core.storables import FileTarget
from dman.core.storables import storable, write, read, register_storable
from dman.core.path import mount, target, get_root_path, AUTO
from dman.core import log

from dman.model.record import record, remove, Context
from dman.model.modelclasses import recordfield, mdict, smdict, mlist, smlist, mruns, smruns, serializefield, modelclass
from dman.model.modelclasses import smlist_factory, smdict_factory, smruns_factory, mruns_factory, mdict_factory, mlist_factory
from dman.model.modelclasses import record_fields, unused_fields, register_preset
from dman.model.repository import track, save, load, store, clean
from dman.model.repository import uninterrupted, context

from dman.utils import sjson
from dman.utils.smartdataclasses import idataclass, configclass, optionfield, is_configclass

from dman.config import params

try:
    import dman.numeric as numeric
    from dman.numeric import barray, sarray, carray
    _numeric_available = True
except ImportError as e:
    _numeric_available = False
    barray, sarray, carray = None, None, None

try:
    import dman.tui as tui
    _tui_available = True
except ImportError as e:
    _tui_available = False


from dataclasses import field, dataclass

