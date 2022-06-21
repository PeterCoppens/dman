"""
Common Use Example
-------------------------

This script contains a common use case of the ``dman`` library. 
We setup some config classes and simulation data classes to define the 
file structure on disk. We then show how files can be saved and loaded.

This script is accompanied by a 
    [detailed explanation](https://petercoppens.github.io/dman/docs/usage/common.html)

You can find more advanced storage patterns in ``examples/patterns``.
We closely mimic the ``registry`` pattern described in ``examples/patterns/registry.py``.
"""


from dman import modelclass, track, load
from dman import mruns_factory, mruns
from dman.numeric import barray, barrayfield

import numpy as np


@modelclass(name='config')
class Configuration:
    """
    Configuration file
    """
    seed: int = 1234
    size: int = 20
    nsample: int = 1000
    nrepeats: int = 2


@modelclass(name='run', storable=True)
class Run:
    """
    Run class
        Stores simulation data.
    """
    config: Configuration
    data: barray = barrayfield(default=None)
    output: barray = barrayfield(default=None)


def execute(cfg: Configuration):
    """
    Run a simulation based on the provided configuration.
    """

    # load the experiments from disk
    with track('experiment' , default_factory=mruns_factory(subdir='results')) as content:
        content: mruns = content

        # if the config was run before we don't need to run again
        if len(content) > 0 and any((run.config == cfg for run in content)):
            return

        # generate data
        rng = np.random.default_rng(cfg.seed)
        data = rng.random(size=(cfg.size, cfg.nsample))
        transform = rng.standard_normal(size=(100, data.shape[0]))
        output = transform @ data
        content.append(Run(cfg, data, output))            


def main():
    # clear any old experiments
    with track('experiment' , default_factory=mruns_factory(stem='experiment', subdir='results')) as content:
        content: mruns = content
        content.clear()
    
    # execute some configurations
    execute(Configuration(seed=1000))
    execute(Configuration(seed=1024))
    execute(Configuration(seed=1000))

    # print the results
    content: mruns = load('experiment')
    for run in content:
        print(run)


if __name__ == '__main__':
    main()


    
