"""
Contains path handling systems used internally by ``dman``.
"""


from contextlib import contextmanager, suppress
from pathlib import Path
import os, sys
from typing import Iterable

from dman.core import log
from dman.utils.smartdataclasses import configclass, optionfield
from dman.utils.regex import substitute
from dman.utils.user import prompt_user

ROOT_FOLDER = ".dman"


@configclass
class Config:
    """Configuration class for path handling.

        This class has a global instance that can be accessed as follows:

        >>> dman.core.path.config.on_retouch = 'prompt'
        >>> dman.params.store.on_retouch = 'prompt'  # equivalent

    Args:
        on_retouch (str, optional): Procedure handling re-used file names. 
            Options are ``'prompt'``, ``'quit'``, ``'ignore'``, ``'auto'``.
            Defaults to ``'ignore'``. 
        default_suffix (str, optional): Default suffix used for files when none is specified.
            Defaults to ``'.sto'``.
    """
    on_retouch: str = optionfield(
        ["prompt", "quit", "ignore", "auto"], default="ignore"
    )
    default_suffix: str = '.sto'


config = Config()


class _Auto: ...
AUTO = _Auto()


class RootError(RuntimeError):
    """Raised when no ``.dman`` directory could be found."""
    ...


def get_root_path(create: bool = False, *, cwd: os.PathLike = None):
    root_path = None
    cwd = Path.cwd() if cwd is None else Path(cwd)

    current_path = cwd
    while root_path is None:
        if current_path.joinpath(ROOT_FOLDER).is_dir():
            root_path = current_path.joinpath(ROOT_FOLDER)
        else:
            current_path = current_path.parent
            if current_path.parent == current_path:
                if create:
                    log.io(
                        f"no .dman folder found, created one in {normalize_path(cwd)}",
                        "path",
                    )
                    root_path = os.path.join(cwd, ROOT_FOLDER)
                    os.makedirs(root_path)
                    return root_path
                raise RootError("no .dman folder found. Consider running $dman init")

    return str(root_path)


def script_label(base: os.PathLike = None):
    """Generate a label for the current executing script. 

        Takes the path relative to the folder containing ``.dman`` and 
        replaces the separators with ``:``."""
    if base is None:
        base = get_root_path()
    base = Path(base).parent
    try:
        script = sys.argv[0]
        if len(script) == 0:
            return "__interpreter__"
        script = Path(script).resolve().relative_to(base)
    except ValueError:
        return Path(sys.argv[0]).stem
    except TypeError:
        return "__interpreter__"

    directory = str(script.parent)
    name = str(script.stem)
    return f'{directory.replace(os.sep, ":")}:{name}'


def normalize_path(path: str):
    """Simplify path string relative to folder containing 
        ``.dman`` to be used for printing."""
    try:
        # root = Path(os.getcwd())
        root = Path(get_root_path()).parent
        return str(Path(path).resolve().relative_to(root))
    except RootError:
        return path
    except ValueError:
        return path


class TargetException(Exception):
    """Raised when an invalid target file is encountered."""
    ...


class Target(os.PathLike):
    """Object representing file relative to current folder."""

    def __init__(
        self,
        stem: str = AUTO,
        suffix: str = AUTO,
        subdir: os.PathLike = '',
        name: str = AUTO,
    ):
        """Get a target path used for relative file definitions.
            ``<subdir>/<stem>.<suffix>`` or ``<subdir>/<name>``

        Raises:
            ValueError: Both name and suffix or stem were provided.
        """
        if name is not AUTO and (stem is not AUTO or suffix is not AUTO):
            raise ValueError("Either provide a name or suffix + stem.")
        if name is not AUTO:
            stem, suffix = os.path.splitext(name)
        self.subdir, self.stem, self.suffix = subdir, stem, suffix

    @property
    def name(self):
        """Name of the file"""
        return self.stem + self.suffix

    @classmethod
    def from_path(cls, path: os.PathLike):
        """Create a target from a relative path."""
        subdir, name = os.path.split(path)
        return cls(subdir=subdir, name=name)

    @classmethod
    def from_tuple(cls, t):
        """Create a target from a tuple (subdir, stem, suffix)."""
        return cls(t[1], t[2], t[0])

    def __iter__(self):
        yield from (self.subdir, self.stem, self.suffix)

    def __repr__(self):
        if self.is_complete():
            return self.__fspath__()
        return f"target{tuple(self)}"

    def __fspath__(self):
        """Return the file system path representation of the object."""
        if self.is_complete():
            return os.path.join(self.subdir, self.name)
        raise TargetException(f'Tried to process incomplete target "{self}".')
    
    def __hash__(self):
        if not self.is_complete():
            return tuple(self).__hash__()
        return os.path.normpath(self).__hash__()

    def __eq__(self, other):
        return self.__hash__() == other.__hash__()

    def is_complete(self):
        """Is the target completely specified."""
        return AUTO not in self

    def merge(self, *args):
        """Merge target with others.
        
        Example:
            >>> Target(name='test.json').merge(Target(suffix='.obj'), Target(subdir='folder'))
            folder/test.obj
            >>> Target(name='test.json').merge(Target(subdir='folder'), Target(suffix='.obj'))
            test.obj
            >>> Target(name='test.json').merge(Target(subdir='folder'), Target(suffix='.obj', subdir=AUTO))
            folder/test.obj
        """
        if len(args) == 0:
            return self
        t = tuple(v if _v is AUTO else _v for v, _v in zip(self, args[0]))
        return Target.from_tuple(t).merge(*args[1:])

    def update(
        self,
        stem: str = AUTO,
        suffix: str = AUTO,
        subdir: os.PathLike = AUTO,
        name: str = AUTO,
    ):
        """Update parts of target.
            See also :func:`merge`.
        """
        return self.merge(Target(stem, suffix, subdir, name))


