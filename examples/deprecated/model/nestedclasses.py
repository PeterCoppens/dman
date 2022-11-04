from tempfile import TemporaryDirectory
import dman
from dman import tui


@dman.modelclass(frozen=True, storable=True)
class Inner:
    content: str


@dman.modelclass(storable=True)
class Outer:
    inner: Inner


inner = Inner('test')
outer = Outer(inner)
with TemporaryDirectory() as tdir:
    tui.print_serializable(outer, dman.context(tdir, verbose=True))
    tui.walk_directory(tdir, show_content=True)

