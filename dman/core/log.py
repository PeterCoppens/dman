from dataclasses import MISSING, asdict
import logging as backend
from contextlib import contextmanager
import os
import io as _io
import shutil
from tempfile import TemporaryDirectory
import textwrap
from tkinter import NONE
from types import ModuleType
from typing import List, Type
import re
from uuid import uuid4
from dman.core.errors import Trace


LOGGER_NAME = "dman"
DEFAULT_FORMAT = "%(indent)s%(label)s%(message)s"
DEFAULT_FORMAT_LEVEL = "%(asctime)s %(levelname)s: %(indent)s%(label)s%(message)s"
BASE_INDENT = "  "
CAPITALIZE_LEVELNAME = False

from logging import CRITICAL, FATAL, ERROR, WARN, WARNING, INFO, DEBUG, NOTSET


class IndentedFormatter(backend.Formatter):
    """Formatter that supports indentation and label specification.

    New formatting options: `indent` and `label`
    
    Example:

    >>> fmt = IndentedFormatter(fmt="%(levelname)s: %(indent)s%(label)s%(message)s")
    >>> logger = Logger('example', level=INFO)
    >>> h = backend.StreamHandler()
    >>> h.setFormatter(formatter)
    >>> log.addHandler(hdlr)
    >>> with log.layer('value', 'label'):
    ...     log.info('test')
    ...     log.info('test', 'label')
    <label type=value>
    test
    [label]: test
    <end label type=value>
    """

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
        if not hasattr(record, 'label'):
            setattr(record, 'label', '')
        if not hasattr(record, 'indent'):
            setattr(record, 'indent', '')
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
            
        # record.msg = s
        # record.indent = ''
        # record.label = ''
        return s

def format_type(obj):
    """Get string label for type."""
    if isinstance(obj, (ModuleType, Type)):
        return obj.__name__
    return type(obj).__name__


def default_formatter(fmt: str = DEFAULT_FORMAT, datefmt: str = None, capitalize_levelname: bool = False):
    """Return the default ``dman`` formatter.

    Args:
        fmt (str, optional): Format string.
        datefmt (str, optional): Date format specification. Defaults to None.
        capitalize_levelname (bool, optional): Capitalize the log-level name. Defaults to False.
    """
    return IndentedFormatter(fmt, datefmt, capitalize_levelname=capitalize_levelname)


try:
    from rich.logging import RichHandler
    from rich.theme import Theme
    from rich.console import Console
    from rich.text import Text
    from rich.highlighter import RegexHighlighter, Highlighter
    import rich.traceback as _rich_tb
    from rich.table import Table

    CAPITALIZE_LEVELNAME = True

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
        """Apply coloring to ``dman`` log messages. Highlights label, headers, paths and strings."""

        base_style = "backend."
        highlights = [
            r"(?P<label>\[(.*?)\]:)",
            r"(?<![\\\w])(?P<str>b?'''.*?(?<!\\)'''|b?'.*?(?<!\\)'|b?\"\"\".*?(?<!\\)\"\"\"|b?\".*?(?<!\\)\")",
            r"(?P<path>\B(/[-\w._:+]+)*\/)(?P<filename>[-\w._+]*)?",
            r"(?P<tag><(.*?)>)",
        ]

    class MinimalHighlighter(RegexHighlighter):
        """Only highlight label."""

        base_style = "backend."
        highlights = [
            r"(?P<label>\[(.*?)\]:)",
        ]

    class ColorHighlighter(Highlighter):
        """Highlights all basic text with specified color, still applying base to get specific colors
        for other pieces of text."""
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
        """Get a highlighter.

        Args:
            color (str): The color of the base text.
            minimal (bool): When set to False, :class:`LoggingHighlighter` is 
                applied to the string after setting the base color.
        """
        return (LoggingHighlighter()
            if color is None
            else ColorHighlighter(
                color, base=MinimalHighlighter if minimal else LoggingHighlighter
            )
        )

    def trace2rich(trace: Trace):
        """Convert traceback to internal representation used by rich."""
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
        """The default logging handler used by ``dman``."""
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
            if hasattr(record, 'trace'):
                if self.rich_tracebacks:
                    record.exc_text = ''
                else:
                    delattr(record, 'trace')
            return super().emit(record)
            
        def render(self, *, record: backend.LogRecord, traceback, message_renderable):
            if hasattr(record, 'trace'):
                traceback = _rich_tb.Traceback(
                    trace2rich(record.trace),
                    **self._traceback_kwargs()
                )

            # highlight traceback
            if isinstance(traceback, Text):
                if record.levelno == backend.WARNING:
                    traceback = ColorHighlighter('backend.warning', base=MinimalHighlighter)(traceback)
                elif record.levelno in [backend.ERROR, backend.CRITICAL]:
                    traceback = ColorHighlighter('backend.error', base=MinimalHighlighter)(traceback)
                else:
                    traceback = self.highlighter(traceback)
            
            # apply indent if necessary
            fmt = self.formatter if self.formatter else backend.Formatter()
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
                    
            return super().render(record=record, traceback=traceback, message_renderable=message_renderable)
    
    def default_handler(stream=None, use_rich: bool = True, **kwargs):
        """Get the default handler used by ``dman``.

        The stream is passed to the handler, which is either a standard :class:`backend.StreamHandler`
        or a :class:`DManHandler` instance. Any other keyword arguments are passed to the 
        ``__init__`` method of the handler.

        Additionally the option ``console_style`` can be set to a dictionary. 
        The keyword arguments contained within are passed to the :class:`rich.console.Console`
        initializer and the output console is passed to the `DManHandler`. 
        """
        if not use_rich:
            return backend.StreamHandler(stream)
        console_style = {'theme': log_theme, 'file': stream}
        console_style.update(kwargs.pop('console_style', {}))
        default = dict(
            rich_tracebacks=True,
            tracebacks_show_locals=False,
            console=Console(**console_style),
            enable_link_path=False
        )
        default.update(kwargs)
        return DManHandler(**default)


