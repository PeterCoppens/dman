import dman
import numpy as np

from dman.plotting import PdfFigure, PklFigure, Figure
import matplotlib.pyplot as plt
        

def main():
    # create the figures and save to file ......................................
    f1 = plt.figure()
    plt.plot(np.linspace(0, 1, 100), np.linspace(0, 1, 100)**2)

    f2 = plt.figure()
    plt.plot(np.linspace(0, 1, 100), (np.linspace(0, 1, 100)-0.5)**2)

    dman.save('fig', Figure([f1, f2]))
    plt.close('all')

    # load figures from file (can be executed from different script) ...........
    fig = dman.load('fig')
    print(fig)
    plt.show()


if __name__ == '__main__':
    main()