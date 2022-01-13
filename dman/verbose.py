import logging
import textwrap
from dman.persistent.record import Context, Record, is_removable
from dman.persistent.serializables import ser_str2type, ser_type2str, SER_TYPE
from dman.persistent.serializables import Unserializable, BaseInvalid
from dman.utils import sjson
from dataclasses import is_dataclass


class VerboseContext(Context):
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
    level = 0
    LOGGER = logging.getLogger('verbose')
    HANDLER = logging.StreamHandler()

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
        if label is not None:
            label = self.color_label(label)
        else:
            label = ''
        VerboseContext.LOGGER.info(textwrap.indent(
            str, VerboseContext.level*self.bcolors.INDENT + label))

    def log(self, label: str, msg: str, level: int = 0):
        if isinstance(msg, BaseInvalid):
            self.log(label, str(msg), level=1)
            return

        if level == 1:
            msg = self.color_error(msg)
        if level == 2:
            msg = self.color_accent(msg)
        self.display(msg, label=label)

    def serialize(self, ser, content_only: bool = False):
        if ser is None:
            return ser

        if isinstance(ser, Unserializable):
            self.display(self.color_error(str(ser)))
            return super().serialize(ser, content_only)

        if type(ser) in sjson.atomic_types:
            return super().serialize(ser, content_only)

        title = self.format_serializable(ser)
        self.display(self.color_header('SERIALIZING:     ') + title)
        VerboseContext.level += 1
        res = super().serialize(ser, content_only)
        VerboseContext.level -= 1
        self.display(self.color_header('END SERIALIZING: ') + title)

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
        self.display(self.color_header('DESERIALIZING:     ') + title)
        VerboseContext.level += 1
        res = super().deserialize(serialized, ser_type)
        if isinstance(res, BaseInvalid):
            self.display(self.color_error(str(res)))
        VerboseContext.level -= 1
        self.display(self.color_header('END DESERIALIZING: ') + title)
        return res

    def read(self, sto_type):
        self.display(self.color_io(f'reading from file: "{self.path}"'))
        return super().read(sto_type)

    def write(self, storable):
        self.display(self.color_io(f'writing to file: "{self.path}"'))
        return super().write(storable)

    def delete(self, obj):
        if is_removable(obj) or is_dataclass(obj) or isinstance(obj, (tuple, list, dict)):
            self.parent.remove(obj)
        self.display(self.color_io(f'deleting file: "{self.path}"'))
        return super().delete(obj, remove=False)

    def remove(self, obj):
        if is_removable(obj) or is_dataclass(obj) or isinstance(obj, (tuple, list, dict)):
            title = self.format_remove(obj)
            self.display(self.color_header('REMOVING:   ') + title)
            VerboseContext.level += 1
            res = super().remove(obj)
            VerboseContext.level -= 1
            self.display(self.color_header('END REMOVING: ') + title)
            return res
        return super().remove(obj)


__handler = VerboseContext.HANDLER
__handler.setFormatter(logging.Formatter(fmt="%(message)s"))
VerboseContext.LOGGER.addHandler(__handler)
VerboseContext.LOGGER.setLevel(logging.INFO)


def context(path: str, verbose: int = -1):
    if verbose > 0:
        return VerboseContext(path=path)
    return Context(path=path)