except ImportError as e:
    def get_highlighter(color: str, minimal: bool):
        """Get a highlighter when ``rich`` is not available. 
        In this case the options have no effect.
        """
        return None

    def default_handler(stream=NONE, **kwargs):
        """Get the default handler when ``rich`` is not available. 
        In this case the returned handler is a standard stream handler."""
        return backend.StreamHandler(stream)


def default_config(level: int = None):
    """Load the default logger configuration."""
    config(level=level, force=True)


def config(*, level=None, filename: str=None, filemode: str = 'a', stream=None, format: str = None, datefmt: str = None, handlers: List[backend.Handler] = None, force: bool = False, **kwargs):
    """Configure the ``dman`` logger.
    
    This function does nothing if the ``dman`` logger already has handlers configured,
    unless if the ``force`` keyword argument is set to true.

    The default behavior is to create a :class:`DmanHandler` using 
    the :func:`default_handler` method. Any keyword arguments not specified below are 
    passed to that method. 

    Args:
        level (_type_, optional): Set the logger level to the specified level.
        filename (str, optional): Specifies that a FileHandler be created, using the specified
            filename, rather than a StreamHandler.
        filemode (str, optional): Specifies the mode to open the file, if filename is specified
            (if filemode is unspecified, it defaults to 'a').
        stream (optional): Use the specified stream to initialize the StreamHandler. Note
            that this argument is incompatible with 'filename' - if both
            are present, 'stream' is ignored.
        format (str, optional): Use the specified format string for the handler.
        datefmt (str, optional): Use the specified date/time format.
        handlers (List[backend.Handler], optional): If specified, this should be 
            an iterable of already created handlers, which will be added to the 
            root handler. Any handler in the list which does not have a formatter 
            assigned will be assigned the formatter created in this function.
        force (bool, optional): If this keyword is specified as true, any 
            existing handlers attached to the root logger are removed and closed, 
            before carrying out the configuration as specified by the other
            arguments.. Defaults to False.

    Note that you could specify a stream created using open(filename, mode)
    rather than passing the filename and mode in. However, it should be
    remembered that StreamHandler does not close its stream (since it may be
    using sys.stdout or sys.stderr), whereas FileHandler closes its stream
    when the handler is closed.
    """
    backend.basicConfig
    if force:
        for h in logger.handlers[:]:
            logger.removeHandler(h)
            h.close()

    if len(logger.handlers) == 0:
        if handlers is None:
            if stream is not None and filename is not None:
                raise ValueError("'stream' and 'filename' should not be "
                                    "specified together")
        elif stream is not None or filename is not None:
            raise ValueError("'stream' or 'filename' should not be "
                                "specified together with 'handlers'")
        if handlers is None:
            if filename:
                h = backend.FileHandler(filename, filemode)
            else:
                h = default_handler(stream=stream, **kwargs)
            handlers = [h]

        if format is None:
            format = DEFAULT_FORMAT if kwargs.get('use_rich', True) else DEFAULT_FORMAT_LEVEL
            
        fmt = default_formatter(format, datefmt, capitalize_levelname=CAPITALIZE_LEVELNAME)
        for h in handlers:
            if h.formatter is None:
                h.setFormatter(fmt)
            logger.addHandler(h)
        
    if level is not None:
        logger.setLevel(level)

            
