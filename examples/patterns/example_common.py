"""
Getting Started
========================

Basic use case of ``dman``.
"""


# %%
# Overview
# ---------------------------
#
# We provide an example here of how one could approach. This example will show you
#
# * How to integrate ``numpy`` arrays into the framework.
# * How to setup an experiment modelclass.
# * How to save and load from cache.

# %%
# Setting up
# ------------------------
#
# To setup the example we will need to following imports:

import dman
from dman import tui
import numpy as np
import os


# %%
# The first step is to describe how arrays are stored. We do so by
# creating a ``storable`` type.


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
# We specify three components. First ``__ext__`` specifies the suffix added
# to the created files. The ``__write__`` defines how to store the content
# at a specified path and similarly ``__read__`` defines how to read
# the content from a file.
#
# It will be inconvenient to always call ``data.view(barray)`` to convert
# data to the storable type. To make this more convenient we can
# create a wrapper around ``recordfield``:


def barrayfield(**kwargs):
    def to_sarray(arg):
        if isinstance(arg, np.ndarray):
            return arg.view(barray)
        return arg

    return dman.recordfield(**kwargs, pre=to_sarray)


# %%
# The callable provided through the ``pre`` argument is called whenever
# a field is set in a ``modelclass``.
#
# .. note::
#
#     Both ``barray`` and ``barrayfield`` are implemented in ``dman.numeric``.
#     We provide the details here since they are a good example on how
#     to implement a ``storable`` type.

# %%
# Next we want to define the experiment configuration. To do so
# we use a ``modelclass`` which acts similarly to a ``dataclass``,
# but it is automatically serializable.


@dman.modelclass(name="config")
class Config:
    seed: int = 1234
    size: int = 20
    nsample: int = 1000
    nrepeats: int = 2


# %%
# We will want to do multiple runs of some test in this example, so next
# lets specify the run type.


@dman.modelclass(name="run", storable=True)
class Run:
    """
    Run class
        Stores simulation data.
    """

    config: Config
    data: barray = barrayfield(default=None)
    output: barray = barrayfield(default=None)


# %%
# Simple enough. We specify that the ``modelclass``
# can be stored to a file using ``storable=True``. Doing so
# helps with performance, since loading from files is only done
# when needed.
#
# The run contains two fields: ``data`` and ``output``. Note
# that these are specified using a ``barrayfield`` (which wrapped ``recordfield``).
# This has all options from the ``field`` method. We use this method since
# the ``barray`` fields should be stored to a file. The ``recordfield`` makes this
# clear and enables specifying things like the filename (using ``stem='<name>'``),
# subdirectory (using ``subdir='<subdir>'``), etc.
# We leave these unspecified in this case and leave filename selection to
# the ``dman`` framework.

# %%
# We will store our data in an instance of ``mruns``, which acts like
# a list. File names are determined automatically based on the specified stem.
#
# For example we can specify to store items at ``results/sim-#``
# with ``#`` replaced by the number of the run.
#
# .. code-block:: python
#
#     content = mruns(stem='sim', subdir='results')
#
# .. warning::
#
#     To avoid unnecessary overhead caused by having to move files around,
#     the index used in the file name is not the index in the list. Instead
#     it is based on a counter that keeps track of the number of runs added.
#     This matches the index until items are deleted or inserted.


# %%
# Running the experiment
# ----------------------------------
# We implement a method to run the experiment given some configuration:


def execute(cfg: Config):
    """
    Run a simulation based on the provided configuration.
    """
    # load the experiments from disk
    with dman.track(
        "experiment",
        default_factory=dman.mruns_factory(stem="experiment", subdir="results"),
    ) as content:

        # for type hinting (this is good practice in ``dman`` since it also
        # makes sure you imported the type you want to load).
        content: dman.mruns = content

        # if the config was run before we don't need to run again
        if len(content) > 0 and any((run.config == cfg for run in content)):
            return

        # generate data
        rng = np.random.default_rng(cfg.seed)
        data = rng.random(size=(cfg.size, cfg.nsample))
        transform = rng.standard_normal(size=(100, data.shape[0]))
        output = transform @ data
        content.append(Run(cfg, data, output))


