"""
Repository
========================

Shows how to store data based on configs.
"""

import dman
from dman.numeric import carray, barray
from dman.plotting import PdfFigure

import numpy as np
import matplotlib.pyplot as plt
import warnings


@dman.modelclass(compact=True, storable=True)
class Config:
    degrees: carray[int]

    def key(self):
        return f"fit({','.join([str(d) for d in self.degrees])})"


@dman.modelclass(storable=True, store_by_field=True)
class Experiment:
    x: barray = dman.recordfield(subdir='samples')
    y: barray = dman.recordfield(subdir='samples')
    z: dman.mruns
    fig: PdfFigure = None


def experiment(cfg: Config):
    """Generate experiment data.
    Based on: https://numpy.org/doc/stable/reference/generated/numpy.polyfit.html.
    """
    xp = np.linspace(-2, 6, 100)
    x = np.array([0.0, 1.0, 2.0, 3.0, 4.0, 5.0])
    y = np.array([0.0, 0.8, 0.9, 0.1, -0.8, -1.0])
    z = dman.mruns(stem="poly", store_subdir=False, subdir='fit')

    fig, ax = plt.subplots(1, 1)
    ax.plot(x, y, ".", color="gray", label="samples")
    for d in dman.tui.progress(cfg.degrees, description="order"):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", np.RankWarning)
            zz = np.polyfit(x, y, d)
        z.append(zz.view(barray))
        p = np.poly1d(zz)
        ax.plot(xp, p(xp), "-", label=f"fit deg={d}")
    ax.legend()
    return Experiment(x, y, z, PdfFigure(fig))


def evaluate(cfg: Config):
    """Evaluate the provided configuration.
    If the experiment was executed before we return its result
    otherwise a new experiment is executed."""
    with dman.track("poly", default_factory=dman.mdict_factory(store_subdir=True, store_by_key=True)) as reg:
        reg: dman.mdict = reg  # for type hinting
        value = reg.get(cfg.key(), None)
        if value is None:
            value = experiment(cfg)
            reg[cfg.key()] = value
        return value

# Clear the old runs if they exist (for testing)
dman.clean('poly')

# Execute several configurations
res1 = evaluate(Config([1, 5, 7]))
res2 = evaluate(Config([8, 3]))

# %%
# We can examine the results and see that they are correct.
dman.tui.pprint(res1)
dman.tui.pprint(res2)

# %%
# We can re-execute an old configuration
res3 = evaluate(Config([1, 5, 7]))
dman.tui.pprint(res3)  # data is unloaded since it was loaded from disk

# %%
# The file structure is then as follows. Note that a pdf has been created
# for each experiment containing the produced figures. Feel free to take a look.
dman.tui.walk_directory(dman.mount("poly"))
