from dataclasses import dataclass, field
import os
import sys
from tempfile import TemporaryDirectory
from dman.persistent.modelclasses import modelclass, mdict, smdict

from dman.persistent.record import Record, RecordContext, record, remove

from pathlib import Path
from dman.persistent.serializables import serialize

from dman.persistent.storeables import read

ROOT_FOLDER = '.dman'


def get_root_path():
    root_path = None
    cwd = Path.cwd()

    current_path = cwd
    while root_path is None:
        if current_path.joinpath(ROOT_FOLDER).is_dir():
            root_path = current_path.joinpath(ROOT_FOLDER)
        else:
            current_path = current_path.parent
            if current_path.parent == current_path:
                print(f'no .dman folder found, created one in {cwd}')
                root_path = os.path.join(cwd, ROOT_FOLDER)
                os.makedirs(root_path)
                return root_path

    return str(root_path)


@dataclass
class GitIgnore(RecordContext):
    ignored: set = field(default_factory=set)
    active: bool = True

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
    def dirname(self):
        return os.path.dirname(self.path)

    def append(self, file: str):
        if self.active:
            self.ignored.add(
                os.path.relpath(file, start=os.path.dirname(self.path))
            )
        else:
            raise RuntimeError('tried to register ignored file while repository is already closed')
    
    def remove(self, file: str):
        if self.active:
            self.ignored.remove(
                os.path.relpath(file, start=os.path.dirname(self.path))
            )
        else:
            raise RuntimeError('tried to delete ignored file while repository is already closed')

    def close(self):
        self.track()
        if len(self.ignored) == 1:
            # clean up if we do not need to ignore anything
            if os.path.exists(self.path):
                os.remove(self.path)
                self.untrack()
        else:
            with open(self.path, 'w') as f:
                f.writelines((line + '\n' for line in self.ignored))
        
        self.active = False

@dataclass
class Repository(RecordContext):
    path: os.PathLike = field(default_factory=get_root_path)
    parent: 'Repository' = field(default=None, repr=False)
    _git: GitIgnore = field(default=None, init=False, repr=False)

    @property
    def git(self):
        if self._git is None:
            self._git = GitIgnore.class_join(self, '.gitignore')
        return self._git

    def ignore(self, file: os.PathLike):
        self.git.append(file)
    
    def unignore(self, file: os.PathLike):
        self.git.remove(file)

    def track(self, gitignore: bool = True, *args, **kwargs):
        super(Repository, self).track(*args, **kwargs)
        if gitignore:
            self.parent.ignore(self.path)

    def untrack(self, gitignore: bool = True, *args, **kwargs):
        if self.parent is None:
            raise RuntimeError('cannot untrack root repository')
        if gitignore:
            self.parent.unignore(self.path)
        super(Repository, self).untrack(*args, **kwargs)
    
    def join(self, other: os.PathLike) -> 'Repository':
        res = super(Repository, self).join(other)
        return res.__enter__()
           
    def close(self):
        for child in self.children.values():
            repo: Repository = child
            repo.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class TemporaryRepository(TemporaryDirectory):
    def __init__(self):
        TemporaryDirectory.__init__(self)
        self.repo = None
    
    def __enter__(self) -> 'Repository':
        self.repo = Repository(TemporaryDirectory.__enter__(self))
        return self.repo.__enter__()

    def __exit__(self, exc_type, exc_val, exc_tb):
        res = self.repo.__exit__(exc_type, exc_val, exc_tb)
        TemporaryDirectory.__exit__(self, exc_type, exc_val, exc_tb)
        return res



