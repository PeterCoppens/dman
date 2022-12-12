import pickle
import dman

import shutil
from typing import Union, List
import subprocess
import re
import textwrap

import os
import math



try:
    import matplotlib
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

    @classmethod
    def __read__(self):
        raise RuntimeError('Cannot read PrintFigure objects.')


class SVGLogFormatter(matplotlib.ticker.LogFormatterMathtext):
    def _non_decade_format(self, sign_string, base, fx, usetex):
        """Return string for non-decade locations."""
        return r'\$%s%s^{%.2f}\$' % (sign_string, base, fx)

    def __call__(self, x, pos=None):
        # docstring inherited
        min_exp = plt.rcParams['axes.formatter.min_exponent']

        if x == 0:  # Symlog
            return r'\$0\$'

        sign_string = '-' if x < 0 else ''
        x = abs(x)
        b = self._base

        # only label the decades
        fx = math.log(x) / math.log(b)
        is_x_decade = matplotlib.ticker.is_close_to_int(fx)
        exponent = round(fx) if is_x_decade else np.floor(fx)
        coeff = round(b ** (fx - exponent))
        if is_x_decade:
            fx = round(fx)

        if self.labelOnlyBase and not is_x_decade:
            return ''
        if self._sublabels is not None and coeff not in self._sublabels:
            return ''

        # use string formatting of the base if it is not an integer
        if b % 1 == 0.0:
            base = '%d' % b
        else:
            base = '%s' % b

        if abs(fx) < min_exp:
            return r'\$%s%g\$' % (sign_string, x)
        elif not is_x_decade:
            return self._non_decade_format(sign_string, base, fx)
        else:
            return r'\$%s%s^{%d}\$' % (sign_string, base, fx)


@dman.storable(name='__plt_svg')
class SVGFigure:
    __ext__ = '.svg'

    def __init__(self, fig: plt.Figure, generate_tex: bool = False, **kwargs):
        self.fig = fig
        self.kwargs = kwargs
        self.generate_tex = generate_tex
    
    def _generate_tex(self, base: str):
        try:
            subprocess.run([
                'inkscape', 
                '-D', 
                '-z', 
                f'--file={base}.svg', 
                f'--export-pdf={base}.pdf', 
                '--export-latex'
            ])
        except FileNotFoundError:
            dman.log.warning('Inkscape is not installed on this platform.')
        
        if not os.path.exists(f'{base}.pdf_tex'):
            raise RuntimeError('Inkscape failed to generate tex at "{base}.pdf_tex".')
        
        with open(f'{base}.pdf_tex', 'r') as f:
            content = f.readlines()

        idx1 = next(i for i, e in enumerate(content) if 'makeatletter' in e)
        idx2 = next(i for i, e in enumerate(content) if 'makeatother' in e)
        pre, post = content[:idx1+1], content[idx2:]
        commands = ''.join(content[idx1+1:idx2])

        # add svgfont command
        commands = textwrap.dedent(commands)
        commands = commands.split('\n')[:-1]
        msg = textwrap.dedent('''\
        \\ifx\\svgfont\\undefined%
        \\global\\let\\svgfont\\footnotesize
        \\fi%    
        ''')
        commands.extend(msg.split('\n'))
        commands = textwrap.indent('\n'.join(commands), prefix=' '*2)
        commands = [commands]

        pattern = re.compile(r'(\\begin\{tabular\}\[t]\{.\})(.*?)(\\end\{tabular\})')
        replace = r'\g<1>\\svgfont{}\g<2>\g<3>'
        for i, line in enumerate(post):
            post[i] = pattern.sub(replace, line)

        with open(f'{base}.tex', 'w') as f:
            f.writelines(pre+commands+post)
        os.remove(f'{base}.pdf_tex')

    def __write__(self, path: str):
        if self.generate_tex:
            keys = ['svg.fonttype', 'mathtext.default', 'text.usetex']
            old = {key: plt.rcParams[key] for key in keys}
            plt.rcParams['svg.fonttype'] = 'none'
            plt.rcParams['mathtext.default'] = 'regular'
            plt.rcParams['text.usetex'] = False        

            changes = []
            for ax in self.fig.get_axes():
                for cax in [ax.xaxis, ax.yaxis]:
                    fmt = cax.get_major_formatter()
                    if isinstance(fmt, matplotlib.ticker.LogFormatter):
                        cax.set_major_formatter(SVGLogFormatter())
                        changes.append((cax, fmt))
                
        self.fig.savefig(path, **self.kwargs)

        if self.generate_tex:
            # TODO has no effect
            plt.rcParams.update(old)
            for cax, fmt in changes:
                cax.set_major_formatter(fmt)
            
            self._generate_tex(os.path.splitext(path)[0])

    @classmethod
    def __read__(self):
        raise RuntimeError('Cannot read PrintFigure objects.')


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
        elif os.path.exists(self.path) and self.path != path:
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