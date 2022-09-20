from contextlib import suppress
from dataclasses import MISSING
from logging import getLogger
from pathlib import Path
import os, sys

from dman.core import log

ROOT_FOLDER = ".dman"


class RootError(RuntimeError):
    ...


def get_root_path(create: bool = False, *, logger: log.Logger = None):
    logger = getLogger(logger)
    root_path = None
    cwd = Path.cwd()

    current_path = cwd
    while root_path is None:
        if current_path.joinpath(ROOT_FOLDER).is_dir():
            root_path = current_path.joinpath(ROOT_FOLDER)
        else:
            current_path = current_path.parent
            if current_path.parent == current_path:
                if create:
                    logger.io(f"no .dman folder found, created one in {normalize_path(cwd)}", "path")
                    root_path = os.path.join(cwd, ROOT_FOLDER)
                    os.makedirs(root_path)
                    return root_path
                raise RootError("no .dman folder found. Consider running $dman init")

    return str(root_path)


def script_label(base: os.PathLike):
    if base is None:
        base = get_root_path()
    try:
        script = sys.argv[0]
        if len(script) == 0:
            return os.path.join("cache", "__interpreter__")
        script = Path(script).resolve().relative_to(Path(base).parent)
    except ValueError:
        return Path(sys.argv[0]).stem
    except TypeError:
        return os.path.join("cache", "__interpreter__")

    directory = str(script.parent)
    name = str(script.stem)

    return os.path.join("cache", f'{directory.replace(os.sep, ":")}:{name}')


def normalize_path(path: str):
    try:
        root = Path(os.getcwd())
        # root = Path(get_root_path()).parent
        return os.path.join(
            '.',
            str(Path(path).resolve().relative_to(root))
        )
    except RootError:
        return path
    except ValueError:
        return path


class Directory:
    def __init__(self, path: str, clean: bool = False, logger: log.Logger = None):
        self.logger = log.getLogger(logger)
        self.path = path
        self.clean = clean

    def __enter__(self):
        if os.path.exists(self.path):
            return
        self.logger.io(f"created directory {normalize_path(self.path)}.", "path")
        os.makedirs(self.path)
        self.clean = True

    def __exit__(self, *_):
        if self.clean and len(os.listdir(self.path)) == 0:
            os.rmdir(self.path)
            self.logger.io(f"removed empty directory {normalize_path(self.path)}.", "path")


class GitIgnore:
    def __init__(
        self,
        directory: str,
        ignored: set = None,
        clean: bool = False,
        check_exists: bool = False,
        logger: log.Logger = None,
    ):
        self.logger = log.getLogger(logger)
        self.directory = directory
        self.path = os.path.join(directory, ".gitignore")
        self.ignored = set() if ignored is None else set()
        original = [".gitignore"]
        if os.path.exists(self.path):
            with open(self.path, "r") as f:
                for line in f.readlines():
                    if len(line) > 0 and line[-1] == "\n":
                        line = line[:-1]
                    original.append(line)
        self.ignored = set.union(set(original), self.ignored)
        self.clean = clean
        self.check_exists = check_exists

    def normalize(self, file):
        file = os.path.join(self.directory, file)
        return os.path.relpath(file, start=self.directory)

    def append(self, file: str):
        self.ignored.add(self.normalize(file))

    def remove(self, file: str):
        with suppress(KeyError):
            self.ignored.remove(self.normalize(file))

    def __enter__(self):
        return self

    def build(self, ignored: list):
        with open(self.path, "w") as f:
            for i, line in enumerate(ignored):
                if i < len(ignored) - 1:
                    f.write(line + "\n")
                else:
                    f.write(line)

        self.logger.io(f'created gitignore at "{normalize_path(self.path)}".', "path")

    def __exit__(self, *_):
        if not self.check_exists:
            with Directory(self.directory, logger=self.logger):
                self.build(self.ignored)
                return

        ignored = []
        for line in self.ignored:
            if line == ".gitignore":
                ignored.append(line)
            if os.path.exists(os.path.join(self.directory, line)):
                ignored.append(line)
        if len(ignored) <= 1 and not os.path.exists(self.directory):
            return

        with Directory(self.directory, self.clean, self.logger):
            if len(ignored) <= 1:
                # clean up if we do not need to ignore anything
                if os.path.exists(self.path):
                    os.remove(self.path)
                    self.logger.io(
                        f"removed empty gitignore {normalize_path(self.path)}.", "path"
                    )
                return
            self.build(ignored)


def add_gitignore(
    dir: str, file: str, *, clean: bool = False, check_exists: bool = True
):
    with GitIgnore(dir, clean=clean, check_exists=check_exists) as git:
        git.append(file)


def get_directory(
    key: str,
    *,
    subdir: os.PathLike = "",
    cluster: bool = True,
    generator: str = MISSING,
    base: os.PathLike = None,
    logger: log.Logger = None,
):
    """
    Get the directory where a file with the given key is stored by dman.
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

    :param str key: Key for the file.
    :param str obj: The serializable object.
    :param bool subdir: Specifies optional subdirectory in generator folder
    :param bool cluster: A subfolder ``key`` is automatically created when set to True.
    :param int verbose: Level of verbosity (1 == print log).
    :param bool gitignore: Automatically adds a .gitignore file to ignore the created object when set to True.
    :param str generator: Specifies the generator that created the file.
    :param str base: Specifies the root folder (.dman by default).
    :param Logger logger: Specifies the logger.

    :returns str: The directory where the file is stored by dman.
    """
    base = get_root_path(logger) if base is None else base
    if generator is None:
        generator = ""
    if generator is MISSING:
        generator = script_label(os.path.abspath(base))
    res = os.path.join(base, generator, subdir)
    if cluster:
        return os.path.join(res, key)
    return res


def prepare(
    key: str,
    *,
    suffix: str = ".json",
    subdir: os.PathLike = "",
    cluster: bool = True,
    verbose: int = None,
    gitignore: bool = True,
    generator: str = MISSING,
    base: os.PathLike = None,
    logger: log.Logger = None,
):
    """
    Prepare directory and log for dman file access.
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

    :param str key: Key for the file.
    :param str obj: The serializable object.
    :param bool subdir: Specifies optional subdirectory in generator folder
    :param bool cluster: A subfolder ``key`` is automatically created when set to True.
    :param int verbose: Specify log level (False == WARNING, True == INFO).
    :param bool gitignore: Automatically adds a .gitignore file to ignore the created object when set to True.
    :param str generator: Specifies the generator that created the file.
    :param str base: Specifies the root folder (.dman by default).
    :param Logger logger: Logger used for io reporting.

    :returns str: The directory where files are stored by dman.
    """
    # load the logger
    logger = log.getLogger(logger, level=verbose)

    # get the directory
    dir = get_directory(
        key,
        subdir=subdir,
        cluster=cluster,
        generator=generator,
        base=base,
        logger=logger,
    )

    # create directory
    created_dir = not os.path.exists(dir)
    if created_dir:
        os.makedirs(dir)
        logger.io(f"created directory {normalize_path(dir)}.", "path")

    # configure logger
    if verbose == False:
        verbose = log.WARNING
    elif verbose == True:
        verbose = log.INFO

    # log the creation of the directory
    if created_dir:
        log.io(f"created directory {normalize_path(dir)}.", "path")

    # create gitignore
    if gitignore:
        if cluster:
            add_gitignore(os.path.dirname(dir), dir, check_exists=False)
        else:
            add_gitignore(dir, f"{key}{suffix}", check_exists=False)

    return dir
