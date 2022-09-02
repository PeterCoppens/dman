from contextlib import suppress
from dataclasses import MISSING
from pathlib import Path
import os, sys

from dman.core import log

ROOT_FOLDER = '.dman'


class RootError(RuntimeError):
    ...


def get_root_path(create: bool = False):
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
                    log.io(f'no .dman folder found, created one in {cwd}', 'path')
                    root_path = os.path.join(cwd, ROOT_FOLDER)
                    os.makedirs(root_path)
                    return root_path
                raise RootError(
                    'no .dman folder found. Consider running $dman init')

    return str(root_path)


def script_label(base: os.PathLike):
    if base is None:
        base = get_root_path()
    try:
        script = sys.argv[0]
        if len(script) == 0:
            return os.path.join('cache', '__interpreter__')
        script = Path(script)\
            .resolve()\
            .relative_to(Path(base).parent)
    except ValueError:
        return Path(sys.argv[0]).stem
    except TypeError:
        return os.path.join('cache', '__interpreter__')

    directory = str(script.parent)
    name = str(script.stem)

    return os.path.join('cache', f'{directory.replace(os.sep, ":")}:{name}')


class Directory:
    def __init__(self, path: str, clean: bool = False):
        self.path = path
        self.clean = clean

    def __enter__(self):
        if os.path.exists(self.path):
            return
        log.io(f'created directory {log.path(self.path)}.', 'path')
        os.makedirs(self.path)
        self.clean = True
    
    def __exit__(self, *_):
        if self.clean and len(os.listdir(self.path)) == 0:
            os.rmdir(self.path)
            log.io(f'removed empty directory {log.path(self.path)}.', 'path')


class GitIgnore:
    def __init__(self, directory: str, ignored: set = None, clean: bool = False, check_exists: bool = False):
        self.directory = directory
        self.path = os.path.join(directory, '.gitignore')
        self.ignored = set() if ignored is None else set()
        original = ['.gitignore']
        if os.path.exists(self.path):
            with open(self.path, 'r') as f:
                for line in f.readlines():
                    if len(line) > 0 and line[-1] == '\n':
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
        with open(self.path, 'w') as f:
            for line in ignored:
                f.write(line + '\n')
        log.io(f'created gitignore at {log.path(self.path)}.', 'path')

    def __exit__(self, *_):
        if not self.check_exists:
            with Directory(self.directory):
                self.build(self.ignored)
                return

        ignored = []
        for line in self.ignored:
            if line == '.gitignore':
                ignored.append(line)
            if os.path.exists(os.path.join(self.directory, line)):
                ignored.append(line)
        if len(ignored) <= 1 and not os.path.exists(self.directory):
            return

        with Directory(self.directory, self.clean):
            if len(ignored) <= 1:
                # clean up if we do not need to ignore anything
                if os.path.exists(self.path):
                    os.remove(self.path)
                    log.io(f'removed empty gitignore {log.path(self.path)}.', 'path')
                return
            self.build(ignored)


def add_gitignore(dir: str, file: str, *, clean: bool = False, check_exists: bool = True):
    with GitIgnore(dir, clean=clean, check_exists=check_exists) as git:
        git.append(file)


def get_directory(key: str, *, subdir: os.PathLike = '', cluster: bool = False, generator: str = MISSING, base: os.PathLike = None):
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

    :returns str: The directory where the file is stored by dman.
    """    
    base = get_root_path() if base is None else base
    if generator is None:
        generator = ''
    if generator is MISSING:
        generator = script_label(os.path.abspath(base))
    res = os.path.join(base, generator, subdir)
    if cluster:
        return os.path.join(res, key)
    return res 


def prepare(key: str, *, suffix: str = '.json', subdir: os.PathLike = '', cluster: bool = False, verbose: int = None, gitignore: bool = True, generator: str = MISSING, base: os.PathLike = None):    
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
    :param int verbose: Level of verbosity (1 == print log).
    :param bool gitignore: Automatically adds a .gitignore file to ignore the created object when set to True.
    :param str generator: Specifies the generator that created the file. 
    :param str base: Specifies the root folder (.dman by default).

    :returns str: The directory where files are stored by dman.
    """    
    dir = get_directory(key, subdir=subdir, cluster=cluster, generator=generator, base=base)
    
    # create directory
    created_dir = not os.path.exists(dir)
    if created_dir:
        os.makedirs(dir)

    # configure logger
    if verbose is None or verbose <= 0:
        verbose = log.NOTSET
    logger = log.get_logger(level=verbose)
    log_dir = None
    if logger._target is log.Target.ROOT:
        log_dir = get_root_path()
        log.setFile(os.path.join(log_dir, 'log.ansi'))
    if logger._target is log.Target.AUTO:
        log_dir = dir
        log.setFile(os.path.join(log_dir, 'log.ansi'))
    
    # log the creation of the directory
    if created_dir:
        log.io(f'created directory {log.path(dir)}.', 'path')

    # create gitignore
    if gitignore:
        add_gitignore(dir, f'{key}{suffix}', check_exists=False)
        if log_dir:
            add_gitignore(log_dir, 'log.ansi', check_exists=False)

    return dir


if __name__ == '__main__':
    log.setLevel(log.INFO)
    with log.layer('test', 'git'):
        with GitIgnore('tmp', clean=True) as git:
            git.append('tmp.txt')
    
    print(get_directory('key'))
    print(get_directory('key', cluster=True))
    print(get_directory('key', generator='generator'))
    print(get_directory('key', subdir='subdir'))
    print(get_directory('key', subdir='subdir', base='./base'))

    log.setFile(log.Target.AUTO, exclusive=True)
    log.info('lost')
    dir = prepare('key', subdir='subdir', base='./base')
    log.info(dir)
    log.unsetFile()
    log.setStream()
    log.info('test')
