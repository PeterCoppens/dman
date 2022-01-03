from dataclasses import MISSING, dataclass, field
import os
from pathlib import Path
import sys
from contextlib import suppress
from typing import Union

from dman.persistent.record import RecordContext, record
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
                raise RuntimeError('no .dman folder found')

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
    context: RecordContext
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
    def __init__(self, context: RecordContext, git: GitIgnore = None) -> None:
        self.context: RecordContext = context
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
    ctx = RecordContext(base)

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
        target = repo.join(filename).track()
        with open(target.path, 'w') as f:
            sjson.dump(ser, f, indent=4)


def load(key: str, *, default=MISSING, default_factory=MISSING, subdir: os.PathLike = '', cluster: bool = True, gitignore: bool = True, generator: str = MISSING, base: os.PathLike = None):
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
        self.obj = None
        self.default = default
        self.default_factory = default_factory
        self.subdir = subdir
        self.cluster = cluster
        self.gitignore = gitignore
        self.generator = generator
        self.base = base

    def __enter__(self):
        self.obj = load(self.key, default=self.default, default_factory=self.default_factory, subdir=self.subdir, generator=self.generator, base=self.base, cluster=self.cluster, gitignore=self.gitignore)
        return self.obj
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        return save(self.key, self.obj, subdir=self.subdir, gitignore=self.gitignore, generator=self.generator, base=self.base, cluster=self.cluster)


def track(key: str, *, default = MISSING, default_factory = MISSING, subdir: os.PathLike = '', cluster: bool = True, gitignore: bool = True, generator: str = MISSING, base: os.PathLike = None):
    return Track(key, default, default_factory, subdir, cluster, gitignore, generator, base)