"""
TUI plugin
-----------------

The ``tui`` (terminal user interface) is a minimal wrapper around ``rich``,
which is a dependency of the plugin. You can use it to automatically 
display modelclasses in the terminal.

"""


import dman
from dman import tui
from dman.numeric import barrayfield, sarray, barray, sarrayfield

import numpy as np
import numpy.random as npr


@dman.modelclass
class Inner:
    label: str
    content: list


@dman.modelclass
class Foo:
    label: str
    inner: dict
    data: sarray = sarrayfield()
    stored: barray = barrayfield(stem='stored')


def main():
    rg = npr.default_rng(1024)
    inner =  Inner('test', [2, 3, 4])
    foo = Foo(
        'hello', 
        {
            'one': inner,
            'two': Inner('other', [5, 'hello'])
        }, 
        rg.normal(size=(3, 4)), 
        rg.normal(size=(25, 25))
    )

    # we can style the dataclass visualization
    tui.style(dcl_box=tui.box.MINIMAL, dcl_title=False)

    # you can print dataclasses directly
    dman.save('foo', foo)
    foo = dman.load('foo')
    tui.print(foo)

    # printing dictionaries
    dct = dman.mdict()
    dct['test'] = np.eye(2).view(barray)
    dman.save('dct', dct)
    dct = dman.load('dct')
    tui.print(dct)

    # when passing multiple arguments, the print is wrapped in a rich ``Column``
    tui.print(*([inner]*12))


if __name__ == '__main__':
    main()