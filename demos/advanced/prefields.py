from dman import modelclass, serializefield, recordfield, dataclass, storable, track, setup
import numpy as np

import os
from dataclasses import MISSING, Field

from dman.model.record import Record
from dman.utils.smartdataclasses import AUTO

setup(logfile='log.ansi')


@storable(name='sarray')
class sarray(np.ndarray):
    __ext__ = '.npy'

    def __write__(self, path):
        with open(path, 'wb') as f:
            np.save(f, self)

    @classmethod
    def __read__(cls, path):
        with open(path, 'rb') as f:
            res: np.ndarray = np.load(f)
            return res.view(cls)

def sarrayfield(*, default=MISSING, default_factory=MISSING,
                init: bool = True, repr: bool = False,
                hash: bool = False, compare: bool = False, metadata=None,
                stem: str = AUTO, suffix: str = AUTO, name: str = AUTO, subdir: os.PathLike = '', 
                preload: str = False
                ) -> Field:

    def to_sarray(arg):
        if isinstance(arg, np.ndarray):
            return arg.view(sarray)
        return arg                

    return recordfield(default=default, default_factory=default_factory, 
        init=init, repr=repr, hash=hash, compare=compare, metadata=metadata, 
        stem=stem, suffix=suffix, name=name, 
        subdir=subdir, preload=preload, pre=to_sarray)


def to_string(arg):
    return str(arg)


@modelclass(storable=True)
@dataclass
class Storable:
    fld: str = serializefield(pre=to_string)


def to_storable(arg):
    if isinstance(arg, Storable) or isinstance(arg, Record):
        return arg
    return Storable(arg)


@modelclass(compact=True)
@dataclass
class Model:
    o: Storable
    a: Storable = serializefield(pre=to_storable)
    b: Storable = recordfield(pre=to_storable)
    c: sarray = sarrayfield(stem='array')

if __name__ == '__main__':
    arr = np.array([1,2,3])
    df = Model(o=Storable('hello'), a=5, b=2.4, c=arr)
    with track(key='model', default=df, verbose=True) as model:
        model: Model = model
        print(model.a)
        print(model.b)
        print(model.c)
        print(model.o)