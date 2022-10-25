"""
Toolbox for experimental data management in Python.
"""

__version__ = '0.0.0'

from dman.core.serializables import serializable, serialize, deserialize, BaseContext
from dman.core.serializables import ser_type2str, ser_str2type, register_serializable
from dman.core.serializables import isvalid, ValidationError, SerializationError
from dman.core.storables import storable, write, read, register_storable
from dman.core.path import get_directory, get_root_path, logger_context
from dman.core import log

from dman.model.record import record, remove, context
from dman.model.modelclasses import modelclass, recordfield, mdict, smdict, mlist, smlist, mruns, smruns, serializefield
from dman.model.modelclasses import smlist_factory, smdict_factory, smruns_factory, mruns_factory, mdict_factory, mlist_factory
from dman.model.configclasses import configclass, section
from dman.model.repository import track, save, load, store
from dman.model.repository import uninterrupted

from dman.utils import sjson
from dman.utils.smartdataclasses import idataclass, AUTO

try:
    import dman.numeric as numeric
    _numeric_available = True
except ImportError as e:
    _numeric_available = False

try:
    import dman.tui as tui
    _tui_available = True
except ImportError as e:
    _tui_available = False


from dataclasses import field, dataclass

