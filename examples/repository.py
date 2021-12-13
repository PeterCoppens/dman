from tempfile import TemporaryDirectory
from dman.utils import list_files

from record.record import TestSto
from dman.repository import Registry, Repository, Cache


if __name__ == '__main__':
    # build gitignore files
    with TemporaryDirectory() as base:
        with Repository(path=base) as repo:
            file = repo.join('test')
            file.track()

            sub_repo = repo.join('sub')
            file = sub_repo.join('sub_test')
            file.track()

            sub_sub_repo = sub_repo.join('sub')
            file = sub_sub_repo.join('sub_sub_test')
            file.track()

            repo.close()
            list_files(base)

    # registry usage
    with TemporaryDirectory() as base:
        with Registry.load(name='registry', gitignore=False, base=base) as reg:
            reg.record('test0', TestSto(name='value0'))
            reg.record('test1', TestSto(name='value1'), gitignore=False)
            reg.record('test2', TestSto(name='value2'))
            reg.record('test3', TestSto(name='value3'))
            reg.remove('test3')

            reg.close()
            print(f'{"="*25} result {"="*25}')
            list_files(reg.repo.path)

            reg = Registry.load(name='registry', base=reg.repo.path)
            reg.open()
            print(reg.content)
            print(reg.repo.path)

            reg.remove('test2')
            reg.close()
            print(f'{"="*25} result {"="*25}')
            list_files(reg.repo.path)
    
    with TemporaryDirectory() as dir: 
        with Cache.load(base=dir) as cache:
            cache.record('test', TestSto('test'))
        print(f'{"="*25} cache {"="*25}')
        list_files(dir)

        print(f'{"="*25} cache loaded {"="*25}')
        with Cache.load(base=dir) as cache:
            print(cache['test'])
        print()

        print(f'{"="*25} cache cleared {"="*25}')
        Cache.clear(base=dir)
        list_files(dir)
