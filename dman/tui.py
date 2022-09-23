import rich

from typing import Tuple
import os
import pathlib

from rich.style import Style
from rich.console import JustifyMethod, Console, Group
from rich.table import Table
from rich.panel import Panel
from rich.columns import Columns
from rich import box
from rich.progress import track, Progress
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

from dman.core.path import get_root_path
from dman.core.serializables import BaseContext, serialize
from dman import sjson

_print = print

from rich import print


def print_serializable(obj, context: BaseContext = None, content_only: bool = False):
    res = serialize(obj, context=context, content_only=content_only)
    print(JSON(sjson.dumps(res, indent=4)))


def print_json(json: str):
    print(JSON(json))


class TaskStack:
    def __init__(self, state: Tuple[int] = None):
        self.progress = Progress()
        self.total = 1
        self.state = state if state is None else list(state)
        self.registered = []
        self.running = False
        self.tasks = []
        self.lookup = []
    
    def register(self, description: str, steps: int, default_content: dict = None):
        if default_content is None: default_content = dict()
        self.registered.insert(0, (description, steps, self.total, default_content))
        self.total *= steps

        idx = len(self.lookup)
        self.lookup = [l + 1 for l in self.lookup]
        self.lookup.append(0)
        return idx
    
    def __enter__(self):
        self.progress.__enter__()

        # create all tasks
        for d, s, t, c in self.registered:
            task = self.progress.add_task(str.format(d, **c), total=t*s)
            self.tasks.append(task)

        # assign the state
        if self.state is None:
            self.state = [0,]*len(self.tasks)
        else:
            cumulative_work = 0
            for i in reversed(range(len(self.tasks))):
                w = self.registered[i][2]
                cumulative_work += w*self.state[i]
                self.progress.update(self.tasks[i], completed=cumulative_work)
        
        self.running = True
        return self

    def __exit__(self, *_):
        self.progress.stop()
        self.tasks = []
        self.running = False
    
    def __iter__(self):
        entered = False
        if not self.running:
            self.__enter__()
            entered = True

        stack = []
        for (_, steps, _, _), s in zip(self.registered, self.state):
            stack.append(iter(range(s, steps)))
        
        active = 0
        while len(stack) > 0:
            # iterate active stack
            self.state[active] = next(stack[active], None)

            # reset stack layer if we reached the end and decrement active
            if self.state[active] is None:
                if active == 0:
                    # finish
                    for t in self.tasks[1:]:
                        self.progress.remove_task(t)
                    self.progress.update(self.tasks[0], advance=1)
                    if entered:
                        self.__exit__()
                    break

                self.state[active] = 0
                t = self.tasks[active]
                _, steps, _, _ = self.registered[active]
                stack[active] = iter(range(0, steps))
                self.progress.update(t, completed=0)
                active -= 1 # iterate previous layer

            # we iterated on the tail of the stack so yield
            elif active == len(stack) - 1:
                yield self.state
                for t in self.tasks:
                    self.progress.update(t, advance=1)
            
            # climb the stack
            else:
                active += 1
    
    def print(self, msg: str):
        self.progress.print(msg)
    
    def update(self, task: int, **kwargs):
        t = self.lookup[task]
        d, _, _, default = self.registered[t]
        fields = dict.copy(default)
        fields.update(kwargs)
        self.progress.update(
            self.tasks[t], 
            description=str.format(d, **fields)
        )        


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
        if path.suffix == ".py":
            return Panel(Syntax(content), "python")
        return Panel(Text(content), box=box.HORIZONTALS)


def walk_directory(
    directory: pathlib.Path,
    *,
    show_content: bool = False,
    tree: Tree = None,
    normalize: bool = False,
    show_hidden: bool = False,
    console: Console = None,
) -> None:
    """Print the contents of a directory

    :param directory: directory to print
    :param show_content: show content of text files, defaults to False
    :param tree: add content to tree instead of printing, defaults to None
    :param console: console for printing
    """

    # based on https://github.com/Textualize/rich/blob/master/examples/tree.py
    is_root = tree is None
    if is_root:
        name = directory
        if normalize:
            name = os.path.relpath(name, os.path.join(get_root_path(), ".."))
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
            walk_directory(path, tree=branch, show_content=show_content, show_hidden=show_hidden)
        else:
            text_filename = Text(path.name, "green")
            text_filename.highlight_regex(r"\..*$", "green")
            text_filename.stylize(f"link file://{path}")
            file_size = path.stat().st_size
            text_filename.append(f" ({decimal(file_size)})", "blue")
            icon = "🐍 " if path.suffix == ".py" else "📄 "

            res = Text(icon) + text_filename
            if show_content:
                content = walk_file(path)
                if content is not None:
                    res = Group(res, content)
            tree.add(res)

    if is_root:
        if console is None:
            console = Console(width=80)
        console.print(tree)

    