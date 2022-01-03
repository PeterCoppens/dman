from dman import modelclass, track, storable
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
    input: sarray
    output: sarray = recordfield(default=None)

    def execute(self, rng: np.random.Generator):
        transform = rng.standard_normal(size=(100, self.input.shape[0]))
        self.output = transform @ self.input
        self.output = self.output.view(sarray)


@modelclass(name='experiment')
class Experiment:
    mode: str = 'random'
    seed: int = 124
    size: int = 20
    nsample: int = 1000
    nrepeats: int = 2

    results: smdict = recordfield(
        default_factory=smdict_factory(subdir='results', store_by_key=True), 
        stem='results'
    )


def main():
    with track('experiment', default_factory=Experiment) as content:
        experiments: Experiment = content
        if len(experiments.results) > 0:
            print('results already available')
            return

        rng = np.random.default_rng(12345)
        for _ in range(experiments.nrepeats):
            input = rng.random(
                size=(experiments.size, experiments.nsample)
            )
            run = Run(input.view(sarray))
            run.execute(rng)
            experiments.results[f'run-{len(experiments.results)}'] = run


if __name__ == '__main__':
    main()


    
