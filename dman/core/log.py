from enum import Enum
import logging as backend
import textwrap
from typing import Dict

LOGGER_NAME = "dman"
_LOGGER_NAME_ERROR = "__dman"
DEFAULT_LOGGING_FORMAT = "%(message)s"
DEFAULT_HEADER_WIDTH = 20
DEFAULT_INDENT = 4
DEFAULT_LEVEL = backend.CRITICAL

from logging import CRITICAL, FATAL, ERROR, WARNING, WARN, INFO, DEBUG, NOTSET

try:
    from rich.logging import RichHandler
    from rich.theme import Theme
    from rich.console import Console
    from rich.highlighter import RegexHighlighter, Highlighter, _combine_regex
    from rich.text import Text
    _rich_available = True
except ImportError:
    _rich_available = False


class colors(Enum):
    """
    colors for printing
        see https://www.lihaoyi.com/post/BuildyourownCommandLinewithANSIescapecodes.html
    """

    HEADER = 'purple'
    OKBLUE = 'blue'
    OKCYAN = 'cyan'
    OKGREEN = 'green'
    WARNING = "orange1"
    DEBUG = "bright_black"
    FAIL = "red"
    FRAME = "bold"


class LoggingHighlighter(RegexHighlighter):
    """Apply style to anything that looks like an email."""
    base_style = "logging."
    highlights = [
        r"(?P<label>\[[\w]+\])",
        _combine_regex(
            r"(?P<path>\B(/[-\w._+]+)*\/)(?P<filename>[-\w._+]*)?",
            r"(?<![\\\w])(?P<str>b?'''.*?(?<!\\)'''|b?'.*?(?<!\\)'|b?\"\"\".*?(?<!\\)\"\"\"|b?\".*?(?<!\\)\")",
            r"(?P<url>(file|https|http|ws|wss)://[-0-9a-zA-Z$_+!`(),.?/;:&=%#]*)"
        )
    ]


class ColorHighlighter(Highlighter):
    def __init__(self, base_color = None) -> None:
        self.base_color = base_color
        super().__init__()
        
    def highlight(self, text):
        text._text = [t.replace('\[', '[') for t in text._text]
        if self.base_color is not None:
            text.stylize(self.base_color)
        highlighter = LoggingHighlighter()
        highlighter.highlight(text)
        return text


class DmanFormatter(backend.Formatter):
    def __init__(self, fmt=DEFAULT_LOGGING_FORMAT, datefmt=None, style='%', validate=True):
        """
        Initialize the formatter with specified format strings.

        Initialize the formatter either with the specified format string, or a
        default as described above. Allow for specialized date formatting with
        the optional datefmt argument. If datefmt is omitted, you get an
        ISO8601-like (or RFC 3339-like) format.

        Use a style parameter of '%', '{' or '$' to specify that you want to
        use one of %-formatting, :meth:`str.format` (``{}``) formatting or
        :class:`string.Template` formatting in your format string.

        .. versionchanged:: 3.2
           Added the ``style`` parameter.
        """
        super().__init__(fmt, datefmt, style, validate)

    def format(self, record):
        record.levelname = record.levelname.lower()
        return backend.Formatter.format(self, record)


