from dataclasses import dataclass
from dman.core import serializables
from dman.core import path
from dman.model import modelclasses
from dman.utils.smartdataclasses import configclass

@configclass
class Config:
    serialize: serializables.Config = None
    store: path.Config = None
    model: modelclasses.Config = None


params = Config(
    serializables.config, 
    path.config, 
    modelclasses.config
)