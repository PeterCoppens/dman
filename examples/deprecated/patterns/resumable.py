"""
Resumable Pattern
--------------------

When running long simulations it can often be useful to allow interruption 
of the script. Here is a simple template describing how to do so with dman.

To run this script you require ``numpy`` and ``rich`` (for the progress bar).

"""

import time
import numpy as np
import numpy.random as npr
import dman
from dman.numeric import barray, barrayfield
import dman.tui as tui


@dman.modelclass
class Run:
    data: barray = barrayfield(
        stem='data',
        default_factory=lambda: np.zeros(1000)
    )
    _state: int = 0


def main():
    run: Run = dman.load('run', default_factory=Run)
    with tui.Progress() as progress:
        task = progress.add_task('running (try interrupting with CTRL+C and restarting the script)...', total=len(run.data))
        progress.update(task, advance=run._state)
        for i in range(run._state, len(run.data)):
            point = npr.beta(a=5, b=1)
            run.data[i], run._state = point, i
            time.sleep(0.1)
            dman.save('run', run)
            progress.update(task, advance=1)


if __name__ == '__main__':
    main()


