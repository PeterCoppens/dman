import numpy as np
from dman.persistent.storables import storable
from dman.persistent.modelclasses import recordfield

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


def barrayfield(**kwargs):
    def to_sarray(arg):
        if isinstance(arg, np.ndarray):
            return arg.view(barray)
        return arg                
    return recordfield(**kwargs, pre=to_sarray)