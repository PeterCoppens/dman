from dman import modelclass, track, load, storable, save
from dman import recordfield, smdict_factory, smdict, verbose

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


def sarrayfield(**kwargs):
    def to_sarray(arg):
        if isinstance(arg, np.ndarray):
            return arg.view(sarray)
        return arg                
    return recordfield(**kwargs, pre=to_sarray)


@modelclass(name='run', storable=True)
class Run:
    input: sarray = sarrayfield(default=None)
    output: sarray = sarrayfield(default=None)
    
    @classmethod
    def execute(cls, input: np.ndarray, rng: np.random.Generator):
        transform = rng.standard_normal(size=(100, input.shape[0]))
        output = transform @ input
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


@storable(name='__broken')
class Broken: ...


def main():
    verbose.setup(logfile='log.ansi')

    cfg: Configuration = load('config', default_factory=Configuration, cluster=False)
    with track('experiment', default_factory=Experiment, verbose=True) as content:
        experiments: Experiment = content
        experiments.results.clear()
        if len(experiments.results) > 0:
            print('results already available')
            return

        rng = np.random.default_rng(cfg.seed)
        for i in range(cfg.nrepeats):
            input = rng.random(
                size=(cfg.size, cfg.nsample)
            )
            run = Run.execute(input, rng)
            if i == 0:
                run.output = Broken()
            experiments.results[f'run-{len(experiments.results)}'] = run


def create_configuration():
    save('config', Configuration(), cluster=False)

if __name__ == '__main__':
    create_configuration()
    main()


    
