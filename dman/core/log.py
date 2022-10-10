import logging as backend
from contextlib import contextmanager
import textwrap
from types import ModuleType
from typing import Mapping, Type
import re


LOGGER_NAME = "dman"
DEFAULT_FORMAT = "%(indent)s%(context)s%(message)s"
BASE_INDENT = "  "

from logging import CRITICAL, FATAL, ERROR, WARN, WARNING, INFO, DEBUG, NOTSET
from logging import basicConfig


class IndentedFormatter(backend.Formatter):
    def __init__(self, fmt=DEFAULT_FORMAT, datefmt=None, style="%", validate=True, capitalize_levelname: bool = False):
        super().__init__(fmt, datefmt, style, validate)
        self.capitalize_levelname = capitalize_levelname
    
    def _format_inner(self, record: backend.LogRecord, fmt: str, include_stack: bool = False):
        if not include_stack:
            formatter = backend.Formatter(fmt)
            record.message = record.getMessage()
            if formatter.usesTime():
                record.asctime = self.formatTime(record, self.datefmt)
            return formatter.formatMessage(record)
        if len(fmt or '') == 0: 
            return fmt
        try:
            return backend.Formatter(fmt).format(record)
        except ValueError:
            return fmt
    
    def format(self, record):
        if self.capitalize_levelname:
            record.levelname = record.levelname.upper()
        else:
            record.levelname = record.levelname.lower()
        splits = re.split('\%\(indent\)[-0-9]*s', self._fmt)
        if len(splits) != 2 or len(record.indent) == 0:
            return super().format(record)
        prefix, indented = [self._format_inner(record, s, '%(message)' in s) for s in splits]
        lines = indented.split('\n')
        s = prefix + textwrap.indent(lines.pop(0), record.indent)
        if len(lines) > 0:
            s += '\n' + textwrap.indent('\n'.join(lines), ' '*len(prefix) + record.indent)
        return s

try:
    from rich.logging import RichHandler
    from rich.theme import Theme
    from rich.console import Console
    from rich.highlighter import RegexHighlighter, Highlighter

    log_theme = Theme(
        {
            "backend.label": "bright_green",
            "backend.tag": "purple",
            "backend.str": "green",
            "backend.path": "green",
            "backend.filename": "green",
            "backend.error": "red",
            "backend.fail": "red",
            "backend.warning": "yellow",
            "backend.warn": "yellow",
            "backend.debug": "bright_black",
            "backend.emphasis": "blue",
            "backend.io": "bright_cyan",
        }
    )

    class LoggingHighlighter(RegexHighlighter):
        """Apply style to anything that looks like an email."""

        base_style = "backend."
        highlights = [
            r"(?P<label>\[(.*?)\]:)",
            r"(?<![\\\w])(?P<str>b?'''.*?(?<!\\)'''|b?'.*?(?<!\\)'|b?\"\"\".*?(?<!\\)\"\"\"|b?\".*?(?<!\\)\")",
            r"(?P<path>\B(/[-\w._:+]+)*\/)(?P<filename>[-\w._+]*)?",
            r"(?P<tag><(.*?)>)",
        ]

    class MinimalHighlighter(RegexHighlighter):
        """Apply style to anything that looks like an email."""

        base_style = "backend."
        highlights = [
            r"(?P<label>\[(.*?)\]:)",
        ]

    class ColorHighlighter(Highlighter):
        def __init__(self, base_color=None, base=LoggingHighlighter) -> None:
            self.base_color = base_color
            self.base = base
            super().__init__()

        def highlight(self, text):
            if self.base_color is not None:
                text.stylize(self.base_color)
            highlighter = self.base()
            highlighter.highlight(text)
            return text

    def format_type(obj):
        if isinstance(obj, (ModuleType, Type)):
            return obj.__name__
        return type(obj).__name__

    def get_highlighter(color: str, minimal: bool):
        return (LoggingHighlighter()
            if color is None
            else ColorHighlighter(
                color, base=MinimalHighlighter if minimal else LoggingHighlighter
            )
        )
    
    def default_handler(fmt: str = DEFAULT_FORMAT, capitalize_levelname: bool = True):
        handler = RichHandler(
            rich_tracebacks=True,
            tracebacks_show_locals=True,
            console=Console(theme=log_theme),
        )
        fmt = IndentedFormatter(fmt, capitalize_levelname=capitalize_levelname)
        handler.setFormatter(fmt)
        return handler
        

except ImportError:
    def get_highlighter(color: str, minimal: bool):
        return None

    def default_handler(fmt: str = DEFAULT_FORMAT, capitalize_levelname: bool = True):
        handler = backend.StreamHandler()
        fmt = IndentedFormatter(fmt, capitalize_levelname=capitalize_levelname)
        handler.setFormatter(fmt)
        return handler


def defaultConfig():
    backend.basicConfig(format=DEFAULT_FORMAT, handlers=[default_handler()])


