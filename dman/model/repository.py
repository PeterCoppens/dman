from contextlib import contextmanager
from dataclasses import MISSING
import os
from tempfile import TemporaryDirectory
from uuid import uuid4
import shutil

from dman.core import log
from dman.model.record import Context, record
from dman.core.serializables import deserialize, is_serializable, serialize
from dman.core.storables import is_storable
from dman.utils import sjson
from dman.core.path import normalize_path, Target, AUTO
from dman.core.storables import storable

import signal


@contextmanager
def uninterrupted():
    values = None

    def handler(signum, frame):
        global values
        values = (signum, frame)

    original = signal.getsignal(signal.SIGINT)
    signal.signal(signal.SIGINT, handler)
    yield
    signal.signal(signal.SIGINT, original)
    if values is not None:
        raise KeyboardInterrupt()


@contextmanager
def context(
    key: str,
    *,
    subdir: os.PathLike = "",
    cluster: bool = True,
    verbose: int = None,
    generator: str = MISSING,
    base: os.PathLike = None,
    gitignore: bool = True,
):
    """Get a context from a mount point.
        The path of the file is determined as described below.

            If the files are clustered then the path is ``<base>/<generator>/<subdir>/<key>/<key>.<ext>``
            If cluster is set to False then the path is ``<base>/<generator>/<subdir>/<key>.<ext>``

            When base is not provided then it is set to .dman if
            it does not exist an exception is raised.

            When generator is not provided it will automatically be set based on
            the location of the script relative to the .dman folder
            (again raising an exception if it is not found). For example
            if the script is located in ``<project-root>/examples/folder/script.py``
            and .dman is located in ``<project-root>/.dman``.
            Then generator is set to cache/examples:folder:script (i.e.
            the / is replaced by : in the output).

    Args:
        key (str):  Key for the file.
        subdir (os.PathLike, optional): Specifies optional subdirectory in generator folder. Defaults to "".
        cluster (bool, optional): A subfolder ``key`` is automatically created when set to True. Defaults to True.
        verbose (bool, optional): Level of verbosity. Defaults to False
        generator (str, optional): Specifies the generator that created the file. Defaults to script label.
        base (os.PathLike, optional): Specifies the root folder. Defaults to ".dman".
        gitignore (bool, optional): Specifies whether files added to this mount point should be ignored.
    """
    with log.logger_context(level=verbose):
        ctx = Context.mount(
            key,
            subdir=subdir,
            cluster=cluster,
            generator=AUTO if generator is MISSING else generator,
            base=base,
            gitignore=gitignore,
        )
        yield ctx
        ctx.close()


def store(
    key: str,
    obj,
    *,
    subdir: os.PathLike = "",
    cluster: bool = False,
    verbose: int = None,
    gitignore: bool = True,
    generator: str = MISSING,
    base: os.PathLike = None,
):
    """
    Save a storable object.
        The path of the file is determined as described below.

            If the files are clustered then the path is ``<base>/<generator>/<subdir>/<key>/<key>.<ext>``
            If cluster is set to False then the path is ``<base>/<generator>/<subdir>/<key>.<ext>``

            When base is not provided then it is set to .dman if
            it does not exist an exception is raised.

            When generator is not provided it will automatically be set based on
            the location of the script relative to the .dman folder
            (again raising an exception if it is not found). For example
            if the script is located in ``<project-root>/examples/folder/script.py``
            and .dman is located in ``<project-root>/.dman``.
            Then generator is set to cache/examples:folder:script (i.e.
            the / is replaced by : in the output).

    Args:
        key (str):  Key for the file.
        obj (Any): The storable to store.
        subdir (os.PathLike, optional): Specifies optional subdirectory in generator folder. Defaults to "".
        cluster (bool, optional): A subfolder ``key`` is automatically created when set to True. Defaults to True.
        verbose (bool, optional): Level of verbosity. Defaults to False
        generator (str, optional): Specifies the generator that created the file. Defaults to script label.
        base (os.PathLike, optional): Specifies the root folder. Defaults to ".dman".
        gitignore (bool, optional): Specifies whether files added to this mount point should be ignored.
    """
    if not is_storable(obj):
        raise ValueError("Can only store storable objects.")

    with context(
        key,
        subdir=subdir,
        cluster=cluster,
        generator=generator,
        base=base,
        verbose=verbose,
        gitignore=gitignore,
    ) as ctx:
        rec = record(obj, stem=key)
        with log.layer(key, "storing", prefix="key"):
            path = os.path.join(ctx.directory, rec.target)
            log.emphasize(
                f'storing {type(obj).__name__} with key {key} to "{path}".', "store"
            )
            ser = serialize(rec, context=ctx)
            log.emphasize(
                f'finished storing {type(obj).__name__} with key {key} to "{path}".',
                "store",
            )
            return ser


