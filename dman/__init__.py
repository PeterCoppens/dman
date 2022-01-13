from dman.persistent.modelclasses import modelclass, recordfield, mdict, smdict, mlist, smlist, mruns, serializefield
from dman.persistent.modelclasses import smlist_factory, smdict_factory, mruns_factory, mdict_factory
from dman.persistent.serializables import serializable, serialize, deserialize
from dman.persistent.record import record,  remove
from dman.verbose import context
from dman.persistent.storables import storable, write, read
from dman.persistent.configclasses import configclass, section
from dman.repository import track, save, load, RootError
from dman.utils import sjson
from dman.utils.smartdataclasses import idataclass

import logging
from dataclasses import field, dataclass

from dman.repository import get_root_path as __root_path
import os as __os
import dman.verbose as __verbose


def setup(logfile: str = None):
    if logfile is not None:
        logfile = __os.path.join(__root_path(), logfile)
        base, _ = __os.path.split(logfile)
        if not __os.path.isdir(base):
            __os.mkdir(base)
            
        log = __verbose.VerboseContext.LOGGER
        for hdlr in log.handlers[:]:
            log.removeHandler(hdlr)
        log.addHandler(logging.FileHandler(logfile))