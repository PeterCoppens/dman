from dataclasses import dataclass, field
import os
import sys
from tempfile import TemporaryDirectory
from dman.persistent.modelclasses import modelclass, mdict, smdict

from dman.persistent.record import RecordContext, record, remove

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
            self.parent.remove_child(self)
    
    def join(self, other: os.PathLike):
        if other == '' or other == '.':
            return self

        # other = os.path.relpath(other, start=self.path)
        head, tail = os.path.split(other)
        if len(head) > 0:
            return self.join(head).join(tail)

        if other in self.children:
            return self.children[other]

        ctx = super().join(other)
        if os.path.abspath(ctx.path) == os.path.abspath(self.path):
            return self

        sub = Repository(path=ctx.path, parent=self)
        self.children[other] = sub
        return sub.__enter__()
    
    def remove_child(self, child: 'Repository'):
        path = os.path.relpath(child.path, start=self.path)
        del self.children[path]
           
    def close(self):
        for child in self.children.values():
            repo: Repository = child
            repo.close()

        if self.git is not None and self.git.active:
            self.git.__write__()
            self.git.active = False
        elif os.path.isdir(self.path) and len(os.listdir(self.path)) == 0:
            os.rmdir(self.path)

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
    def __init__(self, type, name: str = None, base: str = None) -> None:
        self.cache = Cache.load(base=base)
        self.name = name
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
        self.cache.record(self.name, self.run, subdir='runs')
        self.cache.__exit__(exc_type, exc_val, exc_tb)
        


@modelclass(name='_dman__run', storeable=True)
class Run:
    name: str
    value: str = 'none'
    
    @classmethod
    def load(cls, name: str = None, base: os.PathLike = None):
        return RunFactory(type=cls, name=name, base=base)
    


if __name__ == '__main__':
    # Cache.clear()
    with Run.load() as run:
        print(run.name, run.value)
    with Run.load(name='run-0') as run:
        print(run.name, run.value)


    with Cache.load() as cache:
        from dman.utils import list_files
        list_files(cache.repo.path)
        cache['test'] = cache.get('test', 0) + 1
        print(len(cache.store))
        if len(cache.store) > 5:
            cache.clear()
        
        

    
