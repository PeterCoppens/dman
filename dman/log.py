from enum import Enum
import logging
import textwrap
from tkinter.tix import AUTO

LOGGER_NAME = 'dman'
DEFAULT_LOGGING_FORMAT = '[%(name)s] %(message)s'
DEFAULT_HEADER_WIDTH = 20
DEFAULT_INDENT = 2
DEFAULT_LEVEL = logging.NOTSET

from logging import CRITICAL, FATAL, ERROR, WARNING, WARN, INFO, DEBUG, NOTSET

class colors:
    """
    Ansi colors for printing
        see https://www.lihaoyi.com/post/BuildyourownCommandLinewithANSIescapecodes.html
    """
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    DEBUG = '\033[30;1m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def apply_color(text: str, color: str):
    text = text.splitlines()
    text = [color + line + colors.ENDC + '\n' for line in text]
    return ''.join(text)[:-1]

    
def link(uri, label=None):
    if label is None: 
        label = uri
    parameters = ''

    # OSC 8 ; params ; URI ST <name> OSC 8 ;; ST 
    escape_mask = '\033]8;{};{}\033\\{}\033]8;;\033\\'

    return escape_mask.format(parameters, uri, label)


class DmanFormatter(logging.Formatter):
    def format(self, record):
        record.levelname = record.levelname.lower()
        return logging.Formatter.format(self, record)


class Logger(logging.Logger):
    class _LogLayer:
        def __init__(self, parent: 'Logger', msg, label, width, args, kwargs, indent=DEFAULT_INDENT):
            self.parent = parent
            self.msg = msg
            self.label = label
            self.width = width
            self.args = args
            self.kwargs = kwargs
            self.indent = indent
        def __enter__(self):
            self.parent.header(self.msg, self.label, self.width, *self.args, **self.kwargs)
            self.parent.indent(self.indent)
            return self.parent
        def __exit__(self, *_):
            self.parent.indent(-self.indent)
            self.parent.header(self.msg, f'end {self.label}', self.width, *self.args, **self.kwargs)

    def __init__(self, name: str, level=logging.NOTSET) -> None:
        super().__init__(name, level)
        self._indent = 0
        self.header_width = DEFAULT_HEADER_WIDTH
        self._target = None
        self._stream = None

    def indent(self, indent: int = 0, *, increment: bool = True):
        self._indent = self._indent + indent if increment else indent
    
    def pack(self, msg: str, label: str = None):
        if label is not None:
            msg = apply_color(f'[{label}] ', colors.OKGREEN) + msg
        return textwrap.indent(msg, prefix=' '*self._indent)
    
    def path(self, path: str, label: str = None):
        return '"' + apply_color(link(path, label), colors.UNDERLINE) + '"'

    def _check_target(self):
        if isinstance(self._target, Target):
            super().warning(self.pack(apply_color(
                f'could not write to unprepared target "{self._target.name}".', 
                colors.WARNING), 'log')
            )
    
    def info(self, msg: str, label: str = None, *args, **kwargs):
        self._check_target()
        super().info(self.pack(msg, label), *args, **kwargs)
    
    def debug(self, msg, label=None, *args, **kwargs):
        self._check_target()
        super().debug(self.pack(apply_color(msg, colors.DEBUG), label), *args, **kwargs)
    
    def warning(self, msg, label=None, *args, **kwargs):
        self._check_target()
        super().warning(self.pack(apply_color(msg, colors.WARNING), label), *args, **kwargs)
    
    def error(self, msg, label=None, *args, **kwargs):
        self._check_target()
        super().error(self.pack(apply_color(msg, colors.FAIL), label), *args, **kwargs)
    
    def emphasize(self, msg: str, label: str = None, *args, **kwargs):
        self.info(apply_color(msg, colors.OKCYAN), label, *args, **kwargs)
    
    def io(self, msg: str, label: str = None, *args, **kwargs):
        self.info(apply_color(msg, colors.OKBLUE), label, *args, **kwargs)
    
    def header(self, msg: str, label: str = None, width: int = None, *args, **kwargs):
        if width is None: width = self.header_width
        if label is not None:
            label = label + ' '*(width - len(label))
            label = apply_color(label.upper(), colors.HEADER)
            msg = label + msg
        self.info(msg, *args, **kwargs)
    
    def layer(self, msg: str, label: str = None, width: int = None, *args, **kwargs):
        return self._LogLayer(self, msg, label, width, args=args, kwargs=kwargs)



