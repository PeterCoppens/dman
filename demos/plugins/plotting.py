"""
Plotting Plugin
------------------------

The ``dman`` package has a figure plugin that can be imported when 
``matplotlib`` is installed. This script shows some example usages.

"""

import dman
import numpy as np

from dman.plotting import PdfFigure, Figure, PrintFigure
import matplotlib.pyplot as plt
        

def main():
    # create the figures and save to file ......................................
    f1 = plt.figure()
    plt.plot(np.linspace(0, 1, 100), np.linspace(0, 1, 100)**2)

    f2 = plt.figure()
    plt.plot(np.linspace(0, 1, 100), (np.linspace(0, 1, 100)-0.5)**2)

    # save loadable figure (save for serializables)
    dman.save('graphic-001', Figure([f1, f2]))

    # store pdf figure (store for storables)
    dman.store('graphic-002', PdfFigure([f1, f2]))
    
    # store eps figure (store for storables)
    dman.store('graphic-003', PrintFigure(f1, ext='.eps'))

    # latex figure
    try:
        from dman.plotting import TexFigure
        dman.store('graphic-004', TexFigure(f1))
    except ImportError as e:
        print(e)

    # close figures
    plt.close('all')

    # load figures from file (can be executed from different script) ...........
    fig = dman.load('graphic-001')
    plt.show()


if __name__ == '__main__':
    main()