def target(stem: str = AUTO, suffix: str = AUTO, name: str = AUTO, subdir: str = ""):
    """Get a target path used for relative file definitions.
        ``<subdir>/<stem>.<suffix>`` or ``<subdir>/<name>``

    Raises:
        ValueError: Both name and suffix or stem were provided.
    """
    return Target(stem, suffix, subdir, name)


def gitignore(directory: os.PathLike, ignored: Iterable, *, check: Iterable = None):
    """Add ignored files to gitignore in provided directory.

    Args:
        directory (os.PathLike): Directory to add ``.gitignore`` file to.
        ignored (Iterable): Files to add to current ``.gitignore``.
        check (Iterable, optional): Check whether these files still exists. If not, don't add them.
    """
    if check is None: check = []
    path = os.path.join(directory, ".gitignore")
    original = {}
    if os.path.exists(path):
        with open(path, "r") as f:
            original = set(f.read().splitlines())
            original = set((
                p for p in original 
                if p not in check or os.path.exists(os.path.join(directory, p))
            ))
    ignored = set(ignored).union(original)
    ignored.add('.gitignore')
    if len(ignored) == 1:
        os.remove(path)
    else:
        with open(path, "w") as f:
            f.write("\n".join(sorted(ignored)))


def prune_directories(directory: os.PathLike, *, root=True):
    """Prune all empty directories contained within this one."""
    if not os.path.exists(directory):
        return False   # no need to keep parent
    if not os.path.isdir(directory):
        return True  # found file, keep this directory

    keep = False
    for f in os.listdir(directory):
        if prune_directories(os.path.join(directory, f), root=False):
            keep = True
    if keep:
        return True
    if not root:
        os.rmdir(directory)  # was able to prune all subdirectories.
    return False  # no need to keep parent


class UserQuitException(TargetException):
    """Raised when a file was re-used by a mount point and the quit option was selected."""
    ...


class MountException(TargetException):
    """Raised when a file is accessed outside of a mount point."""
    ...



