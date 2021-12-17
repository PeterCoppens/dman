from dman.core import DMan, Stamp
from dman.utils.display import list_files

from tempfile import TemporaryDirectory

if __name__ == '__main__':
    import time
    with TemporaryDirectory() as base:
        with DMan(base=base) as dman:
            dman.stamps.clear()
            
        with DMan(base=base) as dman:
            dman.add_dependency('../multbx')
            dman.stamp(msg='test')
            time.sleep(1)
            dman.stamp()

        with DMan(base=base) as dman:
            for stamp in dman.stamps.values():
                stamp: Stamp = stamp
                print(f'info on stamp {stamp.info.name}')
                print('>>>', stamp.stamp.time, stamp.stamp.hash)
                print('>>>', stamp.dependencies['multbx'].name)

        list_files(base)
    
    