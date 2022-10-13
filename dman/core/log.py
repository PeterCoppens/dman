from ast import Import
from dataclasses import MISSING, asdict
import logging as backend
from contextlib import contextmanager
import sys
import textwrap
from types import ModuleType
from typing import Mapping, Type
import re
from dman.core.errors import Trace


LOGGER_NAME = "dman"
DEFAULT_FORMAT = "%(indent)s%(context)s%(message)s"
BASE_INDENT = "  "

from logging import CRITICAL, FATAL, ERROR, WARN, WARNING, INFO, DEBUG, NOTSET


class IndentedFormatter(backend.Formatter):
    def __init__(self, fmt=DEFAULT_FORMAT, datefmt=None, style="%", validate=True, capitalize_levelname: bool = False):
        super().__init__(fmt, datefmt, style, validate)
        self.capitalize_levelname = capitalize_levelname
    
    def _format_inner(self, record: backend.LogRecord, fmt: str, include_stack: bool = False):
        if len(fmt or '') == 0: 
            return fmt
        if not include_stack:
            formatter = backend.Formatter(fmt)
            record.message = record.getMessage()
            if formatter.usesTime():
                record.asctime = self.formatTime(record, self.datefmt)
            return formatter.formatMessage(record)
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
            
        record.msg = s
        record.indent = ''
        record.context = ''
        return s

def format_type(obj):
    if isinstance(obj, (ModuleType, Type)):
        return obj.__name__
    return type(obj).__name__

try:
    from rich.logging import RichHandler
    from rich.theme import Theme
    from rich.console import Console
    from rich.text import Text
    from rich.highlighter import RegexHighlighter, Highlighter
    import rich.traceback as _rich_tb
    from rich._null_file import NullFile
    from rich.table import Table

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

    def get_highlighter(color: str, minimal: bool):
        return (LoggingHighlighter()
            if color is None
            else ColorHighlighter(
                color, base=MinimalHighlighter if minimal else LoggingHighlighter
            )
        )

    def trace2rich(trace: Trace):
        stacks = []
        for stack in trace.stacks:
            frames = []
            for frame in stack.frames:
                frames.append(_rich_tb.Frame(**asdict(frame)))
            kwargs = asdict(stack)
            kwargs.update({"frames": frames})
            stacks.append(_rich_tb.Stack(**kwargs))
        return _rich_tb.Trace(stacks) 
    
    class DManHandler(RichHandler):
        def _traceback_kwargs(self):
            return dict(
                width=self.tracebacks_width,
                extra_lines=self.tracebacks_extra_lines,
                theme=self.tracebacks_theme,
                word_wrap=self.tracebacks_word_wrap,
                show_locals=self.tracebacks_show_locals,
                locals_max_length=self.locals_max_length,
                locals_max_string=self.locals_max_string,
                suppress=self.tracebacks_suppress,
            )
        def emit(self, record: backend.LogRecord) -> None:
            """Invoked by logging."""
            traceback = None
            fmt = self.formatter if self.formatter else backend.Formatter()

            if self.rich_tracebacks:
                if hasattr(record, 'trace') and record.trace is not None:
                    traceback = _rich_tb.Traceback(
                        trace2rich(record.trace),
                        **self._traceback_kwargs()
                    )
                elif record.exc_info and record.exc_info != (None, None, None):
                    exc_type, exc_value, exc_traceback = record.exc_info
                    assert exc_type is not None
                    assert exc_value is not None
                    traceback = _rich_tb.Traceback.from_exception(
                        exc_type,
                        exc_value,
                        exc_traceback,
                        **self._traceback_kwargs()
                    )
                if traceback is not None:
                    message = record.getMessage()
                    if self.formatter:
                        record.message = record.getMessage()
                        formatter = self.formatter
                        if hasattr(formatter, "usesTime") and formatter.usesTime():
                            record.asctime = formatter.formatTime(record, formatter.datefmt)
                        message = formatter.formatMessage(record)
            elif record.exc_text:
                traceback = Text(record.exc_text)
            elif record.exc_info and record.exc_info != (None, None, None):
                traceback = Text(fmt.formatException(record.exc_info))

            # highlight traceback
            if isinstance(traceback, Text):
                if record.levelno == backend.WARNING:
                    traceback = ColorHighlighter('backend.warning', base=MinimalHighlighter)(traceback)
                elif record.levelno in [backend.ERROR, backend.CRITICAL]:
                    traceback = ColorHighlighter('backend.error', base=MinimalHighlighter)(traceback)
                else:
                    traceback = self.highlighter(traceback)
            
            # apply indent if necessary
            if len(record.indent) > 0 and traceback:
                splits = re.split('\%\(indent\)[-0-9]*s', fmt._fmt)
                if len(splits) == 2 and '%(message)' in splits[1]:
                    output = Table.grid(padding=(0, 0))
                    output.add_column()
                    output.add_column()
                    output.add_row(
                        Text(record.indent), traceback
                    )
                    traceback = output

            record.exc_text = ''
            record.exc_info = None
            
            message = fmt.format(record)

            message_renderable = self.render_message(record, message)
            log_renderable = self.render(
                record=record, traceback=traceback, message_renderable=message_renderable
            )
            if isinstance(self.console.file, NullFile):
                # Handles pythonw, where stdout/stderr are null, and we return NullFile
                # instance from Console.file. In this case, we still want to make a log record
                # even though we won't be writing anything to a file.
                self.handleError(record)
            else:
                try:
                    self.console.print(log_renderable)
                except Exception:
                    self.handleError(record)
    
    def default_handler(fmt: str = DEFAULT_FORMAT, capitalize_levelname: bool = True, rich_tracebacks: bool = True):
        handler = DManHandler(
            rich_tracebacks=rich_tracebacks,
            tracebacks_show_locals=False,
            console=Console(theme=log_theme),
            enable_link_path=False
        )
        fmt = IndentedFormatter(fmt, capitalize_levelname=capitalize_levelname)
        handler.setFormatter(fmt)
        return handler


