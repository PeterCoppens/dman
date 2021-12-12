from dman.repository import Run, Cache
from dman.utils import list_files
from tempfile import TemporaryDirectory

if __name__ == '__main__':
    with TemporaryDirectory() as base:
        with Run.load(base=base) as run:
            print(run.name, run.value)
        with Run.load(base=base) as run:
            print(run.name, run.value)
        with Run.load(name='run-tst', base=base, gitignore=False) as run:
            print(run.name, run.value)
        with Run.load(name='run-0', base=base) as run:
            run.value='it worked'
            print(run.name, run.value)

        print('='*25+' result '+'='*25)
        list_files(base)
        Cache.clear()
        list_files(base)
