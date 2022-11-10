"""
Using Records
========================

We show how to use ``records`` to serialize storables.
"""

# %%
# Basic usage
# -------------------------

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
# by setting ``dman.params.serialize.validate=True``. Further details are provided 
# in :ref:`sphx_glr_gallery_fundamentals_example5_errors.py`

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

tdir = TemporaryDirectory()
base = tdir.name
ctx = dman.Context.from_directory(base)
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
tdir.cleanup()   # clean temporary directory

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
# More details are provided in :ref:`sphx_glr_gallery_fundamentals_example4_path.py`,
# where `targets` are introduced.
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
#     will not accidentally re-use existing files. When a file is re-used,
#     ``dman`` can automatically handle this when configured to do so
#     or, by default, it gives a warning.
#     See :ref:`sphx_glr_gallery_fundamentals_example4_path.py` for details.


# %% 
# Contexts
# -----------------------
# Sometimes storable objects can create more than one file. The types
# provided by ``dman`` that do so are referred to as ``models``.
# See :ref:`sphx_glr_gallery_fundamentals_example3_models.py` for examples.
# 
# The files created by these models should also be stored somewhere. 
# Their path is determined relative to the root storable. This process is 
# handled by the context. As we will illustrate below:

@dman.storable
class Feedback:
    def __write__(self, path: str, context):
        print(context)
    @classmethod
    def __read__(cls, path: str):
        return cls()

_ = dman.serialize(dman.record(Feedback(), subdir='folder'), context=ctx)

# %%
# As you can see the context received in the ``__write__`` method 
# now keeps track of the subfolder. Hence any further serializations happen
# relative to it. 
#
# We can keep going:

@dman.storable
class SubSerialize:
    def __write__(self, path: str, context):
        dman.serialize(dman.record(Feedback(), subdir='folder2'), context=context)
    @classmethod
    def __read__(cls, path: str):
        return cls()

_ = dman.serialize(dman.record(SubSerialize(), subdir='folder'), context=ctx)


# %%
# This is used inside of model types to determine the file paths. 
# We will not go into much more detail here and instead refer 
# to :ref:`sphx_glr_gallery_fundamentals_example3_models.py`.
#
# Whenever you create additional files you should also add a ``__remove__``
# method. See the end of :ref:`sphx_glr_gallery_fundamentals_example1_storables.py`
# for more details on this topic.