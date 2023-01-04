"""
Model Types
========================

The objects you will use most frequently in ``dman`` are models. 
"""

# %%
# Modelclass
# ----------------------
# We start with the most flexible model type, the ``modelclass``.
# Like all models it extends a classical Python class to handle storables.
# Internally it uses ``record`` instances to do so. Hence reading up
# on those in :ref:`sphx_glr_gallery_fundamentals_example2_records.py`
# could be helpful. Defining a ``modelclass`` is similar to defining a
# ``dataclass``. We will be creating one to store numpy arrays.

import dman
from dman.numeric import sarray, barray
import numpy as np

dman.log.default_config(level=dman.log.WARNING)


@dman.modelclass
class Container:
    label: str
    points: sarray[int]
    values: barray


# %%
# We will be working in a temporary directory
from tempfile import TemporaryDirectory

base = TemporaryDirectory().name

# %%
# We can serialize the container like any other serializable type.
container = Container("experiment", np.arange(5), np.random.randn(4))
dman.save("container", container, base=base)
dman.tui.walk_directory(dman.mount("container", base=base), show_content=True)

# %%
# Note that the contents of the container are serialized as if it were a dataclass.
# However the ``barray`` has been replaced by a record, pointing to a file.
container: Container = dman.load("container", base=base)
dman.tui.pprint(dman.record_fields(container))

# %%
# This record is not preloaded, so the value of the barray will only be loaded
# when the field is accessed.
print(container.values)
dman.tui.pprint(dman.record_fields(container))

# %%
# So we know that the modelclass has an internal notion of records.
# We can use this to specify the target of the ``barray``.
# The most configurable option is to just set the record manually

container.values = dman.record(np.random.randn(5).view(barray), stem="barray")
dman.save("container", container, base=base)
dman.tui.walk_directory(dman.mount("container", base=base), show_content=True)

# %%
#
# .. note::
#       Note that the old file has been removed automatically, since the record
#       tracking it has been removed. This avoids cluttering your
#       ``.dman`` directory with untracked files. We could turn this auto cleaning
#       behavior off as follows:
#
#       .. code-block:: python
#
#           dman.params.model.auto_clean = False
#
#
# When specifying the record we had to manually convert a numpy array to
# a ``barray``. This happens automatically in the ``modelclass``. You can use
# the ``dman.register_preset`` method to do this for your own types.
#
# .. autofunction:: dman.register_preset
#     :noindex:
#
# It will be useful to access the record configuration in other ways.
# After all, for most instances of the modelclass we likely want the same
# file names. Here the ``recordfield`` comes in.


@dman.modelclass
class Container:
    label: str
    points: sarray[int]
    values: barray = dman.recordfield(stem="barray")


# %%
# We can see that the stem has been adjusted.
container = Container("experiment", np.arange(5), np.random.randn(4))
dman.save("container", container, base=base)
dman.tui.walk_directory(dman.mount("container", base=base), show_content=True)

# %%
# Specifying stems like this comes at a risk however. If we save two instances
# of ``Container`` to the same folder, the ``barray.npy`` file will be reused.

c1 = Container("experiment", np.arange(5), np.random.randn(4))
c2 = Container("experiment", np.arange(5), np.random.randn(4))
_ = dman.save("list", [c1, c2], base=base)

# %%
# By default ``dman`` gives a warning and then overrides the file.
# This implies that you should change your file hierarchy.
# Later we will show how to do so correctly. You can also configure
# ``dman`` to resolve this issue in other ways.
#
# One option is to automatically add an index to the file whenever this happens.
dman.params.store.on_retouch = "auto"
c1 = Container("experiment", np.arange(5), np.random.randn(4))
c2 = Container("experiment", np.arange(5), np.random.randn(4))
_ = dman.save("list", [c1, c2], base=base)
dman.tui.walk_directory(dman.mount("list", base=base))

# %%
# Other options are
#   - ``'quit'``: The serialization process is cancelled.
#   - ``'prompt'``: Prompt the user for a file name.

# %%
# The ``recordfield`` has all the options of ``field`` and ``record`` combined.
# Feel free to experiment with them. We can also configure stems globally.


@dman.modelclass(store_by_field=True)
class Container:
    label: str
    points: sarray[int]
    values: barray


container = Container("experiment", np.arange(5), np.random.randn(4))
dman.save("fields", container, base=base)
dman.tui.walk_directory(
    dman.mount("fields", base=base),
)


# %%
# The ``modelclass`` decorator has all the options that ``dataclass``
# has and some additional ones. 
#
# .. autofunction:: dman.modelclass
#     :noindex:
#
# We provide examples of some of the more advanced features at work below
# 
# **1. subdirectories**:
# We showcase how subdirectories are determined in a ``modelclass``.