@modelclass(name='_registry', storeable=True)
class Registry:
    _instances = dict()

    name: str
    gitignore: bool = field(repr=False)
    files: mdict = field(repr=False)

    repo: Repository = field(default=None, repr=False)
    _repo: Repository = field(default=None, repr=False, init=False)

    _closed: bool = True

    __no_serialize__ = ['repo', '_repo', '_instances', '_closed']

    @classmethod
    def load(cls, name: str, gitignore: bool = True, base: os.PathLike = None):
        if name in Registry._instances:
            reg: Registry = Registry._instances[name]
            return reg

        if base is None:
            base = get_root_path()
        
        repo = Repository(base)
        local = RecordContext(base)
        target = local.join(f'{name}.json')
        if os.path.exists(target.path):
            reg: cls = read(cls, target.path, local)
            reg.repo = repo
        else:
            reg = cls(name=name, gitignore=gitignore, repo=repo, files=mdict(store_by_key=True, subdir=name))

        cls._instances[name] = reg
        return reg
    
    @property
    def __make_record(self):
        return record(self, stem=self.name, suffix='.json', gitignore=self.gitignore)
    
    @property
    def directory(self):
        return os.path.join(self.repo.path, self.name)

    def record(self, key, value, /, *, name: str = None, subdir: os.PathLike = '', preload: bool = None, gitignore: bool = True):
        self.files.record(key, value, name=name, subdir=subdir, preload=preload, gitignore=gitignore)
    
    def remove(self, key):
        self.files.remove(key, self.repo)
    
    def open(self):
        self._closed = False
        self._repo = self.repo
        self.repo = self.repo.__enter__()
        return self

    def __enter__(self):
        return self.open()
    
    def close(self, exc_type=None, exc_val=None, exc_tb=None):
        if self._closed:
            return
        self._closed = True
        serialize(self.__make_record, self.repo)

        self._repo.__exit__(exc_type, exc_val, exc_tb)
        del Registry._instances[self.name]
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close(exc_type, exc_val, exc_tb)
    
    def empty(self):
        if self._closed:
            self.open()
        remove(self.__make_record, self.repo)
        self._closed = True
        self._repo.__exit__(None, None, None)
        del Registry._instances[self.name]


class TemporaryRegistry:
    def __init__(self, directory: TemporaryDirectory, registry: Registry):
        self.directory = directory
        self.registry = registry
    
    @staticmethod
    def load(name: str, gitignore: bool = True):
        directory = TemporaryDirectory()
        registry = Registry.load(name, gitignore, base=directory.__enter__())
        return TemporaryRegistry(directory, registry)

    def __enter__(self) -> 'Registry':
        return self.registry.__enter__()

    def __exit__(self, exc_type, exc_val, exc_tb):
        res = self.registry.__exit__(exc_type, exc_val, exc_tb)
        self.directory.__exit__(exc_type, exc_val, exc_tb)
        return res


class Cache(Registry):
    @classmethod
    def load(cls, gitignore: bool = True, base: os.PathLike = None):
        return super(Cache, cls).load(name='cache', gitignore=gitignore, base=base)
    
    @classmethod
    def clear(cls, base: os.PathLike = None):
        cache = super(Cache, cls).load(name='cache', base=base)
        cache.empty()
    
    @staticmethod
    def script_key():
        script = Path(sys.argv[0]).resolve().relative_to(
            Path(get_root_path()).parent)
        directory = str(script.parent)
        name = str(script.stem)
        return f'{directory.replace(os.sep, ":")}:{name}'
    
    @property
    def store(self):
        key = Cache.script_key()
        if key in self.files:
            return self.files[key]
        
        res = smdict(subdir=key, store_by_key=True, options={'gitignore': True})
        self.files[key] = res
        return res
    
    def __getitem__(self, key):
        return self.store[key]
    
    def __setitem__(self, key, value):
        self.store.__setitem__(key, value)
    
    def get(self, key, default):
        return self.store.get(key, default)

    def record(self, key, value, /, *, name: str = None, subdir: os.PathLike = '', preload: bool = None, gitignore: bool = True):
        self.store.record(
            key, value, 
            name=name, subdir=subdir,
            preload=preload, gitignore=gitignore
        )

    def remove(self, key):
        self.store.remove(
            key, self.repo
        )
    
    def empty(self):
        if self._closed:
            self.open()
        
        key = Cache.script_key()
        if key in self.files:
            self.files.remove(key, self.repo)

        if len(self.files) == 0:
            super(Cache, self).empty()
        else:
            self.close()


class RunFactory:
    def __init__(self, type, name, base, gitignore) -> None:
        self.cache = Cache.load(base=base)
        self.name = name
        self.gitignore = gitignore
        self.run = None
        self.type = type
    
    def __enter__(self) -> 'Run':
        self.cache.__enter__()
        if self.name is None:
            run_count = self.cache.get('__run_count', 0)
            self.name = f'run-{run_count}'
            self.cache['__run_count'] = run_count + 1
        self.run = self.cache.get(
            self.name,
            self.type(name=self.name)
        )
        return self.run
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cache.record(self.name, self.run, subdir='runs', gitignore=self.gitignore)
        self.cache.__exit__(exc_type, exc_val, exc_tb)
        


@modelclass(name='_dman__run', storeable=True)
class Run:
    name: str
    value: str = 'none'
    
    @classmethod
    def load(cls, name: str = None, base: os.PathLike = None, gitignore: bool = True):
        return RunFactory(type=cls, name=name, base=base, gitignore=gitignore)
        
        

    
