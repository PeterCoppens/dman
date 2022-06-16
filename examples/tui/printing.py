import dman
from dman import tui
from dman.numeric import barrayfield, sarray, barray, sarrayfield
from tempfile import TemporaryDirectory

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
    foo = Foo(
        'hello', 
        {
            'one': Inner('test', [2, 3, 4]),
            'two': Inner('other', [5, 'hello'])
        }, 
        rg.normal(size=(3, 4)), 
        rg.normal(size=(25, 25))
    )

    tui.style(dcl_box=tui.box.MINIMAL, dcl_title=False)
    tui.print(foo)


if __name__ == '__main__':
    main()