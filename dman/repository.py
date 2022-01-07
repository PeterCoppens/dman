from dataclasses import MISSING, dataclass, field
import os
from pathlib import Path
import sys
from contextlib import suppress
from typing import Union

from dman.persistent.record import Context, record
from dman.persistent.serializables import deserialize, is_serializable, serialize
from dman.persistent.storables import is_storable
from dman.utils import sjson

ROOT_FOLDER = '.dman'


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
                    print(f'no .dman folder found, created one in {cwd}')
                    root_path = os.path.join(cwd, ROOT_FOLDER)
                    os.makedirs(root_path)
                    return root_path
                raise RuntimeError('no .dman folder found. Consider running $dman init')

    return str(root_path)


def script_label(base: os.PathLike):
    if base is None:
        base = get_root_path()
    try:
        script = Path(sys.argv[0])\
            .resolve()\
            .relative_to(Path(base).parent)
    except ValueError:
        return Path(sys.argv[0]).stem
    except TypeError:
        return os.path.join('cache', '__interpreter__')

    directory = str(script.parent)
    name = str(script.stem)

    return os.path.join('cache', f'{directory.replace(os.sep, ":")}:{name}')


@dataclass
class GitIgnore:
    context: Context
    ignored: set = field(default_factory=set)

    def __post_init__(self):
        original = ['.gitignore']
        if os.path.exists(self.path):
            with open(self.path, 'r') as f:
                for line in f.readlines():
                    if len(line) > 0 and line[-1] == '\n':
                        line = line[:-1]
                    original.append(line)
        self.ignored = set.union(set(original), self.ignored)

    @property
    def path(self):
        return os.path.join(self.context.path, '.gitignore')

    def normalize(self, file):
        return os.path.relpath(file, start=self.context.path)

    def append(self, file: str):
        self.ignored.add(self.normalize(file))

    def remove(self, file: str):
        with suppress(KeyError):
            self.ignored.remove(self.normalize(file))
    
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if len(self.ignored) == 1:
            # clean up if we do not need to ignore anything
            if os.path.exists(self.path):
                os.remove(self.path)
                self.context.clean()
        else:
            added = 0
            self.context.open()
            with open(self.path, 'w') as f:
                for line in self.ignored:
                    if os.path.exists(os.path.join(self.context.path, line)):
                        f.write(line + '\n')
                        added += 1
            if added == 1:
                os.remove(self.path)
                self.context.clean()


class Repository:
    def __init__(self, context: Context, git: GitIgnore = None) -> None:
        self.context: Context = context
        if git is None:
            git = GitIgnore(context)
        self.git = git
    
    def join(self, other: os.PathLike):
        return Repository(self.context.join(other), git=self.git)
    
    def process(self, file, gitignore):
        file = os.path.join(self.context.path, file)
        if gitignore:
            self.git.append(file)
        else:
            self.git.remove(file)
    
    def __enter__(self):
        self.git.__enter__()
        return self.context
        
    def __exit__(self, exc_type = None, exc_val = None, exc_tb = None):
        self.git.__exit__(exc_type, exc_val, exc_tb)


def repository(*, name: str = '', subdir: str = '', generator: str = MISSING, base: os.PathLike = None, gitignore: Union[dict, bool] = False):
    if base is None:
        base = get_root_path()
    ctx = Context(base)

    if generator is None:
        return Repository(context=ctx)

    if generator is MISSING:
        generator = script_label(base)
    
    generator = os.path.join(generator, subdir)
    target = os.path.join(generator, name)
    if isinstance(gitignore, bool):
        if target == generator:
            name = generator
        else:
            ctx = ctx.join(generator)

        repo = Repository(context=ctx)
        repo.process(name, gitignore)
        return repo.join(name)
    else:
        gitignore: dict = gitignore
        ctx = ctx.join(generator).join(name)
        repo = Repository(context=ctx)
        for path, add in gitignore.items():
            repo.process(path, add)
        return repo
  

def save(key: str, obj, *, subdir: os.PathLike = '', cluster: bool = True, gitignore: bool = True, generator: str = MISSING, base: os.PathLike = None):
    """
    Save a serializable or storable object to a file.
        If the object is storable, it will automatically be wrapped in a 
        record before serialization. 

        The path of the file is determined as described below.

            If the files are clustered then the path is ``<base>/<generator>/<subdir>/<key>/<key>.json``
            If cluster is set to False then the path is ``<base>/<generator>/<subdir>/<key>.json``

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
    :param str obj: The serializable or storable object.
    :param bool subdir: Specifies optional subdirectory in generator folder
    :param bool cluster: A subfolder ``key`` is automatically created when set to True.
    :param bool gitignore: Automatically adds a .gitignore file to ignore the created object when set to True.
    :param str generator: Specifies the generator that created the file. 
    :param str base: Specifies the root folder (.dman by default).

    :raises RuntimeError: if either generator or base is not provided and no .dman folder exists.
    """
    if is_storable(obj):
        obj = record(obj)
    
    if not is_serializable(obj):
        raise ValueError('can only save storable or serializable objects')

    if generator is MISSING:
        generator = script_label(base)

    filename = f'{key}.json'
    name = key
    if not cluster:
        name = ''
        gitignore = {filename: gitignore}

    with repository(name=name, subdir=subdir, generator=generator, base=base, gitignore=gitignore) as repo:
        ser = serialize(obj, repo)
        target = repo.join(filename).touch()
        with open(target.path, 'w') as f:
            sjson.dump(ser, f, indent=4)