class Logger(backend.Logger):
    """Logger instance used by ``dman``. Provides some additional logging methods."""

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
            label = "" if label is None else f"[{label}]: "
        else:
            stack = self.format_stack()
            label = f"[@{stack}" + ("" if label is None else f" | {label}") + "]: "

        indent = ""
        if enabled and self.indent > 0:
            indent = BASE_INDENT * self.indent + " "

        extra = {"label": label, "indent": indent}
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
        """Log an info message.

        Args:
            msg (str): message
            label (str, optional): The label added before the message (if specified in format string). Defaults to None.
            color (str, optional): The color of the text. Defaults to None.
            use_rich_highlighter (bool, optional): Use rich highlighting. Defaults to False.
        """
        msg, extra = self.pack(msg, label, color=color, use_rich_highlighter=use_rich_highlighter)
        super().info(msg, extra=extra, *args, **kwargs)

    def debug(self, msg: str, label: str = None, *args, **kwargs):
        """Log a debug message.

        Args:
            msg (str): message
            label (str, optional): The label added before the message (if specified in format string). Defaults to None.
        """
        msg, extra = self.pack(msg, label)
        super().debug(msg, extra=extra, color="backend.debug", *args, **kwargs)

    def warning(self, msg: str, label: str = None, exc_info=False, *args, **kwargs):
        """Log a warning message

        Args:
            msg (str): message
            label (str, optional): The label added before the message (if specified in format string). Defaults to None.
            exc_info (bool, optional): Add exception info. Defaults to False.
        """
        msg, extra, exc_info = self.pack(msg, label, exc_info, color="backend.warning")
        super().warning(msg, extra=extra, exc_info=exc_info, *args, **kwargs)

    def error(self, msg: str, label: str = None, exc_info=False, *args, **kwargs):
        """Log an error message

        Args:
            msg (str): message
            label (str, optional): The label added before the message (if specified in format string). Defaults to None.
            exc_info (bool, optional): Add exception info. Defaults to False.
        """
        msg, extra, exc_info = self.pack(msg, label, exc_info, color="backend.error")
        super().error(msg, extra=extra, exc_info=exc_info, *args, **kwargs)

    def exception(self, msg: str, label: str = None, exc_info=True, *args, **kwargs):
        """Log an exception

        Args:
            msg (str): message
            label (str, optional): The label added before the message (if specified in format string). Defaults to None.
            exc_info (bool, optional): Add exception info. Defaults to True.
        """
        kwargs.update({'stacklevel': kwargs.get('stacklevel', 1)+1})
        self.error(msg, label, exc_info, *args, **kwargs)

    def emphasize(self, msg: str, label: str = None, *args, **kwargs):
        """Log an emphasized info message.

        Args:
            msg (str): message
            label (str, optional): The label added before the message (if specified in format string). Defaults to None.
        """
        kwargs.update({'stacklevel': kwargs.get('stacklevel', 1)+1})
        self.info(msg, label, color="backend.emphasis", *args, **kwargs)

    def io(self, msg: str, label: str = None, *args, **kwargs):
        """Log an info message associated with io.

        Args:
            msg (str): message
            label (str, optional): The label added before the message (if specified in format string). Defaults to None.
        """
        kwargs.update({'stacklevel': kwargs.get('stacklevel', 1)+1})
        self.info(msg, label, color="backend.io", *args, **kwargs)

    def header(self, msg: str, label: str, prefix: str = "type", *args, **kwargs):
        """Log an info header.

        Args:
            msg (str): message
            label (str, optional): The label added before the message (if specified in format string). Defaults to None.
            prefix (str, optional): Prefix added before the message. Defaults to "type".
        """
        kwargs.update({'stacklevel': kwargs.get('stacklevel', 1)+1})
        if label is not None:
            msg = f"<{label} {prefix}={msg}>"
        self.info(msg, *args, **kwargs)

    @contextmanager
    def layer(
        self, msg: str, label: str = None, prefix: str = "type", owner: str = None, *args, **kwargs
    ):
        """Enter a layer context, indenting all future log messages.

        Args:
            msg (str): message
            label (str, optional): The label added before the message (if specified in format string). Defaults to None.
            owner (Str, optional): Owner of the layer, which is added to the stack. Defaults to None.
            prefix (str, optional): Prefix added before the message. Defaults to "type".
        """
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
            rv.exc_info = None
        return rv
    
    def _log(self, level, msg, args, exc_info = None, extra=None, stack_info: bool=False, stacklevel: int=1) -> None:
        return super()._log(level, msg, args, exc_info, extra, stack_info, stacklevel+2)



