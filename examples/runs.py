from dman.runs import Run, Cache
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

        print('='*25+' result with run-tst '+'='*25)
        list_files(base, print_content=False)
        with Cache.load(base=base) as cache:
            cache.remove('run-tst')
            
        print('='*25+' result without run-tst '+'='*25)
        list_files(base, print_content=True)

        print('='*25+' result '+'='*25)
        list_files(base)
        # Cache.clear(base=base)
        # list_files(base)