class Mount(os.PathLike):
    """Mount point used as start of file hierarchy."""

    def __init__(
        self,
        directory: os.PathLike,
        cluster: bool = False,
        gitignore: bool = True,
    ):
        """Construct a mount point at the specified directory."""
        self.directory = directory
        self.cluster = cluster
        self.gitignore = gitignore
        self.touched = []
        self.removed = []

    def __repr__(self):
        return self.__fspath__()

    def __fspath__(self):
        """Return the file system path representation of the object."""
        return self.directory
    
    def __hash__(self):
        return os.path.normpath(self).__hash__()

    def __eq__(self, other):
        return self.__hash__() == other.__hash__()

    def contains(self, path: os.PathLike):
        """Is the specified path contained within this mount point."""
        return os.path.commonpath([self]) == os.path.commonpath(
            [self, os.path.abspath(path)]
        )

    def abspath(self, path: os.PathLike, *, validate=False):
        """Get the absolute path

        Raises:
            ValueError: The path is not contained within this FileSystem.
        """
        # Get absolute path.
        path = os.path.join(self, path)

        # Check if absolute path is contained within the controlled directory.
        if validate and not self.contains(path):
            raise MountException(
                (
                    f'Tried to access path "{self}". The specified'
                    f'"{path}" is not contained within this mount point.'
                )
            )

        # Return result.
        return path

    def normalize(self, path: os.PathLike, *, validate: bool = False):
        """Construct a target based on the path relative to this mount point."""
        path = os.path.relpath(self.abspath(path, validate=validate), start=self)
        return Target.from_path(path)

    def default(self, target: Target):
        """Get default suggestion for target."""
        if target not in self.touched:
            return target

        base, matches = substitute(r"[0-9]+\b", "", target.stem)
        if len(matches) == 0:
            base = f"{base}0"
        else:
            base = f"{base}{int(matches[0].group(0))+1}"
        return self.default(target.update(name=f"{base}{target.suffix}"))

    def register(self, target: Target, *, choice: str = None):
        """Register a target in the mount point. 
        
            It avoids registering a target multiple times. 
            The behavior is determined by ``config.on_retouch`` or the value in `choice`.

            - ``'prompt'``: Prompt the user for a different file name.
            - ``'quit'``: Raise a :class:`UserQuitException`.
            - ``'ignore'``: Override the existing file.
            - ``'auto'``: Add an index to the file name to make it unique.
        """
        # If the target is not registered we can do so and return it.
        if target not in self.touched:
            self.touched.append(target)
            return target

        # Otherwise we should find an alternative.
        # First get the default target and choice.
        default = self.default(target)
        choice = config.on_retouch if choice is None else choice

        # If the choice is "prompt" then we request input from the user.
        if choice == "prompt":
            choice = prompt_user(
                (
                    f"Tried to write to same target twice: {target}.\n"
                    "Specify alternative filename.\n"
                    '    Enter "q" to cancel serialization and "x" to ignore'
                ),
                default=default,
            )

        # If the choice is "auto" (or the same as default) then write to the default
        if choice == default or choice == "auto":
            return self.register(target.update(name=default.name), choice="auto")

        # If the choice is "quit" then we raise a SerializationError,
        # which will cancel serialization.
        if choice in ("q", "quit"):
            raise UserQuitException(
                (
                    f'Attempted to write to target "{target}" twice during serialization.'
                    "Operation exited by user."
                )
            )

        # If the choice is "ignore" then the file is overwritten.
        if choice in ("x", "ignore", "_ignore"):
            if choice != "_ignore":
                log.warning(
                    f'Overwritten previously stored object at target "{target}".',
                    "fs",
                )
            return target
        # We reach this option if a custom file name was provided by the user.
        return self.register(target.update(name=choice), choice="prompt")

    def prepare(self, target: os.PathLike, *, validate: bool = True, choice: str = None):
        """Prepare directory to write to target path."""
        # Normalize the path relative to this mount point.
        target = self.normalize(target, validate=validate)

        # Register the target
        target = self.register(target, choice=choice)

        # Create the required directories
        directory = os.path.join(self, target.subdir)
        if not os.path.isdir(directory):
            log.io(f'Creating empty directory "{normalize_path(directory)}".', "mount")
            os.makedirs(directory)

        # Return the target
        return target

    def close(self):
        """Close this mount point. 
        
            Empty subdirectories are deleted and a gitignore is created if 
            requested on creation.
        """
        prune_directories(self)
        if not self.gitignore:
            return
        ignored = {str(f) for f in self.touched if os.path.exists(self.abspath(f))}
        if len(ignored) == 0:
            return
        if self.cluster:
            directory, name = os.path.split(self)
            gitignore(directory, (name,), check=self.removed)
        else:
            gitignore(self, ignored, check=self.removed)
    
    @contextmanager
    def open(self, path: os.PathLike, *args, **kwargs):
        """Open a file, registered by this mount point.
        
            The signature is identical to the standard ``open`` command.
        """
        path = self.prepare(path, validate=True)
        f = open(self.abspath(path), *args, **kwargs)
        yield f
        f.close()
    
    def untrack(self, target: os.PathLike, *, validate: bool = False):
        """Untrack a registered file. Afterwards it can be overridden without issues."""
        with suppress(ValueError):
            path = self.normalize(target, validate=validate)
            self.touched.remove(path)
            self.removed.append(path)

    def remove(self, target: os.PathLike, *, validate: bool = True):
        """Delete a file from the mount point and stop tracking it."""
        self.untrack(target, validate=validate)
        path = self.abspath(target)
        if os.path.isdir(path) and len(os.listdir(path)) == 0:
            os.rmdir(path)
        elif os.path.exists(path):
            os.remove(path)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def mount(
    key: str = '',
    *,
    subdir: os.PathLike = "",
    cluster: bool = True,
    generator: str = None,
    base: os.PathLike = None,
    gitignore: bool = True,
):
    """Get the mount point where a file with the given key is stored by dman.
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
        
            See :ref:`sphx_glr_gallery_fundamentals_example4_path.py` for
            detailed examples on how to create and use mount points.

    Args:
        key (str, optional):  Key for the file. Default ``''``, so the generator folder is returned.
        subdir (os.PathLike, optional): Specifies optional subdirectory in generator folder. Defaults to "".
        cluster (bool, optional): A subfolder ``key`` is automatically created when set to True. Defaults to True.
        generator (str, optional): Specifies the generator that created the file. Defaults to script label.
        base (os.PathLike, optional): Specifies the root folder. Defaults to ".dman".
        gitignore (bool, optional): Specifies whether files added to this mount point should be ignored.
    """
    base = get_root_path() if base is None else base
    if generator is None:
        generator = os.path.join("cache", script_label(os.path.abspath(base)))
    if cluster:
        subdir = os.path.join(subdir, key)
    directory = os.path.join(base, generator, subdir)
    return Mount(directory, cluster=cluster, gitignore=gitignore)
