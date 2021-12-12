import copy
from pathlib import Path
import time
from dataclasses import field
from datetime import datetime
import os
from dman.persistent.modelclasses import modelclass
from dman.persistent.serializables import serializable
from dman.repository import Registry
from dman.persistent.configclasses import dictsection, section, configclass
from dman.utils import get_git_hash, get_git_url, list_files


LABEL_DT_STRING = "%y%m%d%H%M%S"
DESCR_DT_STRING = "%d/%m/%y %H:%M:%S"


@serializable(name='__dman_time')
class DateTime(datetime):
    serialize_format = DESCR_DT_STRING

    def __serialize__(self):
        return self.strftime(self.serialize_format)
    
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


class DMan:
    def __init__(self, base: os.PathLike = None):
        self.stamps = Registry.load('stamps', gitignore=False, base=base)
        self.dependencies = Registry.load('dependencies', gitignore=False, base=base)
    
    def stamp(self, msg: str = ''):
        stamp = Stamp(info=Stamp.Info(msg=msg), dependencies=self.minimal_dependencies)
        self.stamps.record(stamp.label, stamp, gitignore=False)
    
    @property
    def minimal_dependencies(self):
        res = copy.deepcopy(self.dependencies.files)
        return res
    
    def add_dependency(self, path: os.PathLike):
        dep = Dependency.from_path(path)
        self.dependencies.files[dep.name] = dep

    def __enter__(self):
        self.stamps = self.stamps.__enter__()
        self.dependencies = self.dependencies.__enter__()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stamps.__exit__(exc_type, exc_val, exc_tb)
        self.dependencies.__exit__(exc_type, exc_val, exc_tb)


if __name__ == '__main__':
    import time
    with DMan() as dman:
        dman.stamps.empty()
        
    with DMan() as dman:
        dman.add_dependency('../multbx')
        dman.stamp(msg='test')
        time.sleep(1)
        dman.stamp()

    with DMan() as dman:
        for stamp in dman.stamps.files.values():
            stamp: Stamp = stamp
            print(stamp)
            print(stamp.dependencies['multbx'])

    list_files('.dman')
    
    
