import os
from tempfile import TemporaryDirectory
import textwrap

from example_record import TestSto
from dman.repository import Cache, Registry, TemporaryRegistry, TemporaryRepository


def print_contents(path: os.PathLike):
    print(f'contents of {path}')
    with open(path, 'r') as f:
        print(textwrap.indent(f.read(), '>>> '))

def list_files(startpath):
    print(f'file tree of {startpath}')
    content = []
    for root, dirs, files in os.walk(startpath):
        level = root.replace(startpath, '').count(os.sep)
        if level > 0:
            indent = ' ' * 4 * (level-1)
            print('>>> {}{}/'.format(indent, os.path.basename(root)))

        subindent = ' ' * 4 * (level)
        for f in files:
            content.append(os.path.join(root, f))
            print('>>> {}{}'.format(subindent, f))

    print()
    for f in content:
        print_contents(f)
        print()


if __name__ == '__main__':
    # build gitignore files
    with TemporaryRepository() as repo:
        file = repo.join('test')
        file.track()

        sub_repo = repo.join('sub')
        file = sub_repo.join('sub_test')
        file.track()

        sub_sub_repo = sub_repo.join('sub')
        file = sub_sub_repo.join('sub_sub_test')
        file.track()

        repo.close()
        print_contents(os.path.join(repo.path, '.gitignore'))
        print_contents(os.path.join(repo.path, 'sub/.gitignore'))
        print_contents(os.path.join(repo.path, 'sub/sub/.gitignore'))

    # registry usage
    with TemporaryRegistry.load(name='registry', gitignore=False) as reg:
        print(reg.files)
        print(reg.path)
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
        print(reg.files)
        print(reg.path)

        reg.remove('test2')
        reg.close()
        print(f'{"="*25} result {"="*25}')
        list_files(reg.repo.path)
    
    with TemporaryDirectory() as dir: 
        with Cache.load(base=dir) as cache:
            cache.record('test', TestSto('test'))
        print(f'{"="*25} cache {"="*25}')
        list_files(dir)

        Cache.clear(base=dir)
        print(f'{"="*25} cache cleared {"="*25}')
        list_files(dir)
