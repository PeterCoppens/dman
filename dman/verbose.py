from ast import Str
from enum import Enum
import logging
import textwrap
import os
from dman.path import get_root_path
from dman.persistent.record import Context, Record, is_removable
from dman.persistent.serializables import ser_str2type, ser_type2str, SER_TYPE, validate
from dman.persistent.serializables import Unserializable, BaseInvalid
from dman.utils import sjson
from dataclasses import is_dataclass


class Level(Enum):
    DEBUG = 1
    SOFT = 2


current_level = Level.DEBUG


class VerboseContext(Context):
    class __SerializationLevel:
        def __init__(self, label: str, title: str, context: 'VerboseContext'):
            self.label = label
            self.title = title
            self.context = context

        def __enter__(self):
            self.context.head(f'{self.label}: ', self.title)
            VerboseContext.stack.append(self.title)
        
        def __exit__(self, exc_type, exc_val, exc_tb):
            VerboseContext.stack.pop()
            self.context.head(f'END {self.label}: ', self.title)

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

    HEADER_WIDTH = 20
    LOGGER = logging.getLogger('verbose')
    HANDLER = logging.StreamHandler()

    stack = []

    def format_remove(self, obj):
        if isinstance(obj, Record):
            return str(obj)
        return f'{type(obj).__name__}'

    def format_serializable(self, ser):
        return f'{type(ser).__name__}(name={ser_type2str(ser)})'

    def format_serialized(self, serialized, ser_type):
        if isinstance(serialized, (list, tuple)):
            return str(type(serialized).__name__)
        if ser_type is None:
            if not isinstance(serialized, dict):
                return '<UNKNOWN TYPE>'
            ser_type = serialized.get(SER_TYPE, None)
            if ser_type is None:
                return 'dict'
        if isinstance(ser_type, str):
            ser_type = ser_str2type(ser_type)
            if ser_type is None:
                return '<UNKNOWN TYPE>'
        return f'{ser_type.__name__}(name={ser_type2str(ser_type)})'


    def apply_color(self, text: str, color: str):
        text = text.splitlines()
        text = [color + line + self.bcolors.ENDC + '\n' for line in text]
        return ''.join(text)[:-1]

    def color_accent(self, text):
        return self.apply_color(text, self.bcolors.OKCYAN)

    def color_header(self, text):
        text = text + ' '*(VerboseContext.HEADER_WIDTH - len(text))
        return self.apply_color(text, self.bcolors.HEADER)

    def color_error(self, text):
        return self.apply_color(text, self.bcolors.FAIL)

    def color_io(self, text):
        return self.apply_color(text, self.bcolors.OKBLUE)

    def color_label(self, text):
        return self.apply_color(f'[{text}] ', self.bcolors.OKGREEN)


    def display(self, str, label: str = None):
        if current_level is Level.DEBUG and label is not None:
            label = self.color_label(label)
        else:
            label = ''
        
        indent = 0
        if current_level is Level.DEBUG:
            indent=len(VerboseContext.stack)
        VerboseContext.LOGGER.info(textwrap.indent(
            str, indent * self.bcolors.INDENT + label))


    def info(self, label: str, msg: str):
        if current_level is Level.DEBUG:
            self.display(msg, label=label)
    
    def emphasize(self, label: str, msg: str):
        if current_level is Level.DEBUG:
            self.display(self.color_accent(msg), label=label)
    
    def layer(self, label: str, title: str):
        return VerboseContext.__SerializationLevel(label, title, self)
    
    def head(self, label: str, msg: str):
        if current_level is Level.DEBUG:
            self.display(self.color_header(label) + msg)
    
    def error(self, label: str, msg: str):
        if isinstance(msg, BaseInvalid):
            msg = str(msg)
        if current_level is Level.DEBUG:
            self.display(self.color_error(msg), label=label)
        elif current_level is Level.SOFT:
            head = ''
            for s in VerboseContext.stack:
                head += s + '>'
            self.display(head[:-1], label=label)
            self.display(self.color_error(msg), label=label)
            

    def serialize(self, ser, content_only: bool = False):
        if ser is None:
            return ser

        if isinstance(ser, Unserializable):
            self.display(self.color_error(str(ser)))
            return super().serialize(ser, content_only)

        if type(ser) in sjson.atomic_types:
            return super().serialize(ser, content_only)

        title = self.format_serializable(ser)
        with self.layer('SERIALIZING', title):
            res = super().serialize(ser, content_only)

        return res

    def deserialize(self, serialized, ser_type=None):
        if serialized is None:
            return serialized

        if ser_type in sjson.atomic_types or type(serialized) in sjson.atomic_types:
            res = super().deserialize(serialized, ser_type)
            if isinstance(res, BaseInvalid):
                self.display(self.color_error(str(res)))
            return res

        title = self.format_serialized(serialized, ser_type)
        with self.layer('DESERIALIZING', title):
            res = super().deserialize(serialized, ser_type)
            if isinstance(res, BaseInvalid):
                self.display(self.color_error(str(res)))
        return res

    def read(self, sto_type):
        if current_level is Level.DEBUG:
            self.display(self.color_io(f'reading from file: "{self.path}"'))
        return super().read(sto_type)

    def write(self, storable):
        if current_level is Level.DEBUG:
            self.display(self.color_io(f'writing to file: "{self.path}"'))
        return super().write(storable)

    def delete(self, obj):
        if is_removable(obj) or is_dataclass(obj) or isinstance(obj, (tuple, list, dict)):
            self.parent.remove(obj)
        if current_level is Level.DEBUG:
            self.display(self.color_io(f'deleting file: "{self.path}"'))
        return super().delete(obj, remove=False)

    def remove(self, obj):
        if is_removable(obj) or is_dataclass(obj) or isinstance(obj, (tuple, list, dict)):
            title = self.format_remove(obj)
            with self.layer('REMOVING', title):
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
        global current_level
        current_level = loglevel

    if logfile is not None:
        logfile = os.path.join(get_root_path(), logfile)
        base, _ = os.path.split(logfile)
        if not os.path.isdir(base):
            os.mkdir(base)
            
        log = VerboseContext.LOGGER
        for hdlr in log.handlers[:]:
            log.removeHandler(hdlr)
        log.addHandler(logging.FileHandler(logfile, mode='w'))