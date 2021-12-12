from dataclasses import dataclass, field
from functools import wraps
from genericpath import exists
from inspect import getouterframes
import os
from tempfile import TemporaryDirectory
from dman.persistent.modelclasses import modelclass, recordfield, mdict, mdict_factory

from dman.persistent.record import RecordConfig, RecordContext, record, remove

from pathlib import Path
import shutil
from dman.persistent.serializables import BaseContext, serialize

from dman.persistent.storeables import read, storeable, write

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
                return cwd

    return str(root_path)


@dataclass
class GitIgnore:
    path: str
    ignored: set = field(default_factory=set)
    active: bool = True

    def __post_init__(self):
        self.path = os.path.join(self.path, '.gitignore')
        if os.path.exists(self.path):
            original = GitIgnore.__read__(self.path)
            self.ignored = set.union(original.ignored, self.ignored)
        self.ignored.add('.gitignore\n')
    
    @property
    def dirname(self):
        return os.path.dirname(self.path)

    def append(self, file: str):
        if self.active:
            self.ignored.add(
                os.path.relpath(file, start=os.path.dirname(self.path)) + '\n'
            )
        else:
            raise RuntimeError('tried to register ignored file while repository is already closed')
    
    def remove(self, file: str):
        if self.active:
            self.ignored.remove(
                os.path.relpath(file, start=os.path.dirname(self.path)) + '\n'
            )
        else:
            raise RuntimeError('tried to delete ignored file while repository is already closed')


    def __write__(self, path: str = None):
        if path is None: path = self.path
        if len(self.ignored) == 1:
            # clean up if we do not need to ignore anything
            if os.path.exists(path):
                os.remove(path)
            if os.path.isdir(self.dirname) and len(os.listdir(self.dirname)) == 0:
                os.rmdir(self.dirname)
        else:
            if not os.path.isdir(self.dirname):
                os.makedirs(self.dirname)
            with open(path, 'w') as f:
                f.writelines((line for line in self.ignored))

    @classmethod
    def __read__(cls, path):
        with open(path, 'r') as f:
            ignored = [line for line in f.readlines()]
            if len(ignored) > 0 and ignored[-1][-1] != '\n':
                ignored[-1] += '\n'

            return cls(path=path, ignored=set(ignored))


@dataclass
class Repository(RecordContext):
    path: os.PathLike = field(default_factory=get_root_path)
    parent: 'Repository' = field(default=None, repr=False)
    git: GitIgnore = field(default=None, init=False, repr=False)
    children: dict = field(default_factory=dict, init=False, repr=False)
    
    def ignore(self, file: os.PathLike):
        if self.git is None:
            self.git = GitIgnore(self.path)
        self.git.append(file)
    
    def unignore(self, file: os.PathLike):
        if self.git is None:
            self.git = GitIgnore(self.path)
        self.git.remove(file)

    def track(self, gitignore: bool = True, *args, **kwargs):
        if gitignore:
            if self.parent is None:
                raise RuntimeError('cannot track root repository')
            self.parent.ignore(self.path)

    def untrack(self, gitignore: bool = True, *args, **kwargs):
        if gitignore:
            if self.parent is None:
                raise RuntimeError('cannot untrack root repository')
            self.parent.unignore(self.path)
    
    def join(self, other: os.PathLike):
        if other in self.children:
            return self.children[other]

        ctx = super().join(other)
        if os.path.abspath(ctx.path) == os.path.abspath(self.path):
            return self

        sub = Repository(path=ctx.path, parent=self)
        self.children[other] = sub
        return sub.__enter__()
           
    def close(self):
        if self.git is not None and self.git.active:
            self.git.__write__()
            self.git.active = False

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



@modelclass(name='__registry', storeable=True)
class Registry:
    _instances = dict()

    name: str
    gitignore: bool = field(repr=False)
    files: mdict = field(repr=False)

    repo: Repository = field(default=None, repr=False)
    _repo: Repository = field(default=None, repr=False, init=False)

    _closed: bool = True

    __no_serialize__ = ['repo', '_repo', '_instances', '_closed']

    @staticmethod
    def load(name: str, gitignore: bool = True, base: os.PathLike = None):
        if name in Registry._instances:
            reg: Registry = Registry._instances[name]
            return reg

        if base is None:
            base = get_root_path()
        
        repo = Repository(base)
        local = RecordContext(base)
        target = local.join(f'{name}.json')
        if os.path.exists(target.path):
            reg: Registry = read(Registry, target.path, local)
            reg.repo = repo
        else:
            reg = Registry(name=name, gitignore=gitignore, repo=repo, files=mdict(store_by_key=True, subdir=name))

        Registry._instances[name] = reg
        return reg
    
    @property
    def __make_record(self):
        return record(self, stem=self.name, suffix='.json', gitignore=self.gitignore)
    
    @property
    def path(self):
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
    
    def clear(self):
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

class Cache:
    @staticmethod
    def load(gitignore: bool = True, base: os.PathLike = None):
        return Registry.load(name='cache', gitignore=gitignore, base=base)
    
    @staticmethod
    def clear(base: os.PathLike = None):
        cache = Registry.load(name='cache', base=base)
        cache.clear()


if __name__ == '__main__':
    with Registry.load(name='hello') as reg:
        reg.files['a'] = 'test'
        print(Registry.load(name='hello') is reg)
    
    with Registry.load(name='hello') as reg:
        print(reg.files['a'])
    
