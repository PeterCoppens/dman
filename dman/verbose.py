from ast import Str
from enum import Enum
import logging
import textwrap
import os
from dman.path import get_root_path
from dman.persistent.record import Context, Record, is_removable
from dman.persistent.serializables import Undeserializable, ser_str2type, ser_type2str
from dman.persistent.serializables import Unserializable, BaseInvalid
from dataclasses import is_dataclass


class bcolors:
    """
    Ansi colors for printing
    """
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    INDENT = '  '


class Level(Enum):
    DEBUG = 1
    SOFT = 2


class SerializationLevel:
    def __init__(self, label: str, title: str, type: str, context: 'VerboseContext'):
        self.label = label
        self.type = type
        self.title = title
        self.context = context

    def __enter__(self):
        self.context.head(f'{self.label}: ', self.title)
        VerboseContext.stack.append(self.type)
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        VerboseContext.stack.pop()
        self.context.head(f'END {self.label}: ', self.title)


class VerboseContext(Context):
    HEADER_WIDTH = 20
    LOGGER = logging.getLogger('verbose')
    HANDLER = logging.StreamHandler()
    LEVEL = Level.DEBUG

    stack = []

    def apply_color(self, text: str, color: str):
        text = text.splitlines()
        text = [color + line + bcolors.ENDC + '\n' for line in text]
        return ''.join(text)[:-1]

    def display(self, str, label: str = None):
        if label is not None:
            label = self.apply_color(f'[{label}] ', bcolors.OKGREEN)
        else:
            label = ''
        
        indent = 0
        if VerboseContext.LEVEL is Level.DEBUG:
            indent=len(VerboseContext.stack)
        VerboseContext.LOGGER.info(textwrap.indent(
            str, indent * bcolors.INDENT + label))

    def info(self, label: str, msg: str):
        if VerboseContext.LEVEL is Level.DEBUG:
            self.display(msg, label=label)
    
    def emphasize(self, label: str, msg: str):
        if VerboseContext.LEVEL is Level.DEBUG:
            self.display(
                self.apply_color(msg, bcolors.OKCYAN), label=label
            )
    
    def error(self, label: str, msg: str):
        if isinstance(msg, BaseInvalid):
            msg = str(msg)
        if VerboseContext.LEVEL is Level.DEBUG:
            self.display(self.apply_color(msg, bcolors.FAIL), label=label)
        elif VerboseContext.LEVEL is Level.SOFT:
            head = ''
            for s in VerboseContext.stack:
                head += s.__name__ + ' / '
            self.display(head[:-1])
            self.display(self.apply_color(msg, bcolors.FAIL), label=label)

    def io(self, label: str, msg: str):
        self.display(self.apply_color(msg, bcolors.OKBLUE), label)
    
    def head(self, label: str, msg: str):
        if VerboseContext.LEVEL is Level.DEBUG:
            label = label + ' '*(VerboseContext.HEADER_WIDTH - len(label))
            label = self.apply_color(label, bcolors.HEADER)
            self.display(label+ msg)
    
    def layer(self, label: str, title: str, type: str = None):
        return SerializationLevel(label, title, type, self)

    def serialize(self, ser, content_only: bool = False):
        if isinstance(ser, Unserializable):
            self.error(label=None, msg=str(ser))
        return super().serialize(ser, content_only)
    
    def _serialize__object(self, ser):
        title = f'{type(ser).__name__}(name={ser_type2str(ser)})'
        with self.layer('SERIALIZING', title, type(ser)):
            return super()._serialize__object(ser)
    
    def _serialize__list(self, ser):
        title = f'list(len={len(ser)})' 
        with self.layer('SERIALIZING', title, type(ser)):
            return super()._serialize__list(ser)
    
    def _serialize__dict(self, ser):
        title = f'dict(len={len(ser)})'
        with self.layer('SERIALIZING', title, type(ser)):
            return super()._serialize__dict(ser)

    def deserialize(self, serialized, ser_type=None):
        ser = super().deserialize(serialized, ser_type)
        if isinstance(ser_str2type, Undeserializable):
            self.error(None, str(ser))
        return ser
    
    def _deserialize__object(self, serialized, expected):
        title = f'{expected.__name__}(name={ser_type2str(expected)})'
        with self.layer('DESERIALIZING', title, expected):
            return super()._deserialize__object(serialized, expected)
    
    def _deserialize__list(self, cls, ser):
        title = f'list(len={len(ser)})'
        with self.layer('DESERIALIZING', title, list):
            return super()._deserialize__list(cls, ser)
    
    def _deserialize__dict(self, cls, ser: dict):
        title = f'dict(len={len(ser)})'
        with self.layer('DESERIALIZING', title, dict):
            return super()._deserialize__dict(cls, ser)        

    def read(self, sto_type):
        if VerboseContext.LEVEL is Level.DEBUG:
            self.io('read', f'reading from file: "{self.path}"')
        return super().read(sto_type)

    def write(self, storable):
        if VerboseContext.LEVEL is Level.DEBUG:
            self.io('write', f'writing to file: "{self.path}"')
        return super().write(storable)

    def delete(self, obj):
        if is_removable(obj) or is_dataclass(obj) or isinstance(obj, (tuple, list, dict)):
            self.parent.remove(obj)
        if VerboseContext.LEVEL is Level.DEBUG:
            self.io('delete', f'deleting file: "{self.path}"')
        return super().delete(obj, remove=False)

    def remove(self, obj):
        if is_removable(obj) or is_dataclass(obj) or isinstance(obj, (tuple, list, dict)):
            title = f'{type(obj).__name__}'
            if isinstance(obj, Record):
                title = str(obj)
            with self.layer('REMOVING', title, type(obj)):
                res = super().remove(obj)
            return res
        return super().remove(obj)


__handler = VerboseContext.HANDLER
__handler.setFormatter(logging.Formatter(fmt="%(message)s"))
VerboseContext.LOGGER.addHandler(__handler)
VerboseContext.LOGGER.setLevel(logging.INFO)


def context(path: Str, verbose: int = -1):
    if verbose > 0:
        return VerboseContext(path=path)
    return Context(path=path)


def setup(logfile: str = None, loglevel: Level = None):
    if loglevel is not None:
        VerboseContext.LEVEL = loglevel

    if logfile is not None:
        logfile = os.path.join(get_root_path(), logfile)
        base, _ = os.path.split(logfile)
        if not os.path.isdir(base):
            os.mkdir(base)
            
        log = VerboseContext.LOGGER
        for hdlr in log.handlers[:]:
            log.removeHandler(hdlr)
        log.addHandler(logging.FileHandler(logfile, mode='w'))