def save(
    key: str,
    obj,
    *,
    subdir: os.PathLike = "",
    cluster: bool = True,
    verbose: int = None,
    validate: bool = None,
    gitignore: bool = True,
    generator: str = MISSING,
    base: os.PathLike = None,
):
    """
    Save a serializable object to a file.
        The path of the file is determined as described below.

            If the files are clustered then the path is ``<base>/<generator>/<subdir>/<key>/<key>.<ext>``
            If cluster is set to False then the path is ``<base>/<generator>/<subdir>/<key>.<ext>``

            When base is not provided then it is set to .dman if
            it does not exist an exception is raised.

            When generator is not provided it will automatically be set based on
            the location of the script relative to the .dman folder
            (again raising an exception if it is not found). For example
            if the script is located in ``<project-root>/examples/folder/script.py``
            and .dman is located in ``<project-root>/.dman``.
            Then generator is set to cache/examples:folder:script (i.e.
            the / is replaced by : in the output).

    Args:
        key (str):  Key for the file.
        obj (Any): The serializable to save.
        subdir (os.PathLike, optional): Specifies optional subdirectory in generator folder. Defaults to "".
        cluster (bool, optional): A subfolder ``key`` is automatically created when set to True. Defaults to True.
        verbose (bool, optional): Level of verbosity. Defaults to False
        generator (str, optional): Specifies the generator that created the file. Defaults to script label.
        base (os.PathLike, optional): Specifies the root folder. Defaults to ".dman".
        gitignore (bool, optional): Specifies whether files added to this mount point should be ignored.
    """
    if not is_serializable(obj):
        raise ValueError("Can only save serializable objects.")

    with context(
        key,
        subdir=subdir,
        cluster=cluster,
        generator=generator,
        base=base,
        verbose=verbose,
        gitignore=gitignore,
    ) as ctx:
        with log.layer(key, "saving", prefix="key"):
            _, target = ctx.open(Target(stem=key, suffix='.json'))
            path = os.path.join(ctx.directory, target)
            log.emphasize(
                f'saving {type(obj).__name__} with key "{key}" to "{normalize_path(path)}".',
                "save",
            )
            ser = serialize(obj, context=ctx)
            with open(path, "w") as f:
                sjson.dump(ser, f, indent=4)
            log.emphasize(
                f'finished saving {type(obj).__name__} with key "{key}" to "{normalize_path(path)}".',
                "save",
            )
            return ser


def load(
    key: str,
    *,
    default=MISSING,
    default_factory=MISSING,
    subdir: os.PathLike = "",
    cluster: bool = True,
    verbose: int = None,
    gitignore: bool = True,
    generator: str = MISSING,
    base: os.PathLike = None,
):
    """
    Load a serializable or storable object from a file.
        A default value can be provided, which is returned when no file is found.
        Similarly default_factory is a function without arguments that
        is called instead of default. If both default and default_factory
        are specified then the value in default is returned.

        The path of the file is determined as described below.

            If the files are clustered then the path is ``<base>/<generator>/<subdir>/<key>/<key>.<ext>``
            If cluster is set to False then the path is ``<base>/<generator>/<subdir>/<key>.<ext>``

            When base is not provided then it is set to .dman if
            it does not exist an exception is raised.

            When generator is not provided it will automatically be set based on
            the location of the script relative to the .dman folder
            (again raising an exception if it is not found). For example
            if the script is located in ``<project-root>/examples/folder/script.py``
            and .dman is located in ``<project-root>/.dman``.
            Then generator is set to cache/examples:folder:script (i.e.
            the / is replaced by : in the output).

    Args:
        key (str):  Key for the file.
        default (Any, optional): The default value.
        default_factory (Callable, optional): Method with no argument that produces the default value.
        subdir (os.PathLike, optional): Specifies optional subdirectory in generator folder. Defaults to "".
        cluster (bool, optional): A subfolder ``key`` is automatically created when set to True. Defaults to True.
        verbose (bool, optional): Level of verbosity. Defaults to False
        generator (str, optional): Specifies the generator that created the file. Defaults to script label.
        base (os.PathLike, optional): Specifies the root folder. Defaults to ".dman".
        gitignore (bool, optional): Specifies whether files added to this mount point should be ignored.
    
    Returns:
        Loaded object or default value if file does not exist.
    """

    with context(
        key,
        subdir=subdir,
        cluster=cluster,
        generator=generator,
        base=base,
        verbose=verbose,
        gitignore=gitignore,
    ) as ctx:
        path = os.path.join(ctx.directory, key + ".json")
        with log.layer(key, "loading", prefix="key"):
            if not os.path.exists(path):
                log.emphasize(
                    f'file not available at "{normalize_path(path)}", using default',
                    "load",
                )
                if default is MISSING and default_factory is MISSING:
                    raise FileNotFoundError(
                        f'could not find tracked file "{normalize_path(path)}".'
                    )
                elif default is MISSING:
                    return default_factory()
                else:
                    return default

            log.emphasize(
                f'loading with key "{key}" from "{normalize_path(path)}".', "load"
            )
            with open(path, "r") as f:
                ser = sjson.load(f)
            res = deserialize(ser, context=ctx)
            log.emphasize(
                f'finished loading with key "{key}" from "{normalize_path(path)}".',
                "load",
            )
            return res


