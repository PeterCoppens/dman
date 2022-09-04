try:
    import rich
except ImportError as e:
    raise ImportError('TUI tools require rich.') from e

from typing import Any, Optional, Union
import os
import pathlib

from dataclasses import dataclass, is_dataclass, fields, asdict
from rich.style import Style
from rich.console import Console as _Console
from rich.console import JustifyMethod
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
from rich import print_json
from rich.json import JSON
from rich.console import Group


from dman.core.serializables import deserialize, serialize, SER_CONTENT, SER_TYPE, BaseInvalid
from dman.model.modelclasses import mdict, smdict, mruns, mlist, smlist
from dman.utils import sjson

_print = print

from rich import print


class Console(_Console):
    def whitespace(self, lines: int):
        self.log('\n'*lines)
    
    def log(
            self, 
            *objects: Any, 
            sep: str = " ", 
            end: str = "\n", 
            style: Optional[Union[str, Style]] = None, 
            justify: Optional[JustifyMethod] = None, 
            emoji: Optional[bool] = None, 
            markup: Optional[bool] = None, 
            highlight: Optional[bool] = None, 
            log_locals: bool = False, 
            _stack_offset: int = 1
        ) -> None:

        if len(objects) > 1:
            objects = [Columns([
                Panel(process(o), box=box.MINIMAL) for o in objects
            ])]


        return super().log(
            *objects, 
            sep=sep, 
            end=end, 
            style=style, 
            justify=justify, 
            emoji=emoji, 
            markup=markup, 
            highlight=highlight, 
            log_locals=log_locals, 
            _stack_offset=_stack_offset
        )


class Style:
    dcl_box: box = box.HEAVY_HEAD
    dct_box: box = box.MINIMAL
    dcl_title: bool = True


def style(
        dcl_box: box = None, 
        dcl_title: bool = None,
        dct_box: box = None,
    ):
    if dcl_box is not None: Style.dcl_box = dcl_box
    if dct_box is not None: Style.dct_box = dct_box
    if dcl_title is not None: Style.dcl_title = dcl_title


def process_dataclass(ser):
    res = dict()
    for f in fields(ser):
        res[f.name] = getattr(ser, f.name)
    
    title = None
    if Style.dcl_title:
        title = f'dataclass: {ser.__class__.__name__}'
    return process_dict(
        res, 
        key='field', 
        value='value', 
        box=Style.dcl_box, 
        title=title
    )


def process_dict(ser: dict, key: str = 'key', value: str = 'value', box=None, title: str = None):
    if box is None: box = Style.dct_box
    table = Table(box=box, title=title, title_justify='left')
    table.add_column(key, justify='left')
    table.add_column(value, justify='left')
    for k, v in ser.items():
        res = process_object(v)
        table.add_row(k, res)
    return table


def process_list(ser: list):
    res = []
    itm_strings = True
    for itm in ser:
        obj = process_object(itm)
        if not isinstance(obj, str): itm_strings = False
        res.append(obj)
    
    if itm_strings:
        return ''.join([s + '\n' for s in res])
    return res


def process_object(obj):
    if isinstance(obj, BaseInvalid):
        return '[...]'
    if isinstance(obj, str):
        return obj
    if isinstance(obj, (list, mlist, smlist, mruns)):
        return process_list(obj)
    if is_dataclass(obj):
        return process_dataclass(obj)
    if isinstance(obj, (dict, mdict, smdict)):  
        return process_dict(obj)
    else: 
        return str(obj)
            

def process(obj):
    """
    Print a serializable
    """
    ser = serialize(obj)
    des = deserialize(ser)
    res = process_object(des)
    if res is None:
        return obj
    return res


def walk_file(path: pathlib.Path):
    text_chars = bytearray({7,8,9,10,12,13,27} | set(range(0x20, 0x100)) - {0x7f})
    with open(path, 'rb') as f:
        is_binary_string = bool(f.read(1024).translate(None, text_chars))
    
    if is_binary_string:
        return  None
    with open(path, 'r') as f:
        content = f.read()
        if path.suffix == '.json':
            return Panel(JSON(content), box=box.SQUARE)
        return Panel(content, box=box.SQUARE)



def walk_directory(directory: pathlib.Path, *, show_content: bool = False, tree: Tree = None) -> None:
    """Print the contents of a directory

    :param directory: directory to print
    :param show_content: show content of text files, defaults to False
    :param tree: add content to tree instead of printing, defaults to None
    """

    # based on https://github.com/Textualize/rich/blob/master/examples/tree.py
    is_root = tree is None
    if is_root:
        tree = Tree(
            f":open_file_folder: [link file://{directory}]{directory}",
            guide_style="bold bright_blue",
        )

    # sort dirs first then by filename
    paths = sorted(
        pathlib.Path(directory).iterdir(),
        key=lambda path: (path.is_file(), path.name.lower()),
    )

    for path in paths:
        # remove hidden files
        if path.name.startswith("."):
            continue
        if path.is_dir():
            style = "dim" if path.name.startswith("__") else ""
            branch = tree.add(
                f"[bold magenta]:open_file_folder: [link file://{path}]{escape(path.name)}",
                style=style,
                guide_style=style,
            )
            walk_directory(path, tree=branch, show_content=show_content)
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
        print(tree)