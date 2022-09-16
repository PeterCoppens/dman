"""
Registry pattern
-----------------------

This is a more extensive version of the backup pattern. It stores Runs 
based on their config, generating new runs when a new config is introduced.

This pattern is similar to the one in ``examples/common.py``.

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

    # load the registry
    with dman.track('registry', default_factory=dman.mruns) as registry:
        registry: dman.mruns = registry

        # find an existing run with matching config
        #   if you plan to generate many runs, you should consider making ``Config``
        #   hashable and using ``dman.mdict`` instead of ``dman.mruns``. 
        #   The disadvantage will be that file names are not as readable.
        run: Run = next((r for r in registry if isinstance(r, Run) and r.cfg == cfg), None)
        
        # if there is none, generate it and store it in the registry
        if run is None: 
            run = experiment(cfg)
            registry.append(run)
    
        print(run.data)


if __name__ == '__main__':
    main()
    