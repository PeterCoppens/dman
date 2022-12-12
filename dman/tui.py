import rich

from typing import Dict, Iterable, Sequence, Tuple
import os
import pathlib
from collections import OrderedDict

from rich.style import Style
from rich.console import JustifyMethod, Console, Group
from rich.table import Table
from rich.panel import Panel
from rich.columns import Columns
from rich import box
from rich.progress import Progress, track
from rich.live import Live
from rich.tree import Tree
from rich.markup import escape
from rich import inspect
from rich.filesize import decimal
from rich.markup import escape
from rich.text import Text
from rich.json import JSON
from rich.syntax import Syntax
from rich.pretty import pprint

from dman.core.path import get_root_path, normalize_path
from dman.core.serializables import BaseContext, serialize
from dman import sjson

_print = print

from rich import print


def print_serializable(obj, context: BaseContext = None, content_only: bool = False):
    print_serialized(serialize(obj, context=context, content_only=content_only))


def print_serialized(ser):
    print_json(sjson.dumps(ser, indent=4))


def print_json(json: str):
    print(JSON(json))



def progress(it: Iterable, description: str = None, show_state: bool = True, total = None):
    if total is None and hasattr(it, "__len__"):
        total = len(it)
    if description is None:
        description = f'Iterating "{it.__class__.__name__}"'
    if total and show_state:
        description = description + ' [{i}/{t}]'
        def gen(i, t):
            return description.format(i=i, t=t)
    else:
        total = 100.0
        def gen(i, t):
            return description
        
    with Progress() as progress:
        task = progress.add_task(gen(0, total), total=total)
        for i, o in enumerate(it):
            progress.update(task, advance=1, description=gen(i+1, total), refresh=True)
            yield o


class StackGenerator:
    def __init__(self, state: Tuple[int] = None):
        self.progress = None
        self._state = [] if state is None else list(state)
        self.registered: Dict[StackLayer, int] = dict()
        self.index: Dict[StackLayer, int] = OrderedDict()

    @property
    def state(self):
        return list(self.index.values())

    def print(self, msg: str):
        self.progress.print(msg)

    def __call__(
        self,
        it: Iterable,
        *,
        total: int = None,
        keep: bool = None,
        description: str = None,
        post: str = ' ...',
        show_state: bool = True,
        log: dict = None,
    ):
        if keep is None:
            keep = len(self.registered) == 0
        if total is None and hasattr(it, "__len__"):
            total = len(it)
        if log is None:
            log = dict()
        logstr = ''
        for k in log:
            logstr += (str(k) + '={' + str(k) +'}, ')
        if len(logstr) > 0:
            logstr = ' | ' + logstr[:-2] + ' |' 
        if description is None:
            description = f'Iterating "{it.__class__.__name__}"'
        if total and show_state:
            description = description + ' [{state}/{total}]'
            log.update({'state': 1, 'total': total})
        description += logstr + post

        state = 0 if len(self._state) == 0 else self._state.pop(0)
        layer = StackLayer(it, self, state, keep, description, log)
        layer._update(total=total)
        self.registered[layer] = self.add_task(layer.description, total=total)
        self.index[layer] = 0
        return layer

    def range(self, *args, description: str = None, **kwargs):
        if description is None: description = 'Range'
        it = range(*args)
        return self.__call__(it, description=description, **kwargs)

    def add_task(self, name, total: int = None):
        if self.progress is None:
            return None
        return self.progress.add_task(name, total=total)

    def remove_task(self, task: "StackLayer"):
        if self.progress is None:
            return
        self.progress.remove_task(self.registered[task])
        del self.index[task]

    def update(self, task: "StackLayer", completed: int, description: str = None):
        if self.progress is None:
            return
        self.index[task] += 1
        self.progress.update(self.registered[task], completed=completed, description=description, refresh=True)
    
    def start(self):
        self.progress = Progress()
        self.progress.__enter__()

    def stop(self):
        self.progress.stop()
        self.progress = None
        for r in self.registered:
            r.progress = None

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *_):
        self.stop()


