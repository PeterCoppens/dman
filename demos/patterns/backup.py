"""
Backup Pattern
----------------------------

We can easily backup runs whenever a new one is available with ``dman``.
This script shows a minimal example of how to do so.

"""


import dman
from dman.numeric import sarray, sarrayfield, barray, barrayfield

import numpy as np
from numpy import random as npr


@dman.modelclass(compact=True)
class Config:
    """
    Config class
        Acts as the signature of the ``Run``.    
    """
    nsample: sarray = sarrayfield(as_type=int, compare=True, default=None)
    nrepeat: int = 10
    seed: int = None


@dman.modelclass(storable=True)
class Run:
    """
    Run class
        Contains the data from some simulation based on a ``Config``.
    """
    cfg: Config
    data: barray = barrayfield(stem='data')


def experiment(cfg: Config):
    """
    Execute an experiment based on some config.
    """
    rg = npr.default_rng(cfg.seed)
    
    result = np.empty((len(cfg.nsample), cfg.nrepeat))
    for i, nsample in enumerate(cfg.nsample):
        data = rg.beta(a=1, b=12, size=(nsample, cfg.nrepeat))
        result[i] = np.mean(data, axis=0)
    
    return Run(cfg=cfg, data=result)


def main():
    # create a configuration for the next run
    cfg = Config(nsample=np.logspace(0, 3, 4))

    # try to load the current run
    run: Run = dman.load('current', default=None)

    # if there is no current run or it has a different config
    #   1. we move the current run to a backup folder
    #   2. we generate a new run and store it as the current one
    if run is not None and run.cfg != cfg:
        with dman.track('backup', default_factory=dman.mruns) as backup:
            dman.mruns.append(backup, run)
            print(backup)
        run = None
    
    if run is None:
        run = experiment(cfg)
        dman.save('current', run)
    
    print(run.data)


if __name__ == '__main__':
    main()
    