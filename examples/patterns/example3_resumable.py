"""
Resumable
========================

How to implement a resumable experiment.
"""

# %%
# Overview
# -------------------------
#
# We show how you can use ``dman`` to create a resumable script. To do
# so we introduce the following components:
#
# * ``tui.stack`` used for resumable for loops (requires ``rich``).
# * ``dman.uninterrupted`` to allow for keyboard interrupt safe storing of files.


# %%
# Setting up
# ----------------------
#
# To setup the example you will need the following imports:

import dman
from dman import tui
from dman.numeric import barray

import numpy as np
import numpy.random as npr

import time
from typing import Tuple


# %%
# We will also be using the following ``modelclass`` to store our data.
# The field ``state`` will keep track of the current state of the script.


@dman.modelclass
class Experiment:
    data: barray = dman.recordfield(stem="data", default=None)
    state: Tuple[int] = None


# %%
# Running the experiment
# -------------------------
# We load the experiment if it exists, otherwise we create a default one.
shape = (30, 10)
exp: Experiment = dman.load("experiment", default_factory=Experiment)
if exp.data is None:
    exp.data = np.zeros(shape)

# %%
# We use a stack to iterate through the two nested for loops,
# populating the data array. You can alternatively use 
# ``sg(range(shape[1]), ...)``, replacing ``range`` with any other iterable. 
rg = npr.default_rng(1024)
with tui.stack(exp.state) as sg:
    it = sg.range(shape[0], log={'value': np.nan})
    for i in it:
        for j in sg.range(shape[1]):
            # generate new data point
            time.sleep(0.01)
            exp.data[i, j] = rg.normal()

            # update descriptors of tasks
            it.update(value=exp.data[i, j])

            # store the state and current result
            exp.state = sg.state
            with dman.uninterrupted():
                dman.save("experiment", exp)

# %%
# We used ``dman.uninterrupted`` to make sure that no keyboard interrupts
# occur while saving to disk. Instead they are captured and
# raised after ``dman.save`` is completed.
#
# You can try running the script and seeing what happens when you press
# ``CTRL+C`` and resume.
#
# No matter how many times you quit the script. Eventually the full 
# array should be computed:

exp: Experiment = dman.load("experiment")
with np.printoptions(linewidth=80, formatter={"float": lambda f: f"{f:+0.2f}"}):
    tui.pprint(exp.data)