def load(key: str, *, default=MISSING, default_factory=MISSING, subdir: os.PathLike = '', cluster: bool = True, gitignore: bool = True, generator: str = MISSING, base: os.PathLike = None):
    """
    Load a serializable or storable object from a file.
        A default value can be provided, which is returned when no file is found.
        Similarly default_factory is a function without arguments that 
        is called instead of default. If both default and default_factory
        are specified then the value in default is returned.

        The path of the file is determined as described below.

            If the files are clustered then the path is ``<base>/<generator>/<subdir>/<key>/<key>.json``
            If cluster is set to False then the path is ``<base>/<generator>/<subdir>/<key>.json``

            When base is not provided then it is set to .dman if 
            it does not exist an exception is raised.

            When generator is not provided it will automatically be set based on 
            the location of the script relative to the .dman folder
            (again raising an exception if it is not found). For example
            if the script is located in ``<project-root>/examples/folder/script.py``
            and .dman is located in ``<project-root>/.dman``.
            Then generator is set to cache/examples:folder:script (i.e.
            the / is replaced by : in the output).

        If the object is storable, it will automatically be wrapped in a 
        record before serialization. 

    :param str key: Key for the file.
    :param default: Default value.
    :param default_factory: Method with no argument that produces the default value.
    :param bool subdir: Specifies optional subdirectory in generator folder
    :param bool cluster: A subfolder ``key`` is automatically created when set to True.
    :param bool gitignore: Automatically adds a .gitignore file to ignore the created object when set to True.
    :param str generator: Specifies the generator that created the file. 
    :param str base: Specifies the root folder (.dman by default).

    :returns: Loaded object or default value if file does not exist.

    :raises RuntimeError: if either generator or base is not provided and no .dman folder exists.
    """
    if generator is MISSING:
        generator = script_label(base)

    filename = f'{key}.json'
    name = key
    if not cluster:
        name = ''
        gitignore = {filename: gitignore}

    with repository(name=name, subdir=subdir, generator=generator, base=base, gitignore=gitignore) as repo:
        target = repo.join(f'{key}.json')
        if not os.path.exists(target.path):
            if default is MISSING and default_factory is MISSING:
                raise FileNotFoundError(f'could not find tracked file {target.path}')
            elif default is MISSING:
                return default_factory()
            else:
                return default
        with open(target.path, 'r') as f:
            ser = sjson.load(f)
            return deserialize(ser, repo)


class Track:
    def __init__(self, key: str, default, default_factory, subdir: os.PathLike, cluster: bool, gitignore: bool, generator: str, base: os.PathLike) -> None:
        self.key = key
        self._content = None
        self.default = default
        self.default_factory = default_factory
        self.subdir = subdir
        self.cluster = cluster
        self.gitignore = gitignore
        self.generator = generator
        self.base = base

    @property
    def content(self):
        if self._content is None: self.load()
        return self._content

    def save(self, unload: bool = False):
        save(self.key, self._content, subdir=self.subdir, gitignore=self.gitignore,
                generator=self.generator, base=self.base, cluster=self.cluster)
        if unload: self.load()
    
    def load(self):
        self._content = load(self.key, default=self.default, 
            default_factory=self.default_factory, subdir=self.subdir, 
            generator=self.generator, base=self.base, cluster=self.cluster, 
            gitignore=self.gitignore)
        return self._content

    def __enter__(self):
        return self.load()
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        return self.save()


def track(key: str, *, default = MISSING, default_factory = MISSING, subdir: os.PathLike = '', cluster: bool = True, gitignore: bool = True, generator: str = MISSING, base: os.PathLike = None):
    """
        Create track a serializable or storable object with a file.
            Ideally track is used as a context: i.e. ``with track(...) as obj: ...``.
            When the context is entered the object is loaded from a file 
            (or default value is returned as described below). When the context
            exits, then the file is saved.

            If the object is storable, it will automatically be wrapped in a 
            record before serialization. 

            The path of the file is determined as described below.

                If the files are clustered then the path is ``<base>/<generator>/<subdir>/<key>/<key>.json``
                If cluster is set to False then the path is ``<base>/<generator>/<subdir>/<key>.json``

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
        :param default: Default value.
        :param default_factory: Method with no argument that produces the default value.
        :param bool subdir: Specifies optional subdirectory in generator folder
        :param bool cluster: A subfolder ``key`` is automatically created when set to True.
        :param bool gitignore: Automatically adds a .gitignore file to ignore the created object when set to True.
        :param str generator: Specifies the generator that created the file. 
        :param str base: Specifies the root folder (.dman by default).

        :raises RuntimeError: if either generator or base is not provided and no .dman folder exists.
    """
    return Track(key, default, default_factory, subdir, cluster, gitignore, generator, base)