class Logger(backend.Logger):
    def __init__(self, name: str, level=backend.NOTSET, stack: list = None):
        super().__init__(name, level)
        self.stack = [] if stack is None else stack

    @property
    def indent(self):
        return len(self.stack)

    def format_stack(self):
        if len(self.stack) == 0:
            return ''
        return "".join([format_type(a) + "." for a in self.stack if a is not None])[:-1]


    def pack(
        self,
        msg: str,
        label: str,
        color: str = None,
        minimal: bool = False,
        use_rich_highlighter: bool = False,
    ):
        enabled = self.isEnabledFor(backend.INFO)
        stack = self.stack
        if enabled or len(stack) == 0:
            context = "" if label is None else f"[{label}]: "
        else:
            stack = self.format_stack()
            context = f"[@{stack}" + ("" if label is None else f" | {label}") + "]: "

        indent = ""
        if enabled and self.indent > 0:
            indent = BASE_INDENT * self.indent + " "

        extra = {"context": context, "indent": indent}
        if not use_rich_highlighter:
            extra["highlighter"] = get_highlighter(color, minimal)
        return msg, extra

    def info(
        self,
        msg: str,
        label: str = None,
        color: str = None,
        use_rich_highlighter: bool = False,
    ):
        msg, extra = self.pack(msg, label, color, use_rich_highlighter)
        super().info(msg, extra=extra)

    def debug(self, msg: str, label: str = None):
        msg, extra = self.pack(msg, label)
        super().debug(msg, extra=extra, color="backend.debug")

    def warning(self, msg: str, label: str = None, exc_info=False):
        msg, extra = self.pack(msg, label, color="backend.warning")
        super().warning(msg, extra=extra, exc_info=exc_info)

    def error(self, msg: str, label: str = None, exc_info=False):
        msg, extra = self.pack(msg, label, color="backend.error")
        super().error(msg, extra=extra, exc_info=exc_info)

    def exception(self, msg: str, label: str = None, exc_info=True):
        msg, extra = self.pack(msg, label, color="backend.error")
        super().error(msg, extra=extra, exc_info=exc_info)

    def emphasize(self, msg: str, label: str = None):
        self.info(msg, label, color="backend.emphasis")

    def io(self, msg: str, label: str = None):
        self.info(msg, label, color="backend.io")

    def header(self, msg: str, label: str, prefix: str = "type"):
        if label is not None:
            msg = f"<{label} {prefix}={msg}>"
        self.info(msg)

    @contextmanager
    def layer(
        self, msg: str, label: str = None, prefix: str = "type", owner: str = None
    ):
        self.header(msg, label, prefix)
        self.stack.append(owner)
        yield self
        self.stack.pop()
        self.header(msg, f"end {label}", prefix)

    def makeRecord(
        self,
        name,
        level,
        fn,
        lno,
        msg,
        args,
        exc_info,
        func=None,
        extra=None,
        sinfo=None,
    ):
        """
        A factory method which can be overridden in subclasses to create
        specialized LogRecords.
        """
        _record_factory = backend.getLogRecordFactory()
        rv = _record_factory(name, level, fn, lno, msg, args, exc_info, func, sinfo)
        if extra is not None:
            for key, value in extra.items():
                if key == "context":
                    if rv.context != "":
                        raise KeyError("Attempt to overwrite %r in LogRecord" % key)
                    rv.content = value
                elif key == "indent":
                    if rv.indent != "":
                        raise KeyError("Attempt to overwrite %r in LogRecord" % key)
                    rv.indent = value
                elif (key in ["message", "asctime"]) or (key in rv.__dict__):
                    raise KeyError("Attempt to overwrite %r in LogRecord" % key)
                rv.__dict__[key] = value
        return rv


logger: Logger = backend.getLogger(LOGGER_NAME)
logger.__class__ = Logger
logger.stack = []

_record_factory = backend.getLogRecordFactory()


def record_factory(
    name, level, fn, lno, msg, args, exc_info, func=None, sinfo=None, **kwargs
):
    record = _record_factory(
        name, level, fn, lno, msg, args, exc_info, func, sinfo, **kwargs
    )
    record.context, record.indent = "", ""
    return record


backend.setLogRecordFactory(record_factory)


def info(
    msg: str, label: str = None, color: str = None, use_rich_highlighter: bool = True
):
    if len(logger.handlers) == 0:
        defaultConfig()
    return logger.info(msg, label, color, use_rich_highlighter)


def debug(msg: str, label: str = None):
    if len(logger.handlers) == 0:
        defaultConfig()
    return logger.debug(msg, label)


def warning(msg: str, label: str = None, exc_info=False):
    if len(logger.handlers) == 0:
        defaultConfig()
    return logger.warning(msg, label, exc_info)


def error(msg: str, label: str = None, exc_info=False):
    if len(logger.handlers) == 0:
        defaultConfig()
    return logger.error(msg, label, exc_info)


def exception(msg: str, label: str = None, exc_info=True):
    if len(logger.handlers) == 0:
        defaultConfig()
    return logger.exception(msg, label, exc_info)


def emphasize(msg: str, label: str = None):
    if len(logger.handlers) == 0:
        defaultConfig()
    return logger.emphasize(msg, label)


def io(msg: str, label: str = None):
    if len(logger.handlers) == 0:
        defaultConfig()
    return logger.io(msg, label)


def layer(msg: str, label: str = None, prefix: str = "type", owner: str = None):
    if len(logger.handlers) == 0:
        defaultConfig()
    return logger.layer(msg, label, prefix, owner)



class LogTarget(backend.FileHandler):
    def __init__(self, filename = None):
        super().__init__(filename)
        self.tempdir = None