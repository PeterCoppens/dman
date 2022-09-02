import textwrap, os, logging
from dman.path import get_root_path


def print_contents(path: os.PathLike):
    print(f'contents of {path}')
    with open(path, 'r') as f:
        content = f.read()
        if content[-1] == '\n':
            content = content[:-1]

        print(textwrap.indent(content, '>>> '))
    print()


def list_files(startpath, print_content: bool = True):
    if startpath is None:
        startpath = get_root_path()
    print(f'file tree of {startpath}')
    content = []
    for root, _, files in os.walk(startpath):
        root: str = root
        level = root.replace(startpath, '').count(os.sep)
        if level > 0:
            indent = ' ' * 4 * (level-1)
            print('>>> {}{}/'.format(indent, os.path.basename(root)))

        subindent = ' ' * 4 * (level)
        for f in files:
            content.append(os.path.join(root, f))
            print('>>> {}{}'.format(subindent, f))

    print()
    if print_content:
        for f in content:
            print_contents(f)
