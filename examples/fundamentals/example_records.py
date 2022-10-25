"""
Using Records
========================

We show how to use ``records`` to serialize storables.
"""

# %%
# We will be using ``barray`` for this example so you should have ``numpy`` 
# installed.

from tempfile import TemporaryDirectory
import dman
from dman.numeric import barray
from dman import tui
import numpy as np

# turn of logging
dman.log.default_config(level=dman.log.CRITICAL)

# %% 
# By default a ``barray`` object is not serializable:
array = np.arange(3).view(barray)
ser = dman.serialize(array)
tui.print_json(dman.sjson.dumps(ser, indent=4))

# %%
# Note how ``dman`` does not throw an error here. This is to make sure that 
# as much data is serialized as possible. You can turn on validation
# by using a context. We illustrate such functionality in TODO add reference

# %%
# Contexts will also be useful for storing purposes.
# They specify the directory in which files should be stored during serialization.
# To make sure a ``storable`` can be serialized it should be wrapped in a 
# ``record``. This interface has a the following features:
#
#   * File names and extensions can be specified manually or created automatically.
#   * Sub folders can be specified.
#   * Reading the object from file can be delayed until the content is accessed. 
#
# The most basic usage is as follows:

dir = TemporaryDirectory()
base = dir.name
ctx = dman.context(base)
rec = dman.record(array)
ser = dman.serialize(rec, context=ctx)
tui.print_json(dman.sjson.dumps(ser, indent=4))

# %%
# You can see that the result of serialization now provides a pointer to 
# the file where the array is stored. We can see that the file exists:

tui.walk_directory(base)

# %%
# And we can load its content again

rec = dman.deserialize(ser, context=ctx)
tui.print(rec)

# %%
# Note how the record specifies that it contains a ``_num__barray``
# which is the name for the storable type. However it also specifies ``UL``
# implying that the file has not been loaded. We can load it by accessing 
# the ``content`` field:

array = rec.content
tui.print(array)
tui.print(rec)

# %%
# Now the record no longer specifies that the ``content`` is unloaded.
# Also observe that the file name is still the same as the one
# specified in the original record. This means that when serializing 
# again the old file will be overwritten instead of creating a new one. 
# We can also remove the file:

dman.remove(rec, context=ctx)
tui.walk_directory(base)
dir.cleanup()   # clean temporary directory

# %% 
# It is possible to be more precise when specifying a ``record``.
# To give an overview of the options available when creating 
# a record we provide its documentation:
#
#
# .. autofunction:: dman.record
#     :noindex:
#
#
# The way file names are specified is left flexible for internal use, 
# but is hence somewhat complex. We list examples below.
#
#   ================================================       =========================
#   options                                                 target
#   ================================================       =========================
#   ``stem='test'``                                         ``./test``
#   ``stem='test', suffix='.txt'``                          ``./test.txt``
#   ``name='test.txt'``                                     ``./test.txt``
#   ``name='test.txt', subdir='dir'``                       ``./dir/test.txt``
#   ``name='test.txt', stem='test', suffix='.txt'``         ``ValueError``
#   ================================================       =========================
#
#
# .. note::
#     It is also possible to automatically determine the ``suffix`` based 
#     on the class.
#
#
#     .. code-block:: python
#
#         @storable(name='manual')
#         class ManualFile:
#             __ext__ = '.obj'
#             ...
#
#
#     So if only a ``stem=test`` is specified the target will automatically become ``test.obj``. 
#     If a ``suffix`` is specified anyway, then the one specified through ``__ext__`` 
#     is overridden. 
#
#     When a ``storable`` is automatically created from a ``dataclass`` or a ``serializable``
#     the ``suffix`` will be set to ``.json`` by default. 
#
#
# .. warning::
#     Be careful specifying the ``stem`` of a file. It often makes sense
#     to omit it and leave the selection up to the ``record``. That way you
#     will not accidentally re-use existing files. TODO reference to guide?