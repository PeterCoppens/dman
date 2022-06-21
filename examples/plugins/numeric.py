"""
Numeric Plugin
---------------------

This plugin provides serializable versions of numpy arrays. Hence 
it can only be imported when ``numpy`` is installed.

"""

import dman
from dman.numeric import sarray, sarrayfield, barray, barrayfield
import numpy as np
import numpy.random as npr


@dman.modelclass
class Data:
    """
    Class containing numeric data

    Parameters
    ----------------
    view:
        serializable numpy array (will be human readable in the json)
    store:
        storable numpy array (will be stored in binary file)

    We need to assign an instance of ``sarrayfield`` or ``barrayfield``
    to handle automatic conversion from ``np.ndarray`` to 
    the types ``sarray`` and ``barray`` respectively. 
    This happens by turing ``view`` and ``store`` into a property with a 
    getter and setter. The setter automatically calls 
    for example ``value.view(sarray)``. 
    """
    view: sarray = sarrayfield()
    store: barray = barrayfield(stem='store')


@dman.modelclass(order=True)
class Config:
    """
    Config like class.
        You can configure an ``sarrayfield`` to automatically convert 
        anything assigned to it to an integer array. Moreover 
        when setting ``compare`` to ``True`` you can make the 
        class comparable. 
    """
    content: sarray = sarrayfield(as_type=int, compare=True)



def main():
    # 1. basic class with numeric data
    print('\nresults ... [1]')
    store = npr.uniform(size=(20, 100))
    view = np.arange(5)

    data = Data(view=view, store=store)
    dman.save('data', data)

    reloaded: Data = dman.load('data')
    print(f'{reloaded.view=}')
    print(f'{reloaded.store.shape=}')

    # 2. comparable class
    print('\nresults ... [2]')
    cfg1 = Config(10*npr.uniform(size=3))
    cfg2 = Config(10*npr.uniform(size=3))
    cfg2.content = np.copy(cfg1.content + 0.1)
    print(f'{cfg1.content=}')
    print(f'{cfg2.content=}')
    print(f'{(cfg1==cfg2)=}')
    cfg2.content[-1] = cfg1.content[-1] + 1
    print(f'{cfg2.content=}')
    print(f'{(cfg1==cfg2)=}')



if __name__ == '__main__':
    main()