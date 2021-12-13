from dataclasses import dataclass, field
import os
import sys
from typing import MutableMapping
from dman.persistent.modelclasses import modelclass, mdict, smdict

from dman.persistent.record import Record, RecordContext, record, remove

from pathlib import Path
from dman.persistent.serializables import serialize

from dman.persistent.storeables import read

from contextlib import suppress

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
    parent: RecordContext
    ignored: set = field(default_factory=set)
    active: bool = True

    @property
    def path(self):
        return os.path.join(self.parent.path, '.gitignore')

    def __post_init__(self):
        original = ['.gitignore']
        if os.path.exists(self.path):
            with open(self.path, 'r') as f:
                for line in f.readlines():
                    if len(line) > 0 and line[-1] == '\n':
                        line = line[:-1]
                    original.append(line)
        self.ignored = set.union(set(original), self.ignored)

    def normalize(self, file):
        return os.path.relpath(file, start=self.parent.path)

    def append(self, file: str):
        if not self.active:
            raise RuntimeError(f'can not add {file} to closed gitignore')
        self.ignored.add(self.normalize(file))
            
    def remove(self, file: str):
        if not self.active:
            raise RuntimeError(f'can not remove {file} from closed gitignore')
        with suppress(KeyError):
            self.ignored.remove(self.normalize(file))

    def close(self):
        if len(self.ignored) == 1:
            # clean up if we do not need to ignore anything
            if os.path.exists(self.path):
                os.remove(self.path)
                self.parent.clean()
        else:
            self.parent.open()
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
            self._git = GitIgnore(parent=self)
        return self._git

    def ignore(self, file: os.PathLike):
        self.git.append(file)
    
    def unignore(self, file: os.PathLike):
        self.git.remove(file)

    def track(self, gitignore: bool = True, *args, **kwargs):
        super(Repository, self).track(*args, **kwargs)
        if gitignore:
            self.parent.ignore(self.path)
        else:
            self.parent.unignore(self.path)

    def untrack(self, gitignore: bool = True, *args, **kwargs):
        if self.parent is None:
            raise RuntimeError('cannot untrack root repository')
        if gitignore:
            self.parent.unignore(self.path)
        super(Repository, self).untrack(*args, **kwargs)
    
    def join(self, other: os.PathLike) -> 'Repository':
        return super(Repository, self).join(other).__enter__()
           
    def close(self):
        for child in self.children.values():
            repo: Repository = child
            repo.close()
        if self._git is not None:
            self._git.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


@modelclass(name='_registry', storeable=True)
class Registry(MutableMapping):
    _instances = dict()

    name: str
    gitignore: bool = field(repr=False)
    content: mdict = field(repr=False)
    
    repo: Repository = field(default=None, repr=False)
    closed: bool = True

    __no_serialize__ = ['repo', 'closed', '_instances']
    
    @classmethod
    def load(cls, /, *, name: str, gitignore: bool = True, base: os.PathLike = None):
        if name in Registry._instances:
            reg: Registry = Registry._instances[name]
            return reg
        
        if base is None:
            base = get_root_path()

        repo = Repository(base)
        target = os.path.join(repo.path, f'{name}.json')
        if os.path.exists(target):
            reg: cls = read(cls, target, repo)
            reg.repo = repo
        else:
            reg = cls(name=name, gitignore=gitignore, repo=repo, content=mdict(store_by_key=True, subdir=name))
        
        Registry._instances[reg.name] = reg
        return reg

    @property
    def __make_record(self):
        return record(self, stem=self.name, suffix='.json', gitignore=self.gitignore)

    def open(self):
        self.closed = False
        self.repo = self.repo.__enter__()
        return self

    def __enter__(self):
        return self.open()

    def close(self, exc_type=None, exc_val=None, exc_tb=None):
        if self.closed:
            return
        self.closed = True
        serialize(self.__make_record, self.repo)

        self.repo.__exit__(exc_type, exc_val, exc_tb)
        del Registry._instances[self.name]

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close(exc_type, exc_val, exc_tb)

    def empty(self):
        if self.closed:
            self.open()
        remove(self.__make_record, self.repo)
        self.closed = True
        self.repo.__exit__(None, None, None)
        del Registry._instances[self.name]

    def store(self):
        return self.content
    
    def store_repo(self):
        return self.repo.join(self.name)

    def __repr__(self):
        return self.store().__repr__()

    def remove(self, key):
        self.store().remove(key, self.store_repo())

    def __getitem__(self, key):
        return self.store().__getitem__(key)

    def __setitem__(self, key, value):
        self.store().__setitem__(key, value)

    def record(self, key, value, /, *, name: str = None, subdir: os.PathLike = '', preload: bool = None, **kwargs):
        self.store().record(key, value, name=name, subdir=subdir, preload=preload, **kwargs)

    def __delitem__(self, _) -> None:
        raise ValueError('use remove to delete items')

    def __iter__(self):
        return iter(self.store())

    def __len__(self):
        return len(self.store())


@modelclass(name='_cache', storeable=True)
class Cache(Registry):
    @classmethod
    def load(cls, gitignore: bool = True, base: os.PathLike = None):
        res: Cache = super(Cache, cls).load(name='cache', gitignore=gitignore, base=base)
        return res
    
    @staticmethod
    def script_key():
        script = Path(sys.argv[0]).resolve().relative_to(
            Path(get_root_path()).parent)

        directory = str(script.parent)
        name = str(script.stem)

        if directory == '.':
            if name == '':
                return '__interpreter__'
            return name

        return f'{directory.replace(os.sep, ":")}:{name}'
    
    def store(self):
        key = Cache.script_key()
        if key in self.content:
            return self.content[key]
        
        res = smdict(store_by_key=True, options={'gitignore': True})
        self.content.record(key, res, subdir=key)
        return res
    
    def store_repo(self):
        return super().store_repo().join(Cache.script_key())

    @classmethod
    def clear(cls, base: os.PathLike = None):
        cache: Cache = Cache.load(base=base)
        cache.empty()

    def empty(self):
        if self.closed:
            self.open()

        key = Cache.script_key()
        if key in self.content:
            self.content.remove(key, self.repo)

        if len(self.content) == 0:
            super(Cache, self).empty()
        else:
            self.close()
    
    def add_keep(self):
        keep_count = self.store().get('__keep_count__', 0)
        if keep_count == 0:
            self.gitignore = False
            rec: Record = self.content.store[Cache.script_key()]
            rec.context_options['gitignore'] = False
        self.store()['__keep_count__'] = keep_count + 1
    
    def remove_keep(self):
        keep_count = self.store().get('__keep_count__', 0)
        keep_count = max(keep_count - 1, 0)
        if keep_count == 0:
            self.gitignore = True
            rec: Record = self.content.store[Cache.script_key()]
            rec.context_options['gitignore'] = True
        self.store()['__keep_count__'] = keep_count

    def record(self, key, value, /, *, name: str = None, subdir: os.PathLike = '', preload: bool = None, gitignore: bool = False, **kwargs):
        if gitignore and key in self: 
            rec: Record = self.store().store[key]
            if not rec.context_options.get('gitignore', True):
                self.remove_keep()
        elif not gitignore:
            if key not in self:
                self.add_keep()
            kwargs['gitignore'] = gitignore
        self.store().record(key, value, name=name, subdir=subdir, preload=preload, **kwargs)
    
    def remove(self, key):
        rec: Record = self.store().store[key]
        if not rec.context_options.get('gitignore', True):
            self.remove_keep()
        super().remove(key)
        
        

    
