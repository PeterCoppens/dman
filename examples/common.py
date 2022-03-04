from dman import modelclass, track, load
from dman import mruns_factory, mruns
from dman.numeric import barray, barrayfield

import numpy as np


@modelclass(name='config')
class Configuration:
    seed: int = 1234
    size: int = 20
    nsample: int = 1000
    nrepeats: int = 2


@modelclass(name='run', storable=True)
class Run:
    config: Configuration
    data: barray = barrayfield(default=None)
    output: barray = barrayfield(default=None)


def execute(cfg: Configuration):
    with track('experiment' , default_factory=mruns_factory(subdir='results')) as content:
        content: mruns = content
        if len(content) > 0 and any((run.config == cfg for run in content)):
            return

        rng = np.random.default_rng(cfg.seed)
        data = rng.random(size=(cfg.size, cfg.nsample))
        transform = rng.standard_normal(size=(100, data.shape[0]))
        output = transform @ data
        content.append(Run(cfg, data, output))            


def main():    
    with track('experiment' , default_factory=mruns_factory(stem='experiment', subdir='results')) as content:
        content: mruns = content
        content.clear()
    
    execute(Configuration(seed=1000))
    execute(Configuration(seed=1024))
    execute(Configuration(seed=1000))

    content: mruns = load('experiment')
    for run in content:
        print(run)


if __name__ == '__main__':
    main()


    
