from dataclasses import dataclass, field
from typing import List, Type, Any
from types import TracebackType
import traceback
import re


@dataclass
class Frame:
    filename: str
    lineno: int
    name: str
    line: str = ""

    def __post_init__(self):
        if isinstance(self.lineno, str):
            self.lineno = int(self.lineno)

    def __str__(self):
        return f"File {self.filename}, line {self.lineno}, in {self.name}: {self.line}"

    def __serialize__(self):
        return str(self)

    @classmethod
    def __deserialize__(cls, ser):
        pattern = r"File (?P<filename>.*), line (?P<lineno>[0-9]*), in (?P<name>.*): (?P<line>)"
        res, *_ = re.findall(pattern, ser)
        return cls(*res)
    
    def summary(self):
        return traceback.FrameSummary(self.filename, self.lineno, self.name)


@dataclass
class Stack:
    exc_type: str
    exc_value: str
    is_cause: bool = False
    frames: List[Frame] = field(default_factory=list)

    def __serialize__(self):
        res = {"exc": f"{self.exc_type}({self.exc_value})"}
        if self.is_cause:
            res["is_cause"] = True
        res["frames"] = [frame.__serialize__() for frame in self.frames]
        return res
    
    def __str__(self):
        return self.format_exception()

    @classmethod
    def __deserialize__(cls, ser: dict):
        exc = ser.pop("exc")
        pattern = r"(?P<filename>.*)\((?P<name>.*)\)"
        (ser["exc_type"], ser["exc_value"]), *_ = re.findall(pattern, exc)
        res = cls(**ser)
        res.frames = [Frame.__deserialize__(frame) for frame in res.frames]
        return res

    def format_exception(self):
        yield f'{self.exc_type}: {self.exc_value}'
    
    def format(self, *, single: bool = False):
        if single:
            yield '\n'
        elif not self.is_cause:
            yield '\n\nThe above exception was the direct cause of the following exception:\n\n'
            
        if len(self.frames) > 0:
            yield 'Traceback (most recent call last):\n'
            yield from traceback.StackSummary.from_list(
                [frame.summary() for frame in self.frames]
            ).format()

        yield from self.format_exception()


@dataclass
class Trace:
    stacks: List[Stack] = field(default_factory=list)

    def __serialize__(self):
        return [stack.__serialize__() for stack in self.stacks]

    @classmethod
    def __deserialize__(cls, ser: list):
        return cls([Stack.__deserialize__(stack) for stack in ser])

    @classmethod
    def from_exception(
        cls,
        exc_type: Type[BaseException],
        exc_value: BaseException,
        exc_tb: TracebackType,
        *,
        ignore: int = 0
    ):
        def safe_str(_object: Any) -> str:
            try:
                return str(_object)
            except Exception:
                return "<exception str() failed>"

        stacks: List[Stack] = []
        is_cause = False

        while True:
            summary = traceback.extract_tb(exc_tb)
            frames = [Frame(f.filename, f.lineno, f.name, f.line) for f in summary]
            stacks.append(
                Stack(
                    safe_str(exc_type.__name__), safe_str(exc_value), is_cause, frames
                )
            )

            cause = getattr(exc_value, "__cause__", None)
            if cause and cause.__traceback__:
                exc_type = cause.__class__
                exc_value = cause
                exc_tb = cause.__traceback__
                is_cause = True
                continue

            cause = exc_value.__context__
            if (
                cause
                and cause.__traceback__
                and not getattr(exc_value, "__suppress_context__", False)
            ):
                exc_type = cause.__class__
                exc_value = cause
                exc_tb = cause.__traceback__
                is_cause = False
                continue
            # No cover, code is reached but coverage doesn't recognize it.
            break  # pragma: no cover

        res = cls(stacks)
        if ignore > 0:
            res.stacks[0].frames = res.stacks[0].frames[ignore:]
        return res
    
    def format(self):
        for stack in reversed(self.stacks):
            yield from stack.format(single=len(self.stacks) == 1)


@dataclass(repr=False)
class BaseInvalid:
    """Invalid object encountered by ``dman``."""
    type: str   #: The name of the type.
    info: str   #: Description of the problem.

    def __repr__(self):
        return f'{self.header} ({self.info})'

    def format(self):
        """Generator producing the description of the invalid object."""
        yield self.header + '\n'
        yield ' '*4 + self.info
    
    @property
    def header(self):
        """Header of the description."""
        return f'{self.__class__.__name__}: {self.type}'

    def __str__(self):
        return ''.join(self.format())

    def __serialize__(self):
        res = {'type': self.type}
        if len(self.info) > 0:
            res['info'] = self.info
        return res

    @classmethod
    def __deserialize__(cls, ser: dict):
        return cls(ser.get('type'), ser.get('info', ''))


@dataclass(repr=False)
class ExcInvalid(BaseInvalid):
    """Invalid object created through some exception."""
    trace: Trace    #: The traceback of the exception.

    @classmethod
    def from_exception(
        cls,
        exc_type: Type[BaseException],
        exc_value: BaseException,
        exc_tb: TracebackType,
        *,
        ignore: int = 0,
        **kwargs,
    ):
        """Create an invalid object from an exception.

        Args:
            exc_type (Type[BaseException]): The type of the exception
            exc_value (BaseException): The value of the exception
            exc_tb (TracebackType): The traceback
            ignore (int, optional): Layers of the traceback that should be omitted. Defaults to 0.
        """
        trace = Trace.from_exception(exc_type, exc_value, exc_tb, ignore=ignore)
        return cls(**kwargs, trace=trace)

    def format(self):
        yield from super().format()
        yield from self.trace.format()
    
    def __serialize__(self):
        return dict(
            **super().__serialize__(), 
            trace=self.trace.__serialize__()
        )
    
    @classmethod
    def __deserialize__(cls, ser):
        return cls(
            ser.get('type'), 
            ser.get('info', ''), 
            Trace.__deserialize__(ser.get('trace'))
        )
