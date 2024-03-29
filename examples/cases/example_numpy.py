""" 
Numpy Experiments
==================================

We provide a common use case with ``numpy`` and ``dman``.
"""

# %%
# Overview
# -------------------------
#
# Consider the following simple code to compute least-squares estimates.
# We would like to run a batch experiment on this estimator to evaluate its
# performance for different sample sizes. While doing so we want to
# keep track of our data and how it was generated.

import numpy as np
import numpy.random as npr


def gather_data(
    nb_samples: int, *, std: float = 0.1, theta=None, rg: npr.Generator = None
):
    if rg is None:
        rg = npr.default_rng()
    if theta is None:
        theta = [0.5, 3]
    x = rg.uniform(0, 1, size=nb_samples)
    e = rg.standard_normal(size=nb_samples) * std
    y = theta[0] * x + theta[1] + e
    return (x, y)


def regressors(x: np.ndarray):
    return np.vstack([x, np.ones(len(x))]).T


x, y = gather_data(10)
th = np.linalg.lstsq(regressors(x), y, rcond=None)[0]


# %%
# Experiment configuration
# ---------------------------
#
# First we need to somehow represent an experiment configuration.

import dman
from typing import Sequence


@dman.modelclass(name="model", storable=True)
class Model:
    """Linear model.
    Support storing in a file (storable=True)
    """

    theta: Sequence[float] = (0.5, 3)
    std: float = 0.1


# %%
# If we take a look at the serialization of ``Model`` we see that
# the result could be significantly more compact.

from dman import tui

tui.print_serializable(Model())

# %%
# The current serialization has been automatically generated by ``dman``.
# Instead a custom serialization procedure can be specified.

import re


@dman.modelclass(name="model", storable=True)
class Model:
    """Linear model.
    Support storing in a file (storable=True)
    """

    theta: Sequence[float] = (0.5, 3)
    std: float = 0.1

    def __serialize__(self):
        return f"Model(theta={str(list(self.theta))}, std={self.std})"

    @classmethod
    def __deserialize__(cls, ser):
        pattern = r"Model\(theta=\[(?P<theta>[0-9., ]+)\], std=(?P<std>[0-9.]*)\)"
        m = re.search(pattern, ser).groupdict()
        theta, std = m["theta"], m["std"]
        return cls([float(i) for i in theta.split(",")], float(std))


# %%
# We can then create a gallery of models as follows:
gallery = dman.mdict(store_by_key=True, store_subdir=False)
gallery.update(
    {
        "default": Model(theta=(0.5, 3), std=0.1),
        "flat": Model(theta=(0, 1.0), std=0.1),
        "steep": Model(theta=(10.0, 0.0), std=0.1),
        "noisy": Model(theta=(0.5, 3), std=5.0),
    }
)

dman.save("__gallery", gallery, generator="gallery", cluster=False)
tui.walk_directory(
    dman.mount(key="", generator="gallery", cluster=False), show_content=True
)

# %%
# Models can then be loaded from the gallery as follows
def model(key: str):
    return dman.load("__gallery", generator="gallery", cluster=False)[key]


print(model("default"))


# %% We can now define a more extensive experiment configuration.
# Note that ``modelclass`` acts like a ``dataclass``, but supports some additional
# field types. Some examples are given below.

# We specify that the field should be serialized (not stored)
# an alternative would be ``dman.field`` or ``dman.recordfield``
# in which case the model would be stored in a separate file
# from the configuration.
_model_field = dman.serializefield(default_factory=Model)

# %%
# Comparable arrays (``carray``)
# provide some additional functionality when used in a ``modelclass``
# especially useful in configuration classes. We specifically state that the
# array is of type integer and should  be comparable.
# When assigning an array to the class, it will be converted automatically.

from dman.numeric import carray
@dman.modelclass(name="config", storable=True, compact=True)
class Configuration:
    """Experiment Configuration."""

    model: Model = _model_field
    nb_samples: carray[int] = dman.field(default_factory=lambda: np.logspace(1, 3, 20))
    nb_repeats: int = 1000
    seed: int = None


# %%
# Note how we simply pass some logspace to ``nb_samples`` as default factory.
# The input there will be converted to (numpy) integers automatically.
# All types in ``dman.numeric`` -- that is ``sarray``, ``carray`` and ``barray``
# can be typed similarly to how we do for ``carray`` here.
print("type of nb_samples:", type(Configuration().nb_samples[0]))

# %%
# We can also compare configurations (since we specified ``carray``)
print(
    "check for configs:",
    Configuration() == Configuration(nb_samples=np.logspace(1, 3, 20)),
    Configuration() == Configuration(nb_samples=np.logspace(2, 3, 20)),
)


