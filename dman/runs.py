import os
from dman.persistent.modelclasses import modelclass


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
        self.cache.record(self.name, self.run, subdir='runs',
                          gitignore=self.gitignore)
        self.cache.__exit__(exc_type, exc_val, exc_tb)


@modelclass(name='_dman__run', storeable=True)
class Run:
    name: str
    value: str = 'none'

    @classmethod
    def load(cls, name: str = None, base: os.PathLike = None, gitignore: bool = True):
        return RunFactory(type=cls, name=name, base=base, gitignore=gitignore)

    @staticmethod
    def remove(name: str, base: os.PathLike = None):
        with Cache.load(base=base) as cache:
            cache.remove(name)
            cache['__run_count'] = cache['__run_count'] - 1
            if cache['__run_count'] == 0:
                del cache['__run_count']
