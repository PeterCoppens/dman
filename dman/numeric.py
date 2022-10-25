from dman.core.serializables import serializable, register_serializable
from dman.core.storables import storable
from dman.model.modelclasses import recordfield, serializefield
from dman.utils import sjson
from dman.model.record import Context

from typing import Union
import numpy as np


@storable(name="_num__barray")
class barray(np.ndarray):
    __ext__ = ".npy"

    def __write__(self, path):
        with open(path, "wb") as f:
            np.save(f, self)

    @classmethod
    def __read__(cls, path):
        with open(path, "rb") as f:
            res: np.ndarray = np.load(f)
            return res.view(cls)


@serializable(name="_num__sarray")
class sarray(np.ndarray):
    def __serialize__(self):
        if self.ndim == 0:
            return sjson.dumps(float(self))
        if self.size == 0:
            return {"shape": sjson.dumps(self.shape)}
        elif self.ndim == 1:
            return sjson.dumps(self.tolist())
        return [sarray.__serialize__(a) for a in self]

    @classmethod
    def __deserialize__(cls, obj: Union[list, str]):
        if isinstance(obj, str):
            return np.asarray(sjson.loads(obj)).view(cls)
        if isinstance(obj, dict):
            return np.zeros(sjson.loads(obj.get("shape")))
        if isinstance(obj, (float, int)):
            return np.asarray(obj).view(cls)
        return np.asarray([sarray.__deserialize__(a) for a in obj]).view(cls)


@serializable(name="_num__carray")
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


def sarrayfield(
    *,
    as_type: type = None,
    compare: bool = False,
    empty_as_none: bool = False,
    **kwargs
):
    def to_sarray(arg):
        if isinstance(arg, (list, tuple)):
            arg = np.array(arg)
        if isinstance(arg, np.ndarray):
            arg = arg.view(carray) if compare else arg.view(sarray)
        if as_type is not None:
            arg = arg.astype(as_type)
        if empty_as_none and np.size(arg) == 0:
            arg = None
        return arg

    return serializefield(**kwargs, pre=to_sarray)


from dman.utils.sjson import register_atomic_alias
register_atomic_alias(np.int32, int)
register_atomic_alias(np.int64, int)
register_atomic_alias(np.float32, float)
register_atomic_alias(np.float64, float)


register_serializable(
    '_num__ndarray',
    np.ndarray,
    serialize=lambda ser: ser.view(sarray).__serialize__(),
    deserialize=lambda ser: sarray.__deserialize__(ser).view(np.ndarray),
)


if __name__ == "__main__":
    import dman

    ser = dman.save("array", np.eye(10))
    print(dman.sjson.dumps(ser, indent=4))
    print(dman.load('array'))
