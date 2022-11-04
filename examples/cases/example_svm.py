"""
SKLearn and SVM
============================

We apply ``dman`` to an example on SVM in the SK Learn package.
"""

# %%
# You can find the ``sklearn`` example this one is based on `here <https://scikit-learn.org/stable/auto_examples/svm/plot_svm_nonlinear.html>`_.
# It considers a non-linear binary classification problem, which is solved using SVC with an RBF kernel.
# We will not go into details on the classification problem, but instead
# show how one can use ``dman`` to store the generated data.
# 
# We show the basic example code with some data-structures added already,
# which we will use later for storage.

import numpy as np
import matplotlib.pyplot as plt
from sklearn import svm
import dman


@dman.modelclass(storable=True)
class Config:
    nb_samples: int = 300
    resolution: int = 500
    seed: int = 0


@dman.modelclass(storable=True)
class Samples:
    X: dman.barray = dman.recordfield(stem='x-samples', subdir='samples')
    Y: dman.barray = dman.recordfield(stem='y-samples', subdir='samples')
    

def generate_samples(cfg: Config):
    np.random.seed(cfg.seed)
    X = np.random.randn(cfg.nb_samples, 2)
    Y = np.logical_xor(X[:, 0] > 0, X[:, 1] > 0)
    return Samples(X, Y)


def build_figure(clf: svm.NuSVC, samples: Samples):
    fig, ax = plt.subplots(1, 1)

    # evaluate the fit
    xx, yy = np.meshgrid(np.linspace(-3, 3, 500), np.linspace(-3, 3, 500))
    Z = clf.decision_function(np.c_[xx.ravel(), yy.ravel()])
    Z = Z.reshape(xx.shape)

    # show the result
    ax.imshow(
        Z,
        interpolation="nearest",
        extent=(xx.min(), xx.max(), yy.min(), yy.max()),
        aspect="auto",
        origin="lower",
        cmap=plt.cm.PuOr_r,
    )
    ax.contour(xx, yy, Z, levels=[0], linewidths=2, linestyles="dashed")
    ax.scatter(samples.X[:, 0], samples.X[:, 1], s=30, c=samples.Y, cmap=plt.cm.Paired, edgecolors="k")
    ax.set_xticks(())
    ax.set_yticks(())
    ax.axis([-3, 3, -3, 3])
    return fig


# %%
# We can then run the experiment and plot the result as follows

cfg = Config()
samples = generate_samples(cfg)
clf = svm.NuSVC(gamma="auto")
clf.fit(samples.X, samples.Y)
build_figure(clf, samples)
plt.show()

# %%
# To make the ``NuSVC`` instance serializable we use a template. Luckily the
# ``NuSVC``` class is entirely defined by its ``__dict__``. 

@dman.modelclass(storable=True)
class T_NuSVC:
    store: dman.mdict

    @classmethod
    def __convert__(cls, other: svm.NuSVC):
        store = dman.mdict(store_by_key=True, subdir='svm-data')
        for k, v in other.__dict__.items():
            if isinstance(v, np.ndarray):
                v = v.view(dman.numeric.barray)  # store as binary files
            store[k] = v
        return cls(store=store)
    
    def __de_convert__(self):
        res = svm.NuSVC()
        res.__dict__ = {k: v for k, v in self.store.items()}
        return res

dman.serializable(svm.NuSVC, template=T_NuSVC)
dman.storable(svm.NuSVC)

# %%
# We create a data-type gathering everything together

@dman.modelclass
class Result:
    cfg: Config = dman.recordfield(stem='config')
    samples: Samples = dman.recordfield(stem='samples', subdir='data')
    clf: svm.NuSVC = dman.recordfield(stem='svm', subdir='data')


# %%
# And can then save the data as follows:
res = Result(cfg, samples, clf)
_ = dman.save('result', res)


# %%
# The resulting file structure looks like:
dman.tui.walk_directory(dman.mount('result'), show_content=True)

# %%
# We can load the experiment and show the result once more
res = dman.load('result')
build_figure(res.clf, res.samples)
plt.show()

