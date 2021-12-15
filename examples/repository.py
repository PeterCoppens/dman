from dman.persistent.modelclasses import modelclass
from dman.repository import repository, track
from dman.utils import list_files
from dman.persistent.storeables import write
from tempfile import TemporaryDirectory

from record.record import TestSto

@modelclass
class Model:
    label: str
    content: TestSto         


@modelclass
class SingModel:
    label: str


@modelclass(storable=True)
class StoModel(Model):
    pass


if __name__ == '__main__':
    with repository() as repo:
        print(repo)
    
    with repository(generator=None) as repo:
        print(repo)
    
    with TemporaryDirectory() as base:
        with repository(base=base, gitignore=True) as repo:
            print(repo)
            ctx = repo.join('test.txt')
            ctx.track()
            write(TestSto(name='test'), ctx.path)

        list_files(base)


    with TemporaryDirectory() as base:
        input('\n >>> continue?')
        with track('tracked', default=Model(label='test', content=TestSto(name='hello world')), base=base) as model:
            print(model)
        
        with track('singular', default=SingModel(label='singluar test'), base=base, cluster=False) as test:
            print(test)
        
        list_files(base)

        input('\n >>> continue?')
        with track('tracked', base=base, gitignore=False) as model:
            model: Model = model
            model.content.name = 'found'

        list_files(base)

        input('\n >>> continue?')
        try:
            with track('not_found', base=base) as model:
                print(model)
        except FileNotFoundError as e:
            print(str(e))





