from pathlib import Path
import os


ROOT_FOLDER = '.dman'


class RootError(RuntimeError):
    ...


def get_root_path(create: bool = False):
    root_path = None
    cwd = Path.cwd()

    current_path = cwd
    while root_path is None:
        if current_path.joinpath(ROOT_FOLDER).is_dir():
            root_path = current_path.joinpath(ROOT_FOLDER)
        else:
            current_path = current_path.parent
            if current_path.parent == current_path:
                if create:
                    print(f'no .dman folder found, created one in {cwd}')
                    root_path = os.path.join(cwd, ROOT_FOLDER)
                    os.makedirs(root_path)
                    return root_path
                raise RootError(
                    'no .dman folder found. Consider running $dman init')

    return str(root_path)
