"""
Verbose
-------------------

This script shows the usage of verbose (de)serialization. 
When running the script you can press ENTER to proceed to the next step.
Each time new log information will be shown in terminal, which 
tells a user when what object is (de)serialized in the stack. Errors 
are highlighted in red. 

"""
import dman
from dman import verbose
from tempfile import TemporaryDirectory

@dman.storable
class Broken:
    """
    Wrongly defined storable.
        Will cause errors during write.
    """
    ...


@dman.modelclass
class ModelClass:
    """
    Basic modelclass.
    """
    name: str = 'model'
    value: int = 42
    content: list = dman.field(default_factory=list)


@dman.modelclass(storable=True)
class SModelClass:
    """
    Basic storable modelclass.
    """
    name: str = 's-model'
    value: int = 134
    content: dman.smlist = dman.field(default_factory=dman.smlist)


def main():
    # ------------------------- setup ------------------------------------------
    # You can configure the log level by uncommenting the following lines. 
    #   Feel free to experiment

    # [SOFT] only show errors
    # verbose.setup(loglevel=verbose.Level.SOFT)   

    # [HARD] raise an exception when errors are encountered
    # verbose.setup(loglevel=verbose.Level.HARD)     

    # [DEBUG] show full debug information
    verbose.setup(loglevel=verbose.Level.DEBUG)

    # [LOG] you can send verbose information to a log file.
    # verbose.setup(loglevel=verbose.Level.DEBUG, logfile='log.ansi')
    # ------------------------- setup ------------------------------------------


    
    # create a complex object to serialize
    runs = dman.mruns(subdir='results')
    
    itm = ModelClass('serialized')
    itm.content.extend([25, 'a', ModelClass('inner')])
    runs.append(itm)

    itm = SModelClass('stored')
    itm.content.extend([42, Broken(), SModelClass('inner stored')])
    runs.append(itm)

    # start serialization to file
    #   will be stored in ``.dman/cache/examples:verbose/runs``
    input("Press Enter to start saving instance ...")
    dman.save('runs', runs, verbose=True)

    # reload from file
    input("Press Enter to start loading instance ...")
    runs: dman.mruns = dman.load('runs', verbose=True)

    # clear the runs
    input("Press Enter to clear runs ...")
    runs.clear()

    # save the runs again (removes files from disk)
    input("Press Enter to start saving loaded instance ...")
    dman.save('runs', runs, verbose=True)



if __name__ == '__main__':
    main()