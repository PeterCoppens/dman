from dman.persistent.serializables import serializable
from dman.persistent.storables import storable
from dman.persistent.modelclasses import recordfield, serializefield
from dman.utils import sjson

from typing import Union

try:
    import numpy as np
except ImportError as e:
    raise ImportError('Numeric tools require numpy.') from e


@storable(name='_num__barray')
class barray(np.ndarray):
    __ext__ = '.npy'

    def __write__(self, path):
        with open(path, 'wb') as f:
            np.save(f, self)

    @classmethod
    def __read__(cls, path):
        with open(path, 'rb') as f:
            res: np.ndarray = np.load(f)
            return res.view(cls)


@serializable(name='_num__sarray')
class sarray(np.ndarray):
    def __serialize__(self):
        if self.ndim == 1:
            return sjson.dumps(self.tolist())
        return [sarray.__serialize__(a) for a in self]

    @classmethod
    def __deserialize__(cls, obj: Union[list, str]):
        if isinstance(obj, str):
            return np.asarray(sjson.loads(obj)).view(cls)
        return np.asarray([sarray.__deserialize__(a) for a in obj]).view(cls)


@serializable(name='_num__carray')
class carray(sarray):
    def __eq__(self, other):
        return np.array_equal(self, other)


def barrayfield(*, as_type: type = None, **kwargs):
    def to_barray(arg):
        if isinstance(arg, np.ndarray):
            arg = arg.view(barray)
        if as_type is not None:
            arg = arg.astype(as_type)
        return arg          
    return recordfield(**kwargs, pre=to_barray)


def sarrayfield(*, as_type: type = None, compare: bool = False, **kwargs):
    def to_sarray(arg):
        if isinstance(arg, np.ndarray):
            arg = arg.view(carray) if compare else arg.view(sarray)
        if as_type is not None:
            arg = arg.astype(as_type)
        return arg                
    return serializefield(**kwargs, pre=to_sarray)
