import copy
from pathlib import Path
from dataclasses import field
from datetime import datetime
import os
from dman.persistent.modelclasses import mdict, modelclass
from dman.persistent.serializables import serializable
from dman.repository import track, get_root_path
from dman.persistent.configclasses import dictsection, section, configclass
from dman.utils.git import get_git_hash, get_git_url


LABEL_DT_STRING = "%y%m%d%H%M%S"
DESCR_DT_STRING = "%d/%m/%y %H:%M:%S"


def init_dman():
    get_root_path(create=True)


@serializable(name='__dman_time')
class DateTime(datetime):
    serialize_format = DESCR_DT_STRING

    def __repr__(self):
        return self.strftime(self.serialize_format)

    def __serialize__(self):
        return self.__repr__()
    
    @classmethod
    def __deserialize__(cls, serialized: str):
        return DateTime.strptime(serialized, cls.serialize_format)


def _default_stamp_name():
    return f'stamp-{datetime.now().strftime(LABEL_DT_STRING)}'


def _default_dependency_dir(content=None):
    return dictsection(content=content, type=Dependency)


@configclass(name='_dman__stamp')
class Stamp:
    @section
    class Info:
        name: str = field(default_factory=_default_stamp_name)
        msg: str = ''
    info: Info
    
    @section
    class Stamp:
        hash: str = field(default_factory=get_git_hash)
        time: DateTime = field(default_factory=DateTime.now)
    stamp: Stamp

    dependencies: dictsection = field(default_factory=_default_dependency_dir)

    def __post_init__(self):
        if not isinstance(self.dependencies, dictsection):
            self.dependencies = _default_dependency_dir(content=self.dependencies)

    @property
    def label(self):
        return self.info.name
    
    def display(self, indent=''):
        print(indent+f'info on stamp "{self.info.name}"')
        if len(self.info.msg) > 0:
            print(indent+f'  - note: {self.info.msg}')
        print(indent+f'  - hash: {self.stamp.hash}')
        print(indent+f'  - time: {self.stamp.time}')
        if len(self.dependencies) > 0:
            print(indent+f'stamp dependencies:')
            for k, dep in self.dependencies.items():
                dep: Dependency = dep
                dep.display(indent='  ', head = '- ')
        

@modelclass(name='_dman__dep', compact=True)
class Dependency:
    name: str
    path: str
    remote: str
    hash: str

    @classmethod
    def from_path(cls, path: os.PathLike):
        # we need to select the path relative to root
        path = Path(path)

        remote = get_git_url(cwd=path.resolve())
        base = os.path.basename(remote)
        name, _ = os.path.splitext(base)

        return cls(name.lower(), path=str(path), remote=remote, hash=get_git_hash(cwd=path))
    
    def update(self):
        self.hash = get_git_hash(cwd=self.path)

    def display(self, indent: str = '', head: str = None):
        if head is None:
            print(f'info on dependency "{self.name}"')
        else:
            print(indent+head+f'{self.name}')
        print(indent+f'  path: {self.path}')
        print(indent+f'  repo: {self.remote}')
        print(indent+f'  hash: {self.hash}')
        

class DMan:
    def __init__(self, base: os.PathLike = None):
        self.stamps = mdict(subdir='stamps', store_by_key=True, auto_clean=True)
        self.__stamps = DMan.track('stamps', default=self.stamps, base=base)
        self.dependencies = mdict(subdir='dependencies', store_by_key=True, auto_clean=True)
        self.__dependencies = DMan.track('dependencies', default=self.dependencies, base=base)

    @staticmethod
    def track(key: str, default = None, base: os.PathLike = None):
        return track(key, default=default, generator=None, cluster=False, gitignore=False, base=base)
    
    def stamp(self, name: str = None, msg: str = ''):
        info = Stamp.Info(msg=msg)
        if name:
            info.name = name
        stamp = Stamp(info=info, dependencies=self.minimal_dependencies)
        self.stamps.record(stamp.label, stamp)
        self.stamps['__latest__'] = stamp.label
    
    def latest(self):
        return self.stamps.get('__latest__', None)
    
    @property
    def minimal_dependencies(self):
        res = copy.deepcopy(self.dependencies)
        return res
    
    def add_dependency(self, path: os.PathLike):
        if not os.path.exists(path):
            raise ValueError(f'could not find git repository at: {path}')
        dep = Dependency.from_path(path)
        self.dependencies[dep.name] = dep

    def __enter__(self):
        self.stamps = self.__stamps.__enter__()
        self.dependencies = self.__dependencies.__enter__()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # clean up latest
        if self.latest() not in self.stamps:
            self.stamps.pop('__latest__', None)
            
        self.__stamps.__exit__(exc_type, exc_val, exc_tb)
        self.__dependencies.__exit__(exc_type, exc_val, exc_tb)
