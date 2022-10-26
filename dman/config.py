from dataclasses import dataclass
from dman.core import serializables
from dman.core import storables
from dman.utils.smartdataclasses import configclass

@configclass
@dataclass
class Config:
    serialize: serializables.Config = serializables.config
    store: storables.Config = storables.config

params = Config()