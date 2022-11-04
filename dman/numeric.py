from dman.core.serializables import serializable, register_serializable
from dman.core.storables import storable
from dman.model.modelclasses import register_preset
from dman.utils import sjson
import dman.model.modelclasses

from typing import Type, Union
import numpy as np


class _typed_array(type):
    __cached__ = dict()

    def __getitem__(cls, tp: Type):
        res = _typed_array.__cached__.get((cls, tp), None)
        if res is not None:
            return res

        name = f"{cls.__name__}[{tp.__name__}]"
        res = _typed_array.__new__(
            _typed_array, name, (cls,), {"__qualname__": name, "__module__": __name__}
        )
        register_preset(
            res,
            lambda arg: arg.view(res).astype(tp)
            if isinstance(arg, np.ndarray)
            else arg,
        )
        _typed_array.__cached__[(cls, tp)] = res
        return res


@storable(name="_num__barray")
class barray(np.ndarray, metaclass=_typed_array):
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
class sarray(np.ndarray, metaclass=_typed_array):
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
class carray(np.ndarray, metaclass=_typed_array):
    def __eq__(self, other):
        return np.array_equal(self, other)

    def __serialize__(self):
        return self.view(sarray).__serialize__()

    @classmethod
    def __deserialize__(cls, obj: Union[list, str]):
        return sarray.__deserialize__(obj).view(cls)


register_preset(
    barray, lambda arg: arg.view(barray) if isinstance(arg, np.ndarray) else arg
)
register_preset(
    carray, lambda arg: arg.view(carray) if isinstance(arg, np.ndarray) else arg
)
register_preset(
    sarray, lambda arg: arg.view(sarray) if isinstance(arg, np.ndarray) else arg
)


from dman.utils.sjson import register_atomic_alias

register_atomic_alias(np.int32, int)
register_atomic_alias(np.int64, int)
register_atomic_alias(np.float32, float)
register_atomic_alias(np.float64, float)


register_serializable(
    "_num__ndarray",
    np.ndarray,
    serialize=lambda ser: ser.view(sarray).__serialize__(),
    deserialize=lambda ser: sarray.__deserialize__(ser).view(np.ndarray),
)


if __name__ == "__main__":
    import dman

    ser = dman.save("array", np.eye(10))
    print(dman.sjson.dumps(ser, indent=4))
    print(dman.load("array"))