_loggers: dict[str, Logger] = {}


def get_logger(level: int = None, *, name: str = LOGGER_NAME) -> Logger:
    """Returns logger used by dman."""
    global _loggers

    logger = _loggers.get(name, None)
    if logger is None:
        logger: Logger = logging.getLogger(name)
        logger.__class__ = Logger
        logger._indent = 0
        logger.header_width = DEFAULT_HEADER_WIDTH
        logger.setLevel(DEFAULT_LEVEL)
        logger._target = None

        formatter = DmanFormatter(DEFAULT_LOGGING_FORMAT)
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger._stream = handler
        _loggers[name] = logger

    if level is not None:
        logger.setLevel(level)        
    return logger


def setLevel(level: int, *, name: str = LOGGER_NAME):
    return get_logger().setLevel(level)

def path(path: str, label: str = None):
    return get_logger().path(path, label)

def info(msg: str, label: str = None, *args, **kwargs):
    return get_logger().info(msg, label, *args, **kwargs)

def debug(msg, label=None, *args, **kwargs):
    return get_logger().debug(msg, label, *args, **kwargs)

def warning(msg, label=None, *args, **kwargs):
    return get_logger().warning(msg, label, *args, **kwargs)

def error(msg, label=None, *args, **kwargs):
    return get_logger().error(msg, label, *args, **kwargs)

def emphasize(msg: str, label: str = None, *args, **kwargs):
    return get_logger().emphasize(msg, label, *args, **kwargs)

def io(msg: str, label: str = None, *args, **kwargs):
    return get_logger().io(msg, label, *args, **kwargs)

def header(msg: str, label: str = None, width: int = None, *args, **kwargs):
    return get_logger().header(msg, label, width, *args, **kwargs)

def layer(msg: str, label: str = None, width: int = None, *args, **kwargs):
    return get_logger().layer(msg, label, width, *args, **kwargs)


class Target(Enum):
    ROOT = 0
    AUTO = 1

def setStream(*, name: str = LOGGER_NAME):
    logger = get_logger(name=name)
    if logger._stream is not None:
        logger.info('logger already has stream.', label='log')
        return
    formatter = DmanFormatter(DEFAULT_LOGGING_FORMAT)
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger._stream = handler

def unsetFile(*, name: str = LOGGER_NAME):
    logger = get_logger(name=name)
    if isinstance(logger._target, logging.FileHandler):
        logger.removeHandler(logger._target)
        logger._target = None

def setFile(file: str, *, name: str = LOGGER_NAME, exclusive: bool = False):
    logger = get_logger(name=name)
    if exclusive:
        logger.removeHandler(logger._stream)  
        logger._stream = None
    unsetFile(name=name)
    if isinstance(file, Target):
        logger._target = file
        return
    
    formatter = DmanFormatter(DEFAULT_LOGGING_FORMAT)
    handler = logging.FileHandler(file)
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger._target = handler  



if __name__ == '__main__':
    setLevel(INFO)
    header('enter')
    with layer('enter', 'dman', width=10):
        info('test', 'dman')
        io(f'read {path("./README.md")}', 'dman')
    emphasize('finished', 'dman')
    debug('debug')
    warning('warning')
    error('fail')

    log = get_logger(INFO, name='test')
    with log.layer('enter', 'test', width=10):
        log.info('test', 'test')
        log.io(f'read {path("./README.md")}', 'test')