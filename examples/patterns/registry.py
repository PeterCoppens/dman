import dman
from dman.numeric import sarray, sarrayfield, barray, barrayfield

import numpy as np
from numpy import random as npr


@dman.modelclass(compact=True)
class Config:
    nsample: sarray = sarrayfield(as_type=int, compare=True, default=None)
    nrepeat: int = 10
    seed: int = None


@dman.modelclass(storable=True)
class Run:
    cfg: Config
    data: barray = barrayfield(stem='data')


def experiment(cfg: Config):
    rg = npr.default_rng(cfg.seed)
    
    result = np.empty((len(cfg.nsample), cfg.nrepeat))
    for i, nsample in enumerate(cfg.nsample):
        data = rg.beta(a=1, b=12, size=(nsample, cfg.nrepeat))
        result[i] = np.mean(data, axis=0)
    
    return Run(cfg=cfg, data=result)


def main():
    cfg = Config(nsample=np.logspace(0, 3, 4))
    with dman.track('registry', default_factory=dman.mruns) as registry:
        registry: dman.mruns = registry
        run: Run = next((r for r in registry if isinstance(r, Run) and r.cfg == cfg), None)
        if run is None: 
            run = experiment(cfg)
            registry.append(run)
    
    print(run.data)


if __name__ == '__main__':
    main()
    