class Track:
    def __init__(
        self,
        key: str,
        default,
        default_factory,
        subdir: os.PathLike,
        cluster: bool,
        verbose: int,
        gitignore: bool,
        generator: str,
        base: os.PathLike,
    ) -> None:
        self.key = key
        self._content = None
        self.default = default
        self.default_factory = default_factory
        self.subdir = subdir
        self.cluster = cluster
        self.gitignore = gitignore
        self.generator = generator
        self.base = base
        self.verbose = verbose

    @property
    def content(self):
        if self._content is None:
            self.load()
        return self._content

    def save(self, unload: bool = False):
        save(
            self.key,
            self._content,
            subdir=self.subdir,
            gitignore=self.gitignore,
            generator=self.generator,
            base=self.base,
            cluster=self.cluster,
            verbose=self.verbose,
        )
        if unload:
            return self.load()

    def load(self):
        self._content = load(
            self.key,
            default=self.default,
            default_factory=self.default_factory,
            subdir=self.subdir,
            generator=self.generator,
            base=self.base,
            cluster=self.cluster,
            gitignore=self.gitignore,
            verbose=self.verbose,
        )
        return self._content

    def __enter__(self):
        return self.load()

    def __exit__(self, *_):
        return self.save()


def track(
    key: str,
    *,
    default=MISSING,
    default_factory=MISSING,
    subdir: os.PathLike = "",
    cluster: bool = True,
    verbose: int = None,
    gitignore: bool = True,
    generator: str = MISSING,
    base: os.PathLike = None,
):
    """
    Create track a serializable or storable object with a file.
        Ideally track is used as a context: i.e. ``with track(...) as obj: ...``.
        When the context is entered the object is loaded from a file
        (or default value is returned as described below). When the context
        exits, then the file is saved.

        If the object is storable, it will automatically be wrapped in a
        record before serialization.

        The path of the file is determined as described below.

            If the files are clustered then the path is ``<base>/<generator>/<subdir>/<key>/<key>.<ext>``
            If cluster is set to False then the path is ``<base>/<generator>/<subdir>/<key>.<ext>``

            When base is not provided then it is set to .dman if
            it does not exist an exception is raised.

            When generator is not provided it will automatically be set based on
            the location of the script relative to the .dman folder
            (again raising an exception if it is not found). For example
            if the script is located in ``<project-root>/examples/folder/script.py``
            and .dman is located in ``<project-root>/.dman``.
            Then generator is set to cache/examples:folder:script (i.e.
            the / is replaced by : in the output).

    Args:
        key (str):  Key for the file.
        default (Any, optional): The default value.
        default_factory (Callable, optional): Method with no argument that produces the default value.
        subdir (os.PathLike, optional): Specifies optional subdirectory in generator folder. Defaults to "".
        cluster (bool, optional): A subfolder ``key`` is automatically created when set to True. Defaults to True.
        verbose (bool, optional): Level of verbosity. Defaults to False
        generator (str, optional): Specifies the generator that created the file. Defaults to script label.
        base (os.PathLike, optional): Specifies the root folder. Defaults to ".dman".
        gitignore (bool, optional): Specifies whether files added to this mount point should be ignored.
    """
    return Track(
        key,
        default,
        default_factory,
        subdir,
        cluster,
        verbose,
        gitignore,
        generator,
        base,
    )


@storable(name="_log__filehandler")
class LogTarget(log.backend.FileHandler):
    __ext__ = ".log"

    def __init__(self, filename=None):
        if filename is None:
            self.tempdir = TemporaryDirectory()
            baseFilename = os.path.join(self.tempdir.name, f"log-{uuid4()}.log")
        else:
            self.tempdir = None
            baseFilename = filename
        super().__init__(baseFilename)

    def transfer(self, src: str, dst: str):
        with open(dst, "ab") as wfd:
            with open(src, "rb") as fd:
                shutil.copyfileobj(fd, wfd)

    def __write__(self, path: os.PathLike, context: Context):
        if os.path.abspath(self.baseFilename) == os.path.abspath(path):
            return

        log.info(
            f'switching\n\tfrom "{normalize_path(self.baseFilename)}"\n\tto   "{normalize_path(path)}".',
            "logtarget",
        )

        # close current stream
        super().close()

        # copy original log file (or move if temporary)
        if os.path.exists(self.baseFilename):
            if self.tempdir is not None:
                self.transfer(self.baseFilename, path)
                os.remove(self.baseFilename)
            else:
                self.transfer(self.baseFilename, path)

        # set stream to target file
        self.baseFilename = path
        self.setStream(open(self.baseFilename, "a", encoding=self.encoding))

        if self.tempdir is not None:
            self.tempdir.cleanup()

    def __remove__(self, context: Context):
        self.__init__()  # switch back to temporary file
        log.info(
            f"switching back to temporary file {normalize_path(self.baseFilename)}.",
            "logtarget",
        )

    @classmethod
    def __read__(cls, path: os.PathLike):
        return cls(path)


log.LogTarget = LogTarget
