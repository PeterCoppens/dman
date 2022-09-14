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
# * ``tui.TaskStack`` used for resumable nested for loops (requires ``rich``).
# * ``dman.uninterrupted`` to allow for keyboard interrupt safe storing of files.

# %%
# Setting up
# ----------------------
#
# To setup the example you will need the following imports:

import dman
from dman import tui
from dman.numeric import barray, barrayfield

import numpy as np
import numpy.random as npr

import time
from typing import Tuple


# %%
# We will also be using the following ``modelclass`` to store our data.
# The field ``state`` will keep track of the current state of the script.


@dman.modelclass
class Experiment:
    data: barray = barrayfield(stem="data", default=None)
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
# We create the task stack (i.e. a nested for loop).
# The code below implements the following for loops:
#
# .. code-block:: python
#
#   for i in range(shape[0]):
#       for j in range(shape[1]):
#           ...
#
# Important to note is that the loops are registered starting with the
# innermost loop and working outward. We also pass the current
# experiment state to the stack. This makes sure that the for loops
# resume from when they were interrupted.

stack = tui.TaskStack(exp.state)
task_j = stack.register("column {j} of {m}", shape[1], {"j": 0, "m": shape[1]})
task_i = stack.register("row    {i} of {n}", shape[0], {"i": 0, "n": shape[0]})


# %%
# We can then iterate through the task stack, populating the data array.
rg = npr.default_rng(1024)
for i, j in stack:
    # update descriptors of tasks
    stack.update(task_i, i=i + 1)
    stack.update(task_j, j=j + 1)

    # generate new data point
    time.sleep(0.01)
    exp.data[i, j] = rg.normal()

    # store the state and current result
    exp.state = stack.state
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
