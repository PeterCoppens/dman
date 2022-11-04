import numpy as np
import dman


lst = []
for i in range(10):
    lst.append(np.random.rand(3))

states = np.array(lst)
d = 0.2


@dman.modelclass(storable=True)
class Experiment:
    d: float
    states: np.ndarray


exp = Experiment(d=d, states=states)
dct = dman.load('experiments', default_factory=dman.mdict_factory(store_by_key=True))  # if not found return dict()
dct[str(d)] = exp
dman.save('experiments', dct)
