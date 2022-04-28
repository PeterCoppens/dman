import pickle
import dman

import shutil
from typing import Union, List

import os



try:
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages
except ImportError as e:
    raise ImportError('Plotting tools require matplotlib.') from e


@dman.storable(name='__plt_eps')
class PrintFigure:
    __ext__ = '.eps'

    def __init__(self, fig: plt.Figure, ext: str = '.eps', **kwargs):
        self.__ext__ = ext
        self.fig = fig
        self.kwargs = kwargs

    def __write__(self, path: str):
        self.fig.savefig(path, **self.kwargs)


@dman.storable(name='__plt_pdf')
class PdfFigure:
    __ext__ = '.pdf'

    def __init__(self, fig: Union[List[plt.Figure], plt.Figure] = None, path: str = None, **kwargs):
        if not isinstance(fig, (type(None), list)):
            fig = [fig]
        self.fig = fig
        self.path = path
        self.kwargs = kwargs

    def __write__(self, path: str):
        if self.fig is not None:
            pdf = PdfPages(path)
            for fig in self.fig:
                pdf.savefig(fig, **self.kwargs)
            pdf.close()
        elif self.path != path:
            shutil.copyfile(self.path, path)

        self.path = path
            
    @classmethod
    def __read__(cls, path: str):
        return cls(path=path)


@dman.storable(name='__plt_pkl')
class PklFigure:
    __ext__ = '.fig'

    def __init__(self, fig: Union[List[plt.Figure], plt.Figure]):
        if not isinstance(fig, list):
            fig = [fig]
        self.fig = fig
    
    def __write__(self, path: str):
        with open(path, 'wb') as f:
            pickle.dump(self.fig, f)
    
    @classmethod
    def __read__(cls, path: str):
        with open(path, 'rb') as f:
            fig = pickle.load(f)
        return cls(fig=fig)



try:
    import tikzplotlib
    @dman.storable(name='__plt_tikz')
    class TexFigure:
        __ext__ = '.tex'

        def __init__(self, fig: plt.Figure = None, path: str = None):
            self.path = path
            self.fig = fig
        
        def __write__(self, path: str):
            if self.fig is not None:
                # tikzplotlib.clean_figure()
                tikzplotlib.save(
                    figure=self.fig,
                    filepath=path,
                    axis_width='\linewidth',
                    externalize_tables=False,
                    strict=False,
                    include_disclaimer=False,
                    standalone=False
                )
            elif self.path != path:
                shutil.copyfile()
            self.path = path
            
    @classmethod
    def __read__(cls, path: str):
        return cls(path=path)
except ImportError as e: ...


@dman.modelclass(name='__plt_t_figure')
class t_Figure:
    pdf: PdfFigure = dman.recordfield(stem='preview')
    fig: PklFigure = dman.recordfield(stem='content')

    def __post_init__(self):
        self.pdf.fig = self.fig.fig

    @classmethod
    def __convert__(cls, other: 'Figure'):
        return cls(pdf=PdfFigure(other.fig), fig=PklFigure(other.fig))


@dman.storable(name='__plt_figure')
@dman.serializable(name='__plt_figure', template=t_Figure)
class Figure:
    def __init__(self, fig: Union[List[plt.Figure], plt.Figure]):
        if not isinstance(fig, list):
            fig = [fig]
        self.fig = fig

    @classmethod
    def __convert__(cls, other: t_Figure):
        return cls(fig=other.fig)
        

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