except ImportError:
    def get_highlighter(color: str, minimal: bool):
        return None

    def default_handler(fmt: str = DEFAULT_FORMAT, capitalize_levelname: bool = True, **kwargs):
        handler = backend.StreamHandler()
        fmt = IndentedFormatter(fmt, capitalize_levelname=capitalize_levelname)
        handler.setFormatter(fmt)
        return handler


def defaultConfig(level: int = None):
    backend.basicConfig(format=DEFAULT_FORMAT, handlers=[default_handler()], level=level)


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
        exc_info = MISSING,
        *,
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

        if exc_info is MISSING:
            return msg, extra
        if isinstance(exc_info, Trace):
            extra['trace'] = exc_info
            return msg, extra, None
        return msg, extra, exc_info

    def info(
        self,
        msg: str,
        label: str = None,
        color: str = None,
        use_rich_highlighter: bool = False,
        *args,
        **kwargs
    ):
        msg, extra = self.pack(msg, label, color=color, use_rich_highlighter=use_rich_highlighter)
        super().info(msg, extra=extra, *args, **kwargs)

    def debug(self, msg: str, label: str = None, *args, **kwargs):
        msg, extra = self.pack(msg, label)
        super().debug(msg, extra=extra, color="backend.debug", *args, **kwargs)

    def warning(self, msg: str, label: str = None, exc_info=False, *args, **kwargs):
        msg, extra, exc_info = self.pack(msg, label, exc_info, color="backend.warning")
        super().warning(msg, extra=extra, exc_info=exc_info, *args, **kwargs)

    def error(self, msg: str, label: str = None, exc_info=False, *args, **kwargs):
        msg, extra, exc_info = self.pack(msg, label, exc_info, color="backend.error")
        super().error(msg, extra=extra, exc_info=exc_info, *args, **kwargs)

    def exception(self, msg: str, label: str = None, exc_info=True, *args, **kwargs):
        kwargs.update({'stacklevel': kwargs.get('stacklevel', 1)+1})
        self.error(msg, label, exc_info, *args, **kwargs)

    def emphasize(self, msg: str, label: str = None, *args, **kwargs):
        kwargs.update({'stacklevel': kwargs.get('stacklevel', 1)+1})
        self.info(msg, label, color="backend.emphasis", *args, **kwargs)

    def io(self, msg: str, label: str = None, *args, **kwargs):
        kwargs.update({'stacklevel': kwargs.get('stacklevel', 1)+1})
        self.info(msg, label, color="backend.io", *args, **kwargs)

    def header(self, msg: str, label: str, prefix: str = "type", *args, **kwargs):
        kwargs.update({'stacklevel': kwargs.get('stacklevel', 1)+1})
        if label is not None:
            msg = f"<{label} {prefix}={msg}>"
        self.info(msg, *args, **kwargs)

    @contextmanager
    def layer(
        self, msg: str, label: str = None, prefix: str = "type", owner: str = None, *args, **kwargs
    ):
        kwargs.update({'stacklevel': kwargs.get('stacklevel', 1)+1})
        self.header(msg, label, prefix, *args, **kwargs)
        self.stack.append(owner)
        yield self
        self.stack.pop()
        self.header(msg, f"end {label}", prefix, *args, **kwargs)

    def makeRecord(self, *args, **kwargs):
        rv = super().makeRecord(*args, **kwargs)
        trace: Trace = getattr(rv, 'trace', None)
        if trace:
            rv.exc_text = ''.join(trace.format())
        return rv
    
    def _log(self, level, msg, args, exc_info = None, extra=None, stack_info: bool=False, stacklevel: int=1) -> None:
        return super()._log(level, msg, args, exc_info, extra, stack_info, stacklevel+2)



logger: Logger = backend.getLogger(LOGGER_NAME)
logger.__class__ = Logger
logger.stack = []


def info(
    msg: str, label: str = None, color: str = None, use_rich_highlighter: bool = False
):
    if len(logger.handlers) == 0:
        defaultConfig()
    return logger.info(msg, label, color, use_rich_highlighter, stacklevel=2)


def debug(msg: str, label: str = None):
    if len(logger.handlers) == 0:
        defaultConfig()
    return logger.debug(msg, label, stacklevel=2)


def warning(msg: str, label: str = None, exc_info=False):
    if len(logger.handlers) == 0:
        defaultConfig()
    return logger.warning(msg, label, exc_info, stacklevel=2)


def error(msg: str, label: str = None, exc_info=False, stacklevel=1):
    if len(logger.handlers) == 0:
        defaultConfig()
    return logger.error(msg, label, exc_info, stacklevel=2)


def exception(msg: str, label: str = None, exc_info=True):
    if len(logger.handlers) == 0:
        defaultConfig()
    return logger.exception(msg, label, exc_info, stacklevel=2)


def emphasize(msg: str, label: str = None):
    if len(logger.handlers) == 0:
        defaultConfig()
    return logger.emphasize(msg, label, stacklevel=2)


def io(msg: str, label: str = None):
    if len(logger.handlers) == 0:
        defaultConfig()
    return logger.io(msg, label, stacklevel=2)


def layer(msg: str, label: str = None, prefix: str = "type", owner: str = None):
    if len(logger.handlers) == 0:
        defaultConfig()
    return logger.layer(msg, label, prefix, owner, stacklevel=2)



class LogTarget(backend.FileHandler):
    def __init__(self, filename = None):
        super().__init__(filename)
        self.tempdir = None