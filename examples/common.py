from dman import modelclass, track, load, storable, save
from dman import recordfield, smdict_factory, smdict

import numpy as np


@storable(name='sarray')
class sarray(np.ndarray):
    __ext__ = '.npy'

    def __write__(self, path):
        with open(path, 'wb') as f:
            np.save(f, self)

    @classmethod
    def __read__(cls, path):
        with open(path, 'rb') as f:
            res: np.ndarray = np.load(f)
            return res.view(cls)


@modelclass(name='run', storable=True)
class Run:
    input: sarray = recordfield(default=None)
    output: sarray = recordfield(default=None)
    
    @classmethod
    def execute(cls, input: np.ndarray, rng: np.random.Generator):
        input = input.view(sarray)
        transform = rng.standard_normal(size=(100, input.shape[0]))
        output = transform @ input
        output = output.view(sarray)
        return cls(input, output)


@modelclass(name='config')
class Configuration:
    seed: int = 1234
    size: int = 20
    nsample: int = 1000
    nrepeats: int = 2


@modelclass(name='experiment')
class Experiment:
    results: smdict = recordfield(
        default_factory=smdict_factory(subdir='results', store_by_key=True),
        stem='results'
    )


def main():
    cfg: Configuration = load('config', default_factory=Configuration, cluster=False)
    with track('experiment', default_factory=Experiment) as content:
        experiments: Experiment = content
        if len(experiments.results) > 0:
            print('results already available')
            return

        rng = np.random.default_rng(cfg.seed)
        for _ in range(cfg.nrepeats):
            input = rng.random(
                size=(cfg.size, cfg.nsample)
            )
            run = Run.execute(input.view(sarray), rng)
            experiments.results[f'run-{len(experiments.results)}'] = run


def create_configuration():
    save('config', Configuration(), cluster=False)

if __name__ == '__main__':
    create_configuration()
    main()


    
