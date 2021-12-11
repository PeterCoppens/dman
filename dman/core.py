from dataclasses import dataclass, field
import os
from dman.persistent.modelclasses import modelclass, recordfield, smdict, smdict_factory
from dman.persistent.record import record
from dman.persistent.serializables import serialize
from dman.persistent.storeables import STO_TYPE, read, storeable, write
from dman.repository import Repository, persistent


@persistent(name='dman.json')
@modelclass(name='__dman', storeable=True)
class DataManager(Repository):
    generators: smdict = recordfield(
        default_factory=smdict_factory(
            subdir='generators', store_by_key=True, store_subdir=True, options={'gitignore': False}
        ), name='gen.json', gitignore=False
    )

    acquired: int = field(default=0, init=False, repr=False)

    __no_serialize__ = ['base', 'git', 'acquired']

    def __post_init__(self):
        self.generators.subdir = 'generators'
        self.generators.store_by_key(subdir=True)
    
    def __enter__(self):
        Repository.__enter__(self)
        if self.acquired == 0:
            self.acquired += 1
        return self

    def __store__(self, file, subdir):
        print('..storing')
        local = self.root.join(subdir)
        write(self, local.join(file).path, local)
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.acquired > 0:
            self.acquired -= 1
        if self.acquired == 0:
            self.__store__()
        super().__exit__(exc_type, exc_val, exc_tb)
    
    def acquire(self):
        self.acquired += 1
        if self.acquired == 1:
            self.__enter__()
        return self
    
    def release(self, exc_type=None, exc_val=None, exc_tb=None):
        if self.acquired == 0:
            raise RuntimeError('released without first acquiring')

        self.acquired -= 1

        if self.acquired == 0:
            self.__exit__(exc_type, exc_val, exc_tb)


@modelclass(name='__dman_gen', storeable=True)
class Generator:
    name: str
    latest: str = None

    # TODO specific context options per key!
    runs: smdict = recordfield(
        default_factory=smdict_factory(subdir='runs', store_by_key=True, store_subdir=True, options={'gitignore': False}), name='runs.json', gitignore=False
    )

    def latest_run(self) -> 'Run':
        if self.latest is None:
            raise RuntimeError('no latest run')
        return self.runs[self.latest]
    
    def run(self, name: str) -> 'Run':
        self.latest = name
        if name in self.runs:
            return self.runs[name]
        
        self.runs[name] = Run(name=name)
        return self.runs[name]

    @classmethod
    def load(cls, /, *, name: str):
        mgr = DataManager()
        if name in mgr.generators:
            return mgr.generators[name]

        gen = cls(name=name)
        mgr.generators[name] = gen
        return gen
    
    def __enter__(self):
        DataManager().acquire()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        DataManager().release(exc_type, exc_val, exc_tb)

@modelclass(storeable=True)
class Test:
    a: str = 'hello'


@modelclass(name='__dman_run', storeable=True)
class Run:
    name: str
    val: Test = recordfield(default_factory=Test)

    @classmethod
    def load(self, generator: str, name: str):
        return Generator.load(name=generator).run(name)

    def __enter__(self):
        DataManager().acquire()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        DataManager().release(exc_type, exc_val, exc_tb)


if __name__ == '__main__':
    with DataManager() as mgr:
        mgr.acquire()
    DataManager().release()

    with DataManager() as mgr:
        print(mgr.generators)
    
    print('== generator tests ==')
    with Generator.load(name='hello') as gen:
        gen.latest = 'a'
        print(DataManager().generators)
        print('finished generator')

    with Generator.load(name='hello').run('test') as run:
        print(run.val)
        print(run.name)
    
    with Generator.load(name='hello').latest_run() as run:
        print(run.name)

    with Run.load(generator='hello', name='another') as run:
        print(run.name)
        print(run.val)
        print(Generator.load(name='hello').runs)
    
    with DataManager() as mgr:
        print(serialize(mgr, mgr.root))