@dman.modelclass(cluster=True, subdir='data', store_by_field=True)
class Container:
    root: barray = dman.recordfield(default_factory=lambda: np.ones(3))
    inner: barray = dman.recordfield(default_factory=lambda: np.ones(3), subdir='override')

dman.save('subdirectories', Container(), base=base)
dman.tui.walk_directory(dman.mount('subdirectories', base=base))

# %%
# **2. compact**:
# We showcase how compact works. Note how no types are mentioned.

@dman.modelclass(compact=True)
class Person:
    name: str = 'Cave Johnson'
    age: int = 43
    location: sarray = dman.field(default_factory=lambda: np.array([3.0, 5.0, -100.0]))

dman.tui.print_serializable(Person())


# %%
# **3. skipping serialization**:
# One can designate certain fields to not be serialized.

@dman.modelclass
class Adder:
    __no_serialize__ = ['ans']
    x: int
    y: int
    ans: int = None

    def eval(self):
        self.ans = self.x + self.y

add = Adder(3.0, 5.0)
add.eval()
dman.tui.print_serializable(add)

# %%
# **4. deciding between storing and serializing**:
# Some objects can be both serialized and stored. This is how you can choose 
# which option to use. We also showcase some other advanced features, like storable 
# modelclasses and presets.

# This class is a storable and a serializable
@dman.modelclass(storable=True)
class Fragment:
    value: str

# Presets can be used to automatically convert strings to fragments.
dman.register_preset(
    Fragment, lambda obj: Fragment(obj) if isinstance(obj, str) else obj
)

# Specify fragment fields in a variety of ways.
@dman.modelclass(compact=True, store_by_field=True)
class Fragmenter:
    frag0: Fragment = dman.recordfield()
    frag1: Fragment = dman.field()
    frag3: Fragment
    frag4: Fragment = dman.serializefield()


dman.save('fragmenter', Fragmenter('stored', 'also stored', 'stored too', 'serialized'), base=base)
dman.tui.walk_directory(dman.mount('fragmenter', base=base), show_content=True)


# %%
# Model List
# --------------------------
#
# After modelclasses we have some model type equivalents of basic Python types. 
# The first of which is the model list or :class:`mlist`. These are lists that 
# can contain storables using records as is the case with modelclasses.
# They are used automatically by ``dman``. 

a = np.ones(3).view(dman.barray)
b = np.zeros(3).view(dman.barray)
c = np.arange(3).view(dman.barray)

lst = [a, b]
dman.save('lst', lst, base=base)
dman.tui.walk_directory(dman.mount('lst', base=base), show_content=True)

# %%
# If we load the list from disk we can see that its type has changed.
lst: dman.mlist = dman.load('lst', base=base)
print(type(lst))

# %%
# The internal records can be accessed as follows:
for v in lst.store:
    print(v)

# %%
# You can directly configure a record using the ``record`` method.
lst.record(c, stem='c')
dman.save('lst', lst, base=base)
dman.tui.walk_directory(dman.mount('lst', base=base))

# %%
# If you want a storable version of an :class:`mlist` you can use :class:`smlist`.
# Beyond being storable it acts identical to :class:`mlist` in every way.

# %%
# Often you want to specify file names for the internal records incrementally.
# Using the ``record`` method each time is not convenient however. 
# Hence :class:`mruns` (and :class:`smruns`) are provided, which do so automatically.

runs = dman.mruns([a, b, c], stem='run', store_subdir=False)
dman.save('runs', runs, base=base)
dman.tui.walk_directory(dman.mount('runs', base=base))

# %%
# Here ``store_subdir=False`` specifies that storables should be stored in 
# the root directory of the ``mruns`` object. Usually if your storables create 
# more files it is better to set ``store_subdir=True`` instead. Then each
# storable is stored in its own directory.


# %%
# Model Dictionary
# ------------------------
#
# Similarly to model lists, ``dman`` also provides the model dictionary :class:`mdict` (:class:`smdict`). 
# On a basic level, file names for storables are generated automatically.

dct = {'a': a, 'b': b}
dman.save('dct', dct, base=base)
dman.tui.walk_directory(dman.mount('dct', base=base), show_content=True)

# %%
# Standard dictionaries are converted to model dictionaries automatically
# whenever they contain storables.
dct: dman.mdict = dman.load('dct', base=base)
print(type(dct))

# %%
# Similarly to model lists you can access the internal records as follows
for k, v in dct.store.items():
    print(k, v)

# %%
# You can also specify records directly
dct.record('a', c, stem='c')
dman.save('dct', dct, base=base)
dman.tui.walk_directory(dman.mount('dct', base=base))

# %%
# Model dictionaries come with some additional settings that can aid in 
# automatically generating suitable stems.

dct = dman.mdict.from_dict({'a': a, 'b': b, 'c': c}, store_by_key=True, store_subdir=True)
dman.save('dct2', dct, base=base)
dman.tui.walk_directory(dman.mount('dct2', base=base))