logger: Logger = backend.getLogger(LOGGER_NAME)
logger.__class__ = Logger
logger.propagate = False
logger.stack = []


def info(
    msg: str, label: str = None, color: str = None, use_rich_highlighter: bool = False
):
    """Log an info message.

    Args:
        msg (str): message
        label (str, optional): The label added before the message (if specified in format string). Defaults to None.
        color (str, optional): The color of the text. Defaults to None.
        use_rich_highlighter (bool, optional): Use rich highlighting. Defaults to False.
    """
    if len(logger.handlers) == 0:
        default_config()
    return logger.info(msg, label, color, use_rich_highlighter, stacklevel=2)


def debug(msg: str, label: str = None):        
    """Log a debug message.

    Args:
        msg (str): message
        label (str, optional): The label added before the message (if specified in format string). Defaults to None.
    """
    if len(logger.handlers) == 0:
        default_config()
    return logger.debug(msg, label, stacklevel=2)


def warning(msg: str, label: str = None, exc_info=False):
    """Log a warning message

    Args:
        msg (str): message
        label (str, optional): The label added before the message (if specified in format string). Defaults to None.
        exc_info (bool, optional): Add exception info. Defaults to False.
    """
    if len(logger.handlers) == 0:
        default_config()
    return logger.warning(msg, label, exc_info, stacklevel=2)


def error(msg: str, label: str = None, exc_info=False, stacklevel=1):
    """Log an error message

    Args:
        msg (str): message
        label (str, optional): The label added before the message (if specified in format string). Defaults to None.
        exc_info (bool, optional): Add exception info. Defaults to False.
    """
    if len(logger.handlers) == 0:
        default_config()
    return logger.error(msg, label, exc_info, stacklevel=2)


def exception(msg: str, label: str = None, exc_info=True):
    """Log an exception

    Args:
        msg (str): message
        label (str, optional): The label added before the message (if specified in format string). Defaults to None.
        exc_info (bool, optional): Add exception info. Defaults to True.
    """
    if len(logger.handlers) == 0:
        default_config()
    return logger.exception(msg, label, exc_info, stacklevel=2)


def emphasize(msg: str, label: str = None):
    """Log an emphasized info message.

    Args:
        msg (str): message
        label (str, optional): The label added before the message (if specified in format string). Defaults to None.
    """
    if len(logger.handlers) == 0:
        default_config()
    return logger.emphasize(msg, label, stacklevel=2)


def io(msg: str, label: str = None):
    """Log an info message associated with io.

    Args:
        msg (str): message
        label (str, optional): The label added before the message (if specified in format string). Defaults to None.
    """
    if len(logger.handlers) == 0:
        default_config()
    return logger.io(msg, label, stacklevel=2)


def layer(msg: str, label: str = None, prefix: str = "type", owner: str = None):
    """Enter a layer context, indenting all future log messages.

    Args:
        msg (str): message
        label (str, optional): The label added before the message (if specified in format string). Defaults to None.
        owner (Str, optional): Owner of the layer, which is added to the stack. Defaults to None.
        prefix (str, optional): Prefix added before the message. Defaults to "type".
    """
    if len(logger.handlers) == 0:
        default_config()
    return logger.layer(msg, label, prefix, owner, stacklevel=2)
        

@contextmanager
def logger_context(level: bool = None):
    """Enter a logger context with a temporary log level.
    
    Example:

    >>> with logger_context(level=INFO):
    ...     info('test', 'label')
    """
    if level is None:
        yield logger
        return

    _level = logger.level
    logger.setLevel({True: INFO, False: WARNING}.get(level, level))
    yield logger
    logger.setLevel(_level)