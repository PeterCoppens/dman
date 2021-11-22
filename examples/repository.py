from dman.core import Repository, Manager, modelclass, record, serialize, Run

import os
import json


@modelclass(name='_tst__test', storeable=True)
class Test:
    value: str


BASE_DIR_REPO = os.path.join(os.path.dirname(__file__), '_repository')
BASE_DIR_MGR = os.path.join(os.path.dirname(__file__), '_manager')


if __name__ == '__main__':
    with Repository(directory=BASE_DIR_REPO) as repo:
        repo.clean()

    with Repository.load(directory=BASE_DIR_REPO) as repo:
        print(repo.directory)
        print(repo.baseplan.preload)
        with repo.cachedir('test') as wdir:
            wdir.clean()
            wdir.store(Test('hello'), filename='test')
            print(wdir.load(Test, 'test'))

    with Manager(repo=Repository(directory=BASE_DIR_MGR)) as mgr:
        mgr.repo.clean()
        print(mgr)
        mgr.runs['test'] =  Run.create('test')
        mgr.runs['test'].timing.stop()
        mgr.runs['wow'] = Run.create('wow')
        mgr.runs['wow'].components.append('setup.py')
        mgr.runs['wow'].components.local = True

    with Manager.load(directory=BASE_DIR_MGR) as mgr:
        print(mgr)
        mgr.info.dependencies['test'] = 'test'
        print(mgr.info.dependencies)
        mgr.stamp(name='somestamp')
        # mgr.stamp(name='otherstamp', description='hello there')

    with Manager.load(directory=BASE_DIR_MGR) as mrg:
        print(mgr.runs['test'])