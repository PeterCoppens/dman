try:
    import rich
except ImportError as e:
    raise ImportError('TUI tools require rich.') from e

from typing import Any, Optional, Union

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
from rich import inspect


from dman.persistent.serializables import deserialize, serialize, SER_CONTENT, SER_TYPE, BaseInvalid
from dman.persistent.modelclasses import mdict, smdict, mruns, mlist, smlist
from dman.utils import sjson

_print = print

from rich import print as _rich_print


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

def print(*obj):
    if len(obj) == 1:
        _rich_print(process(obj[0]))
    else:
        res = [Panel(process(o), box=box.MINIMAL) for o in obj]
        _rich_print(Columns(res))

    

    
    