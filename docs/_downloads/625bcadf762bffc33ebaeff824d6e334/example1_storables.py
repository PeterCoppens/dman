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
# There are several ways to define ``storable`` types. We provide an overview 
# here.

from tempfile import TemporaryDirectory
import os
import dman
import numpy as np

# %%
# Manual Definition
# ^^^^^^^^^^^^^^^^^^^^^^^
#
# The first method is to define writing and reading behavior in the signature
# of the class.

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

with TemporaryDirectory() as base:
    path = os.path.join(base, 'array.npy')
    dman.write(np.eye(3).view(barray), path)
    array = dman.read(barray, path)
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
with TemporaryDirectory() as base:
    path = os.path.join(base, 'dcl.json')
    dman.write(DCLBasic(value='hello world!'), path)
    with open(path, 'r') as f:
        print(f.read())


# %%
# .. note::
#
#     It is not recommended to create storables from dataclasses as above. 
#     Instead one should use the more powerful ``modelclass`` decorator
#     with ``storable=True``. The reason is that ``modelclass`` supports 
#     storables as fields, where this method does not. See :ref:`sphx_glr_gallery_fundamentals_example3_models.py`
#     for an overview of the ``modelclass`` decorator. 

# %%
# Registered Definition
# ^^^^^^^^^^^^^^^^^^^^^^^
#
# Similarly to ``serializable`` types you can also define a custom 
# ``storable`` type without touching the original class.
# For a more complete example see :ref:`sphx_glr_gallery_cases_example_pandas.py`.


class Frozen:    
    def __init__(self, data: int):
        self.data = data
    
    def __repr__(self):
        return f'{self.__class__.__name__}(data={self.data})'


def _write_frozen(frozen: Frozen, path: os.PathLike):
    """Write frozen to disk."""
    with open(path, 'w') as f:
        f.write(frozen.data)
    

def _read_frozen(path: os.PathLike):
    """Read frozen from disk."""
    with open(path, 'r') as f:
        return Frozen(int(f.read()))


dman.register_storable(
    'frozen', 
    Frozen, 
    write=_write_frozen, 
    read=_read_frozen
)

# %%
# Creating Multiple Files
# ^^^^^^^^^^^^^^^^^^^^^^^^^
#
# Advanced users might want to have storables create more than one file.
#
# .. warning::
#       
#       It is usually best to have a ``storable`` write to just one file.
#       Whenever you require multiple classes then it is usually better 
#       to wrap them in a ``serializable`` class like the models 
#       provided by ``dman`` (e.g. ``mlist``, ``mdict``, ``modelclass``). 
#       See :ref:`sphx_glr_gallery_fundamentals_example3_models.py` for details.
#
# If you do want to have storables create multiple files, this is possible,
# but you should do so in such a way that ``dman`` can safely keep track of
# the created files. We provide an example below.

@dman.storable
class Multiple:
    def __init__(self, value: str, description: str):
        self.value = value
        self.description = description

    def __write__(self, path: os.PathLike, context: dman.Context):
        # The provided path always points to a specific file associated 
        # with this storable. So you can use it for the main file.
        with open(path, 'w') as f:
            f.write(self.value)

        # For additional files however you need to use the ``context`` 
        # to keep track of them. You can do so as follows:
        with context.open('description.txt', 'w') as f:
            f.write(self.description)

        # The context keeps track of the current directory to which writing
        # occurs. So you usually specify the path relative to it. 

    @classmethod
    def __read__(cls, path: os.PathLike, context: dman.Context):
        # Reading occurs similarly. 
        with open(path, 'r') as f:
            value = f.read()

        with context.open('description.txt', 'r') as f:
            description = f.read()
        
        return cls(value, description)
    
    def __remove__(self, context: dman.Context):
        # Since ``dman`` also removes files when they are no longer tracked
        # you should define a ``__remove__`` method that deletes 
        # any additional files you created. To do so you can use the provided 
        # context again. The removal of the main file is handled by 
        # the record. 
        context.remove('description.txt')

# %%
# We will show how to interact with the storable using a ``record`` 
# here. For more information on how to use those see 
# :ref:`sphx_glr_gallery_fundamentals_example2_records.py`. 
# To see when ``dman`` requires the ``__remove__`` method to 
# delete untracked files, see :ref:`sphx_glr_gallery_fundamentals_example3_models.py`.

with TemporaryDirectory() as base:
    ctx = dman.Context.from_directory(base)     # we will need a context.

    # Create the storable and add it to a record.
    # The record will handle all path specifications automatically.
    mult = Multiple('John Snow', 'The name of the current user.')
    rec = dman.record(mult, stem='value')

    # We can store the file through serialization.
    ser = dman.serialize(rec, context=ctx)
    print('record data:')
    dman.tui.print_serializable(ser)
    print('files:')
    dman.tui.walk_directory(base, show_content=True)

    # Remove all files associated with the record
    dman.remove(rec, context=ctx)  
    print('files after removal:')
    dman.tui.walk_directory(base, show_content=True)


# %%
# To avoid having to manually use ``context`` and ``__remove__``,
# which can likely cause errors we also show a similar implementation
# of the above. The above functionality can usually be avoided like this.
# We use a ``modelclass``. Details on these can be found in  
# :ref:`sphx_glr_gallery_fundamentals_example3_models.py`.


# Create an atomic storable type, creating only one file.
@dman.storable
class StringFile:
    def __init__(self, value: str):
        self.value = value

    def __write__(self, path):
        with open(path, 'w') as f:
            f.write(self.value)

    @classmethod
    def __read__(cls, path):
        with open(path, 'r') as f:
            return cls(f.read())


# Automatically convert values to string files in a ``modelclass``.
dman.register_preset(StringFile, lambda s: StringFile(s))


# Create the modelclass that contains the atomic storable types.
@dman.modelclass(store_by_field=True, compact=True)
class Multiple:
    value: StringFile
    description: StringFile


# %%
# We can now store the instance in a similar way to before, but now without 
# requiring a ``record``. 

with TemporaryDirectory() as base:
    ctx = dman.Context.from_directory(base)     # we will need a context.

    # Create the modelclass.
    mult = Multiple('John Snow', 'The name of the current user.')

    # We can store the file through serialization.
    ser = dman.serialize(mult, context=ctx)
    print('the modelclass data:')
    dman.tui.print_serializable(ser)
    print('files:')
    dman.tui.walk_directory(base, show_content=True)

    # Remove all files associated with the modelclass
    dman.remove(mult, context=ctx)  
    print('files after removal:')
    dman.tui.walk_directory(base, show_content=True)

# %%
# The resulting files are also much more readable, since the modelclass 
# now tells a user what the created files are associated to.