"""
Defining Storables
========================

This example describes ways in which one can define storable objects.
"""

# %%
# Sometimes it is not feasible to serialize an object. For example large 
# arrays in ``numpy``. The ``dman`` framework supports such objects 
# through ``storables``. These should interface with the ``read`` and ``write``
# methods as follows
#
# .. code-block:: python
#
#       import dman
#       dman.write(obj, 'obj.out')
#       assert(obj == dman.read(type(obj), 'obj.out'))
#
# No standard objects are storable. They should be defined by the user:

import dman
import numpy as np

@dman.storable(name="_num__barray")
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

# %%
# The ``barray`` class is also provided in ``dman.numeric`` which can 
# be imported when ``numpy`` is installed. We can use it as follows:

dman.write(np.eye(3).view(barray), 'array.npy')
array = dman.read(barray, 'array.npy')
print(array)

# %%       
# .. warning::
#
#     Again, the specified name should be unique for all storables.
#     It can be the same as a name of a serializable object. A name can 
#     also be automatically generated similar to ``serializable`` when it is left unspecified.
#     The name can be used instead of the type when reading, which is used by the 
#     more complex objects in ``dman``. 
#
#     .. code-block:: python
#
#         dman.read('_num__barray', 'array.npy')
#
# It is also possible to automatically produce storables from 
# dataclasses or serializable objects. With both json is used to 
# store the object, however with a dataclass we use the default ``asdict``
# method to convert it to a dictionary, which only works for certain types of fields.


from dataclasses import dataclass

@dman.storable(name='manual')
@dataclass
class DCLBasic:
    value: str

@dman.storable(name='manual')
@dman.serializable(name='manual')
@dataclass
class SerBasic:
    value: str

# %% 
# Both types result in the same ``json`` file:
dman.write(DCLBasic(value='hello world!'), 'dcl.json')
with open('dcl.json', 'r') as f:
    print(f.read())


# %%
# .. note::
#
#     It is not recommended to create storables from dataclasses as above. 
#     Instead one should use the more powerful ``modelclass`` decorator
#     with ``storable=True`` TODO add reference. The reason is that ``modelclass`` supports 
#     storables as fields, where this method does not. 
