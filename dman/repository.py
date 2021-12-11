from dataclasses import dataclass, field
from functools import wraps
import os
from dman.persistent.modelclasses import mdict, modelclass
from dman.persistent.record import RecordContext

from pathlib import Path
import shutil

from dman.persistent.serializables import serializable
from dman.persistent.storeables import is_storeable, read, storeable, storeable_type, write

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

    def append(self, file: str):
        if self.active:
            self.ignored.add(
                os.path.relpath(file, start=os.path.dirname(self.path)) + '\n'
            )
        else:
            raise RuntimeError('tried to register ignored file while repository is already closed')

    def __write__(self, path: str = None):
        if path is None: path = self.path
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
class RepoContext(RecordContext):
    git: 'GitIgnore'

    def evaluate(self, gitignore: bool = True):
        if gitignore:
            self.git.append(self.path)

    def join(self, other: str):
        ctx = super().join(other)
        return RepoContext(path=ctx.path, git=self.git)


class CacheContext(RepoContext):
    def clear(self):
        shutil.rmtree(self.path)
        self.git.active = False 


@dataclass
class Repository():
    base: str = field(default_factory=get_root_path)
    git: dict = field(default_factory=dict)

    def folder(self, name):
        target = os.path.join(self.base, name)
        self.git[name] = self.git.get(name, GitIgnore(target))
        return target, self.git[name]

    @property
    def root(self): 
        return RepoContext(*self.folder(''))
    
    @property
    def cache(self) -> CacheContext:
        return CacheContext(*self.folder('cache'))
    
    def close(self):
        for v in self.git.values():
            git: GitIgnore = v
            if git.active:
                git.__write__()
                git.active = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    
def persistent(*, name: str, subdir: str = ''):
    def wrap(cls):
        o_store = getattr(cls, '__store__', None)
        o_new = cls.__new__
        o_init = cls.__init__
        o_enter = getattr(cls, '__enter__', None)
        o_exit = getattr(cls, '__exit__', None)
        o_remove = getattr(cls, '__remove__', None)

        reading = False
        instance = None

        def get_file():
            local_name = name
            local_sdir = subdir

            root = get_root_path()
            ctx = RecordContext(root)

            local = ctx.join(local_sdir)
            file = os.path.join(local.path, local_name)
            return local, file

        @wraps(cls.__new__)
        def __new__(cls, *args, **kwargs):
            nonlocal instance
            nonlocal reading

            if reading:
                print('..reading')
                reading = False
                res = o_new(cls)
                o_init(res, *args, **kwargs)
                return res

            if instance is None:
                local, file = get_file()
                if os.path.exists(file):
                    reading = True
                    instance = read(storeable_type(cls), file, local)
                    reading = False
                else:
                    print('..instantiating')
                    instance = o_new(cls)
                    o_init(instance, *args, **kwargs)

            return instance
        
        def __enter__(self):
            if o_enter:
                return o_enter(self)
            return self            
        
        def __store__(self):
            nonlocal instance
            if o_store:
                o_store(self, name, subdir)
            else:
                local, file = get_file()
                write(instance, file, local)
            instance = None
        
        def __remove__(self, context=None):
            if o_remove:
                o_remove(self, context)

            _, file = get_file()
            if os.path.exists(file):
                os.remove(file)
            
        
        cls.__new__ = staticmethod(__new__)
        cls.__init__ = lambda self, *args, **kwargs: None
        cls.__enter__ = __enter__

        if o_exit is None:
            cls.__exit__ = lambda self, exc_type, exc_val, exc_tb: __store__(self)
        setattr(cls, '__store__', __store__)
        setattr(cls, '__remove__', __remove__)

        return cls

    return wrap


    
