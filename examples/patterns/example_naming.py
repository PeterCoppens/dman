"""
Custom file naming
========================

How to specify file names during saving.
"""

# %%
# Overview
# -----------------------
#
# The main goal of ``dman`` is to output human readable files.
# One part of that is transparent file names. By default
# many files will be named using ``uuid4`` to guarantee uniqueness.
# This can sometimes hamper readability.
#
# Therefore we provide ways of specifying filenames in this document.
# The main file naming interface is through ``records``, which
# are introduced in :ref:`sphx_glr_gallery_fundamentals_records.py`.
# We briefly summarize the interface here and then
# illustrate how the provided models interface with records
# to specify file names.

# %%
# Demonstration
# ------------------------------------
#
# We build a demonstration here which contains the major ways of specifying file
# names that you might use within a project. You can use this as
# an initial reference or a demo to play around with. In what follows we discuss
# each component in detail.

import dman
from dman.numeric import barray, barrayfield
import numpy as np
from dman import tui
import shutil, os

# clear current files
if os.path.exists(dman.get_directory("container")):
    shutil.rmtree(dman.get_directory("container"))

# define container model class
@dman.modelclass
class Container:
    # store in ./root/data0.npy
    data0: barray = dman.recordfield(stem="data0", subdir="root")

    # store in ./data1.npy (and automatically convert to `barray`)
    data1: barray = barrayfield(stem="data1")

    # store `smlist` in ./containers/lst.json
    # store contents in ./containers/lst/...
    lst: dman.smlist = dman.recordfield(
        default_factory=dman.smlist_factory(subdir="lst"),
        stem="lst",
        subdir="containers",
    )

    # store `smruns` in ./containers/runs.json
    # store contents in ./containers/runs/...
    runs: dman.smruns = dman.recordfield(
        default_factory=dman.smruns_factory(subdir="runs", stem="experiment"),
        stem="runs",
        subdir="containers",
    )

    # store `smdict` in ./containers/dct.json
    # store contents in ./containers/dct/...
    # By default the value is stored in ./containers/dct/<key>/<key>.npy
    dct: dman.smdict = dman.recordfield(
        default_factory=dman.smdict_factory(
            subdir="dct", store_by_key=True, store_subdir=True
        ),
        stem="dct",
        subdir="containers",
    )


container = Container(data0=np.ones((3,)).view(barray), data1=np.ones((2,)))

# smlist .......................................................................
# by default `smlist` generates file names automatically
container.lst.append(np.ones(3).view(barray))

# we can specify the names using `record` which acts as ``append`` when
# no index is specified and as `insert` otherwise
container.lst.record(np.ones(3).view(barray), stem="data2", subdir="nested")
container.lst.record(np.ones(3).view(barray), 0, stem="data3", subdir="nested")

# mruns ........................................................................
# by default `smruns` generates the file names based on the provided stem
# (in this case `experiment`).
container.runs.append(np.ones(3).view(barray))

# we can still specify the names manually
container.runs.record(np.ones(3).view(barray), stem="data4", subdir="nested")

# smdict .......................................................................
# by default <dct>/key/key.npy
container.dct["data5"] = np.ones(3).view(barray)

# we can specify a custom file name and subdir. The result is still stored in
# a dedicated directory based on the key.
container.dct.record("custom", np.ones(3).view(barray), stem="data6", subdir="nested")

# result .......................................................................
dman.save("container", container)
tui.walk_directory(dman.get_directory("container"))

# %%
# Records
# -----------------------
#
# It is simple to create records:

data = np.eye(3).view(barray)
rec = dman.record(data, stem="data", suffix=".npy", subdir="test")
print("target:", rec.target)

# %%
# A record will store your data and specify the target file to ``dman``.
# This path is relative to the current directory ``dman`` is operating in.
#
# .. autofunction:: dman.record
#     :noindex:
#
# The way you can specify file names is summarized below:
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
# For example:

# clear current files
if os.path.exists(dman.get_directory("record")):
    shutil.rmtree(dman.get_directory("record"))

# save the record
dman.save("record", rec)
tui.walk_directory(dman.get_directory("record"), show_content=True)


# %%
# So ``dman.save`` sets the path to ``.dman/cache/examples:patterns:naming/record``
# and the target is defined relative to that. The same will happen
# with models moving to subdirectories

# %%
# Model Containers
# -------------------
#
# Model List
# ^^^^^^^^^^^^^^
#
# In ``dman`` some standard containers have been turned into models, which
# can store records internally without the user noticing.
# For example

lst = dman.mlist([data])
print(lst.store[0])
print(lst[0])

# %%
# will store a record internally. Note however that the ``target``
# was set to some default value. The target can be manipulated in several ways.
#
# The most configurable way is to use the ``record`` method
lst.record(data, stem="data2", subdir="container")  # used as append
print("data1:", lst.store[1])
lst.record(data, 0, stem="data0", subdir="container")  # used as insert
print("data0:", lst.store[0])

# %%
# If we now save the whole thing:

# clear current files
if os.path.exists(dman.get_directory("mlist")):
    shutil.rmtree(dman.get_directory("mlist"))

dman.save("mlist", lst)
tui.walk_directory(dman.get_directory("mlist"), show_content=True)

#%%
# Interesting to note is that all the targets specified by the records
# internally are also stored in the ``.json`` file of the ``mlist``
# together with its configuration.

# %%
# .. autofunction:: dman.mlist.record
#     :noindex:

# %%
# We can also globally set a ``subdir`` for all targets
lst = dman.mlist([data], subdir="store")
print(lst.store[0].target)

# %%
# A storable model list (``smlist```) is storable itself and should also
# be wrapped in a record. As mentioned above, all further file specifications
# are taken relative to the target folder of the ``record``.

lst = dman.smlist([data], subdir="store")
rec = dman.record(lst, stem="lst", subdir="lst")

if os.path.exists(dman.get_directory("smlist")):
    shutil.rmtree(dman.get_directory("smlist"))

dman.save("smlist", rec)
tui.walk_directory(dman.get_directory("smlist"), show_content=True)

# %%
# This makes sure that nesting containers corresponds with nesting
# their directories. Note that every other basic model container specified
# below has a storable equivalent (i.e. ``smruns`` and ``smdict``).
# These work similarly to ``smlist`` and will therefore not be discussed further.


# %%
# Model Runs
# ^^^^^^^^^^^^^^^^
#
# Runs act very similarly to lists, but they have one additional feature

runs = dman.mruns([data], stem="experiment", subdir="store")
print(runs.store[0].target)

# %%
# You can globally specify a ``stem`` to generate readable file names
# automatically. Note that the ``record`` method is also still
# available for more fine-grained control.

# clear current files
if os.path.exists(dman.get_directory("mruns")):
    shutil.rmtree(dman.get_directory("mruns"))

runs.record(data, stem="data0", subdir="nested")
runs.record(data, stem="data1", subdir=os.path.join("..", "run-2"))
dman.save("mruns", runs)
tui.walk_directory(dman.get_directory("mruns"), show_content=True)
