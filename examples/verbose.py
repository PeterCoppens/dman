from dataclasses import field
from dman import serialize, deserialize, recordfield, storable
from dman import modelclass, mruns, smdict, smlist
from dman import save, load, track
from tempfile import TemporaryDirectory

from dman import verbose

@storable
class Broken: ...


@modelclass
class ModelClass:
    name: str = 'model'
    value: int = 42
    content: list = field(default_factory=list)


@modelclass(storable=True)
class SModelClass:
    name: str = 's-model'
    value: int = 134
    content: smlist = field(default_factory=smlist)


def main():
    verbose.setup(loglevel=verbose.Level.SOFT)
    with TemporaryDirectory() as base:
        runs = mruns(subdir='results')
        
        itm = ModelClass('serialized')
        itm.content.extend([25, 'a', ModelClass('inner')])
        runs.append(itm)

        itm = SModelClass('stored')
        itm.content.extend([42, Broken(), SModelClass('inner stored')])
        runs.append(itm)

        save('runs', runs, base=base, verbose=True)
        
        runs: mruns = load('runs', base=base, verbose=True)
        runs.clear()

        save('runs', runs, base=base, verbose=True)



if __name__ == '__main__':
    main()