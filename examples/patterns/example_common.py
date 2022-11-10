"""
Getting Started
========================

This example illustrates basic usage of ``dman``.
"""


# %%
# Overview
# ---------------------------
#
# The ``dman`` packages allows for convenient data storing and loading.
# The focus is on human readability, hence ``dman`` is mostly a file 
# hierarchy manager. It does allow storing some types to files by default,
# but for others you have to define yourself how files are read from and written 
# to disk. More details are provided in other example. For the full 
# overview of introducing new types into ``dman`` see 
# :ref:`sphx_glr_gallery_fundamentals_example1_storables.py` and
# :ref:`sphx_glr_gallery_fundamentals_example0_serializables.py`. In all
# likelihood however you will not need to do so too often. Especially
# if your data is represented in terms of ``numpy`` arrays. 
# We will be using those in this example. 
#
# This example starts with some basic ``python`` types and how to store them 
# to disk. We then show how ``dman`` extends on these types, allowing 
# for specifying file paths. Finally we show how ``modelclasses``,
# the ``dman`` extension of a ``dataclass`` can be used.
#
# To run this example you will require ``numpy`` and ``rich``.

# %%
# Basic types
# ----------------------------
#
# You can store most basic ``python`` types. Specifically those 
# that can be handled by ``json``. 

# clear any old data
import dman
import shutil, os
if os.path.isdir(dman.mount()):
    shutil.rmtree(dman.mount())

config = {'mode': 'automatic', 'size': 5}
data = [i**2 for i in range(config['size'])]

dman.save('result', {'config': config, 'data': data})

# %%
# If you receive an error about ``.dman`` not existing. This means you 
# have to create one by executing ``dman init`` in your terminal or creating 
# a ``.dman`` folder manually in your project root. 
# Files will, by default, be stored in this folder:

dman.tui.walk_directory(dman.mount(), show_content=True)

# %%
# By default ``dman`` can also handle ``numpy`` arrays.

import numpy as np
dman.save('result', {'config': config, 'data': np.arange(config['size'])**2})
dman.tui.walk_directory(dman.mount(), show_content=True)

# %%
# We mentioned that ``dman`` is a file hierarchy manager.
# Already some convenience is provided since we didn't need to specify a path
# for our data. This path has been determined automatically by :func:`dman.mount`
# internally based on the name of the script. Of course if you want 
# to read the file from a different script this can be inconvenient. 
# So you can specify the generator yourself. 

dman.save('result', 'content', generator='example_common')
dman.tui.walk_directory(dman.mount(generator='example_common'), show_content=True)

# %%
# The signature of :func:`dman.mount` is similar to that of :func:`dman.save`,
# :func:`dman.load` and :func:`dman.track`. Hence if you want to know 
# where your files go, you can always use it. 
#
# We can also load files of course:
print(dman.load('result', generator='example_common'))

# %%
# If the ``generator`` is not specified then loading only works 
# when executed in the same script as the one where ``save`` was called 
# with the default ``generator``. 

print(dman.load('result'))

# %%
# Finally we can do both at the same time

dman.save('updated', {'original': 0})
with dman.track('updated', default_factory=dict) as data:
    data['value'] = 42
dman.tui.walk_directory(dman.mount('updated'), show_content=True)

# %%
# Creating a File Hierarchy
# ----------------------------
#
# Beyond just automatically determining a ``mount`` point to save files 
# to, ``dman`` also allows creating a file hierarchy within this folder. 
#
# To do so we need to use model types. Let's start with the model version 
# of dictionaries and of lists. We will also use ``barray``,
# which is the first ``storable`` type. It can be written and read from disk.
# The second storable is ``smdict``, which is simply a dictionary 
# that will be stored to a separate file. 

from dman.numeric import barray
config = dman.smdict.from_dict(config)
data = (np.arange(config['size'])**2).view(barray)

files = dman.mdict(store_by_key=True)
files.update(config=config, data=data)

dman.save('files', files)
dman.tui.walk_directory(dman.mount('files'), show_content=True)

# %%
# Now three files have been created
#
# - ``files.json`` contains meta-data, describing the content of the other files.
# - ``config.json`` is what became of our ``config`` object.
# - ``data.npy`` stores the contents of ``data``.
#
# Let us consider a more interesting example, using :class:`dman.mruns`. This object 
# acts like a list, but creates file names for storables automatically. 
with dman.track('runs', default_factory=dman.mruns_factory(store_subdir=False)) as runs:
    runs: dman.mruns = runs     # for type hinting
    runs.clear()                # remove all previous runs
    for i in range(3):
        runs.append(np.random.uniform(size=i).view(barray))
    
dman.tui.walk_directory(dman.mount('runs'), show_content=True)

# %%
# If you don't care about file names, ``dman`` can generate them automatically:

with dman.track('auto', default_factory=list) as lst:
    lst.clear()
    lst.extend([np.random.uniform(size=i).view(barray) for i in range(3)])
dman.tui.walk_directory(dman.mount('auto'), show_content=True)

# %%
# .. warning::
#   
#       Both specifying file names and having them be automatically generated 
#       have advantages and disadvantages. When specifying the file names 
#       you risk overwriting existing data, however ``dman`` 
#       will give a warning by default. See :ref:`sphx_glr_gallery_fundamentals_example4_path.py`
#       for more info. Importantly if you want ``dman`` to prompt you for a new 
#       filename whenever it risks overwriting an existing file use:
#
#       .. code-block:: python
#
#           dman.params.store.on_retouch = 'prompt'
#
#       When not specifying file names, files will likely not be removed. 
#       Instead ``dman`` keeps creating new files (unless if you use ``track`` correctly
#       as illustrated above).

# %%
# Modelclasses
# ---------------------
#
# We finally briefly illustrate the usage of ``modelclass``. 
from dman.numeric import sarray

@dman.modelclass(compact=True, storable=True)
class Config:
    description: str
    size: int

@dman.modelclass(storable=True, store_by_field=True)
class Data:
    values: sarray[int]
    output: barray = None

cfg = Config('Experiment generating numbers', 25)
data = Data(np.logspace(0, 3, cfg.size))
data.output = np.random.uniform(size=cfg.size)

# %%
# The ``modelclass`` automatically converts the numpy arrays to the 
# specified types:
print(
    f'{type(data.values)=}', 
    f'{type(data.values[0])=}', 
    f'{type(data.output)=}',
    sep='\n'
)

# %%
# We can now save the result
dman.save(
    'model', 
    dman.mdict.from_dict({'cfg': cfg, 'data': data}, store_by_key=True)
)
dman.tui.walk_directory(dman.mount('model'), show_content=True)

# %%
# More information on how to use ``modelclass`` can be found in 
# :ref:`sphx_glr_gallery_fundamentals_example3_models.py`.