class StackLayer:
    def __init__(
        self,
        it: Iterable,
        parent: StackGenerator,
        state: int = 0,
        keep: bool = False,
        description: str = None,
        log: dict = None
    ):        
        self._description = description
        self.log = dict() if log is None else log
        self.parent = parent
        self.skip = state
        self.keep = keep
        self.state = 0
        self.it = it

    @property
    def description(self):
        return str.format(self._description, **self.log)

    def __iter__(self):
        for x in self.it:
            if self.state >= self.skip:
                yield x
            self.state += 1
            self.update(state=min(self.log.get('total', 0), self.state+1))
        if not self.keep:
            self.parent.remove_task(self)
    
    def _update(self, **kwargs):
        for k, v in kwargs.items():
            if k in self.log:
                self.log[k] = v

    def update(self, **kwargs):
        self._update(**kwargs)
        self.parent.update(self, completed=self.state, description=self.description)


def stack(state: Tuple[int] = None):
    return StackGenerator(state)


def walk_file(path: pathlib.Path):
    text_chars = bytearray({7, 8, 9, 10, 12, 13, 27} | set(range(0x20, 0x100)) - {0x7F})
    with open(path, "rb") as f:
        is_binary_string = bool(f.read(1024).translate(None, text_chars))

    if is_binary_string:
        return None
    with open(path, "r") as f:
        content = f.read()
        if path.suffix == ".json":
            return Panel(JSON(content), box=box.HORIZONTALS)
        # if path.suffix == ".py":
        #     return Panel(Syntax(content), "python")
        return Panel(Text(content), box=box.HORIZONTALS)


def walk_directory(
    directory: pathlib.Path,
    *,
    show_content: bool = False,
    tree: Tree = None,
    normalize: bool = True,
    show_hidden: bool = False,
    console: Console = None,
) -> None:
    """Print the contents of a directory

    :param directory: directory to print
    :param show_content: show content of text files, defaults to False. If True 
        all non-binary files are shown. If a list of strings then only files with that 
        extension are shown. For example show_content=['.json'] shows json files only.
    :param tree: add content to tree instead of printing, defaults to None
    :param normalize: normalize paths with respect to dman root directory, defaults to True
    :param show_hidden: show hidden files, defaults to False
    :param console: console for printing
    """

    # based on https://github.com/Textualize/rich/blob/master/examples/tree.py
    is_root = tree is None
    if is_root:
        name = directory
        if normalize:
            name = normalize_path(name)
        tree = Tree(
            f":open_file_folder: [link file://{directory}]{name}",
            guide_style="bold bright_blue",
        )

    # sort dirs first then by filename
    paths = sorted(
        pathlib.Path(directory).iterdir(),
        key=lambda path: (path.is_file(), path.name.lower()),
    )

    for path in paths:
        # remove hidden files
        if not show_hidden and path.name.startswith("."):
            continue
        if path.is_dir():
            style = "dim" if path.name.startswith("__") else ""
            branch = tree.add(
                f"[bold magenta]:open_file_folder: [link file://{path}]{escape(path.name)}",
                style=style,
                guide_style=style,
            )
            walk_directory(
                path, tree=branch, show_content=show_content, show_hidden=show_hidden
            )
        else:
            text_filename = Text(path.name, "green")
            text_filename.highlight_regex(r"\..*$", "green")
            text_filename.stylize(f"link file://{path}")
            file_size = path.stat().st_size
            text_filename.append(f" ({decimal(file_size)})", "blue")
            icon = "🐍 " if path.suffix == ".py" else "📄 "

            res = Text(icon) + text_filename
            if (
                (
                    isinstance(show_content, Sequence)
                    and os.path.splitext(path.name)[-1] in show_content
                ) or (
                    isinstance(show_content, bool)
                    and show_content == True)
            ):
                content = walk_file(path)
                if content is not None:
                    res = Group(res, content)
            tree.add(res)

    if is_root:
        if console is None:
            console = Console(width=80)
        console.print(tree)