# %%
# We provide an overview of the above code segment:
#
# 1. The ``track`` command
#     It specifies a file key, based on which an object will be loaded.
#     If the file does not exist, it will be created based on ``default_factory``.
#     Similarly to ``load`` it specifies a file key and a default value that is used when the object can
#     not be loaded from the file key. Once the context exists, the file is saved automatically.
#
# 2. The ``mruns_factory`` method
#      Returns a method with no arguments that returns ``mruns(stem='experiment', subdir='results')`` when called.
#
# 3. Note that we specify the loaded type.
#     The interpreter can not know in advance what the loaded type will be, so we specify
#     it manually. This is good practice since it makes refactoring more convenient. It also avoids
#     issues caused by loading stored objects when the class definition is not imported.
#
# 4. We check if the config is new.
#     To avoid re-running experiments unnecessarily we go through the list of
#     experiments and check whether the config was already executed. Note that
#     no data arrays are loaded from disk when doing so because of the deferred
#     loading supported by default through the ``record`` system.
#
# .. warning::
#
#     Before running the script execute ``dman init`` in the root folder
#     of your project. Files will be stored in the ``.dman`` folder created there.


# %%
# We begin by clearing any existing runs
with dman.track(
    "experiment",
    default_factory=dman.mruns_factory(stem="experiment", subdir="results"),
) as content:
    content: dman.mruns = content
    content.clear()

# %%
# Alternatively if you wish to remove only the most recent run you can use:
#
# .. code-block:: python
#
#     with dman.track(
#         'experiment',
#         default_factory=mruns_factory(stem='experiment', subdir='results')
#     ) as content:
#         content: mruns = content
#         content.pop()
#
# The files are only removed once the ``track`` context exits.


# %%
# We next execute three experiments as follows:
execute(Config(seed=1000))
execute(Config(seed=1024))
execute(Config(seed=1000))

# %%
# Afterwards you will see that ``.dman`` is populated as follows:
tui.walk_directory(
    os.path.join(dman.get_directory("experiment"), ".."),
    show_content=True,
    normalize=True,
    show_hidden=True,
)

# %%
# Note that the ``experiment`` folder is ignored
# The root file is ``experiment.json`` (as specified by the key in ``track``).
# Its content is as follows

# show contents of "experiment.json"
with open(os.path.join(dman.get_directory("experiment"), "experiment.json"), "r") as f:
    tui.print_json(f.read())

# %%
# The results are not recorded here directly. Instead we have a
# ``_ser__record`` that specifies the location of the json files
# relative to the file ``experiment.json``.
#
# We can see the options passed to ``mruns_factory``.
# Moreover, all of the run keys are there, but their content
# defers to another file through a ``_ser__record`` field.
# Specifically ``'results/experiment-#/experiment.json'``.

# show contents of "experiment-0.json"
with open(
    os.path.join(
        dman.get_directory("experiment"), "results", "experiment-0", "experiment.json"
    ),
    "r",
) as f:
    tui.print_json(f.read())

# %%
#  You see that the ``experiment-#.json`` files contain
# info about the files containing the ``barray`` types. These file names
# are specified automatically using ``uuid4`` to guarantee uniqueness.

# %%
# The Configuration File
# ------------------------------
#
# Since the configuration is serializable we can also save and load it to disk.
#
# We can create a configuration file using the ``save``
# command.

_ = dman.save("config", Config(), cluster=False)

# %%
# We add the ``cluster=False`` since the Configuration only needs a single file. So no dedicated subfolder (i.e. cluster) should be created.
#
# You should see a ``config.json`` file appear in your ``.dman`` folder.
# You can re-run the code above, after tweaking some values. The experiment
# behavior changes.
#
# We can load it from disk using

cfg: Config = dman.load("config", cluster=False)
tui.print(cfg)

# %%
# It is important that ``cluster=False`` is added here as well. Note that internally
# the ``track`` command uses both ``load`` and ``save``.


# %%
# Specifying Storage Folder
# -------------------------------
#
# In the above experiment, the files were stored in
# a folder called ``cache/examples:common``. The folder name
# was created based on the script path relative to the folder in which
# ``.dman`` is contained. Specifically the script was located in ``examples/common.py``.
#
# The automatic folder name generation is implemented to avoid potential overlap
# between different scripts. Of course, this also means that using
# ``track('experiment')`` in two different scripts will save/load from different
# files. If you want to use files in different scripts you can do so by specifying
# a ``generator`` as follows

_ = dman.save("config", Config(), cluster=False, generator="demo")

# %%
# Doing this, will save/load files from the folder ``.dman/demo`` no matter
# what script the command is executed from. Other options are listed in :ref:`fundamentals`
#
# For reference, the final folder structure is as follows:
tui.walk_directory(
    dman.get_directory('config', cluster=False, generator='demo'),
    show_content=False,
    normalize=True,
    show_hidden=True,
)