class Logger(backend.Logger):
    class _LogLayer:
        def __init__(
            self,
            parent: "Logger",
            msg,
            label,
            owner,
            width,
            args,
            kwargs,
            indent=DEFAULT_INDENT,
        ):
            self.parent = parent
            self.msg = msg
            self.label = label
            self.width = width
            self.owner = owner
            self.args = args
            self.kwargs = kwargs
            self.indent = indent

        def __enter__(self):
            self.parent.header(
                self.msg, self.label, self.width, *self.args, **self.kwargs
            )
            self.parent.indent(self.indent)
            self.parent.put(self.owner)
            return self.parent

        def __exit__(self, *_):
            self.parent.indent(-self.indent)
            self.parent.header(
                self.msg, f"end {self.label}", self.width, *self.args, **self.kwargs
            )
            self.parent.pop()

    def __init__(self, name: str, level=backend.NOTSET) -> None:
        super().__init__(name, level)
        self._indent = 0
        self.header_width = DEFAULT_HEADER_WIDTH
        self._stream = None
        self._stack = []

    def put(self, owner: str):
        self._stack.append(owner)

    def pop(self):
        self._stack.pop()

    def indent(self, indent: int = 0, *, increment: bool = True):
        self._indent = self._indent + indent if increment else indent

    def stack(self):
        return "".join([a + "." for a in self._stack if a is not None])[:-1]

    def pack(self, msg: str, label: str = None):
        if label is not None:
            msg = f"[{label}]" + ' ' + msg
        if 0 < self.level <= INFO:
            return textwrap.indent(msg, prefix=" " * self._indent)
        stack = self.stack()
        if len(stack) == 0:
            return msg
        return f"[{stack}]" + ' ' + msg

    def info(self, msg: str, label: str = None, *args, **kwargs):
        super().info(self.pack(msg, label), *args, **kwargs, extra={'highlighter': ColorHighlighter()})

    def debug(self, msg, label=None, *args, **kwargs):
        super().debug(
            self.apply_color(
                self.pack(msg, label),
                colors.DEBUG
            ), *args, **kwargs
        )

    def warning(self, msg, label=None, *args, **kwargs):
        super().warning(
            self.apply_color(
                self.pack(msg, label),
                colors.WARNING
            ), *args, **kwargs
        )

    def error(self, msg, label=None, *args, **kwargs):
        super().error(self.pack(msg, label), *args, **kwargs)

    def emphasize(self, msg: str, label: str = None, *args, **kwargs):
        super().info(self.pack(msg, label), *args, **kwargs, extra={'highlighter': ColorHighlighter('blue')})

    def io(self, msg: str, label: str = None, *args, **kwargs):
        super().info(self.pack(msg, label), *args, **kwargs, extra={'highlighter': ColorHighlighter('cyan')})

    def header(self, msg: str, label: str = None, width: int = None, *args, **kwargs):
        if width is None:
            width = self.header_width
        if label is not None:
            label = label + " " * (width - len(label))
            label = label.upper()
            msg = label + msg
        self.info(msg, *args, **kwargs)

    def layer(
        self,
        msg: str,
        label: str = None,
        owner: str = None,
        width: int = None,
        *args,
        **kwargs,
    ):
        return self._LogLayer(self, msg, label, owner, width, args=args, kwargs=kwargs)


_loggers: Dict[str, Logger] = {}


def getLogger(name: str = None, *, level: int = None) -> Logger:
    """Returns logger used by dman."""
    global _loggers

    if name is None:
        name = LOGGER_NAME

    if isinstance(name, backend.Logger):
        name = name.name

    if isinstance(name, Logger):
        logger = name
    else:
        logger = _loggers.get(name, None)
        if logger is None:
            logger: Logger = backend.getLogger(name)
            logger.__class__ = Logger
            logger.header_width = DEFAULT_HEADER_WIDTH
            logger._indent = 0
            logger._stack = []
            logger.setLevel(DEFAULT_LEVEL)

            formatter = DmanFormatter(DEFAULT_LOGGING_FORMAT)
            handler = RichHandler(
                show_level=False, 
                show_path=True, 
                show_time=False, 
                keywords=['SERIALIZING', 'DESERIALIZING', 'END'], 
                markup=False, 
                highlighter=LoggingHighlighter(),
                console=Console(
                    theme=Theme({
                        'logging.keyword': 'purple', 
                        'logging.label': 'bold green',
                        'logging.str': 'green',
                        'logging.path': 'green'
                    })
                )
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger._stream = handler
            _loggers[name] = logger

    if level is not None:
        logger.setLevel(level)
    return logger


def setLevel(level: int, *, name: str = LOGGER_NAME):
    return getLogger().setLevel(level)

def info(msg: str, label: str = None, *args, **kwargs):
    return getLogger().info(msg, label, *args, **kwargs)


def debug(msg, label=None, *args, **kwargs):
    return getLogger().debug(msg, label, *args, **kwargs)


def warning(msg, label=None, *args, **kwargs):
    return getLogger().warning(msg, label, *args, **kwargs)


def error(msg, label=None, *args, **kwargs):
    return getLogger().error(msg, label, *args, **kwargs)


def emphasize(msg: str, label: str = None, *args, **kwargs):
    return getLogger().emphasize(msg, label, *args, **kwargs)


def io(msg: str, label: str = None, *args, **kwargs):
    return getLogger().io(msg, label, *args, **kwargs)


def header(msg: str, label: str = None, width: int = None, *args, **kwargs):
    return getLogger().header(msg, label, width, *args, **kwargs)


def layer(
    msg: str, label: str = None, owner: str = None, width: int = None, *args, **kwargs
):
    return getLogger().layer(msg, label, owner, width, *args, **kwargs)


class LogTarget(backend.FileHandler):
    ...