# %%
# Executing experiments
# -------------------------------
# We can now define the experiment behavior. We can do so as follows:

from dataclasses import asdict


def execute(model: Model, nb_samples: int, *, rg: npr.Generator = None):
    x, y = gather_data(nb_samples, **asdict(model), rg=rg)
    th, res, _, _ = np.linalg.lstsq(regressors(x), y, rcond=None)
    return np.linalg.norm(th - model.theta, ord=2), res


# Specify the location of the data using a recordfield.
# The data will be stored in:
#   ./data/<key>.<suffix>
# for each (storable) key.
_data_field = dman.recordfield(
    default_factory=lambda: (dman.smdict(store_subdir=False, store_by_key=True)),
    subdir="data",
    stem="__data",
    repr=False,
)


from dman.numeric import barray


@dman.modelclass(storable=True, compact=True)
class Experiment:
    """Experiment result."""

    model: Model = dman.serializefield()
    nb_samples: int
    nb_repeats: int
    data: dman.smdict = _data_field

    @classmethod
    def generate(cls, cfg: Configuration, idx: int, *, verbose: bool = True):
        rg = npr.default_rng(cfg.seed)
        res = cls(
            model=cfg.model, nb_samples=cfg.nb_samples[idx], nb_repeats=cfg.nb_repeats
        )
        res.data.update(
            {
                "error": np.zeros((cfg.nb_repeats,)).view(barray),
                "residual": np.zeros((cfg.nb_repeats)).view(barray),
            }
        )

        _iter = range(cfg.nb_repeats)
        if verbose:
            _iter = tui.track(
                _iter, total=cfg.nb_repeats, description="Executing experiment ..."
            )
        for i in _iter:
            res.data["error"][i], res.data["residual"][i] = execute(
                cfg.model, cfg.nb_samples[idx], rg=rg
            )
        return res

# %%
# We can run one experiment:
exp = Experiment.generate(Configuration(nb_repeats=5), idx=0)
dman.save("demo-modelclass", exp)
tui.walk_directory(dman.mount("demo-modelclass"), show_content=True)

# %%
# The creation of the data dictionary is somewhat verbose. Instead
# we can again create a data modelclass


@dman.modelclass(store_by_field=True, storable=True, compact=True)
class DataItem:
    error: barray
    residual: barray    


@dman.modelclass(storable=True, compact=True)
class Experiment:
    """Experiment result."""

    model: Model = dman.serializefield()  # Store the model in experiment json.
    nb_samples: int
    nb_repeats: int
    data: DataItem = dman.recordfield(stem='__data', subdir='data', default=None)

    @classmethod
    def generate(cls, cfg: Configuration, idx: int, *, verbose: bool = True):
        rg = npr.default_rng(cfg.seed)
        res = cls(
            model=cfg.model, nb_samples=cfg.nb_samples[idx], nb_repeats=cfg.nb_repeats
        )
        res.data = DataItem(np.zeros((cfg.nb_repeats,)), np.zeros((cfg.nb_repeats)))
        _iter = range(cfg.nb_repeats)
        if verbose:
            _iter = tui.track(
                _iter, total=cfg.nb_repeats, description="Executing experiment ..."
            )
        for i in _iter:
            res.data.error[i], res.data.residual[i] = execute(
                cfg.model, cfg.nb_samples[idx], rg=rg
            )
        return res


# %%
# No need to convert to ``barray``. We can again store the experiment:
exp = Experiment.generate(Configuration(nb_repeats=5), idx=0)
dman.save("demo", exp)
tui.walk_directory(dman.mount("demo"), show_content=True)

# %%
# To store multiple experiments we can use a ``mruns`` object.

runs = dman.smruns(stem="experiment", subdir="experiments")
cfg = Configuration(model=model("flat"), nb_samples=[10, 100, 1000])
for i in tui.track(range(len(cfg.nb_samples)), total=len(cfg.nb_samples)):
    runs.append(Experiment.generate(cfg, idx=i, verbose=False))

dman.save(
    "experiment", dman.mdict.from_dict({"cfg": cfg, "experiments": runs}, store_by_key=True)
)
tui.walk_directory(dman.mount("experiment"), show_content=True)

# %%
# .. warning::
#
#       It is always important to keep in mind how you defined your file hierarchy,
#       especially when dealing with modelclasses. For example an instance of
#       ``Experiment`` will always write the errors to ./data/error.npy. If
#       you try to serialize two instances to the same folder therefore, the data
#       will be overridden.
