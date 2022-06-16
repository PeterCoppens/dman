try:
    import rich
except ImportError as e:
    raise ImportError('TUI tools require rich.') from e


from dataclasses import dataclass, is_dataclass, fields, asdict
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.columns import Columns
from rich import box


from dman.persistent.serializables import deserialize, serialize, SER_CONTENT, SER_TYPE, BaseInvalid
from dman.utils import sjson

_print = print

from rich import print as _rich_print

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
    for itm in ser:
        res.append(process_object(itm) + '\n')
    return ''.join(res)


def process_object(obj):
    if isinstance(obj, BaseInvalid):
        return '[...]'
    if isinstance(obj, str):
        return obj
    if isinstance(obj, list):
        return process_list(obj)
    if is_dataclass(obj):
        return process_dataclass(obj)
    if isinstance(obj, dict):  
        return process_dict(obj)
    else:
        return str(obj)
            

def process(obj):
    """
    Print a serializable
    """
    ser = serialize(obj)
    obj = deserialize(ser)
    return process_object(obj)

def print(obj):
    _rich_print(process(obj))

    

    
    