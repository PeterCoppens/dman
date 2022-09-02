from dataclasses import MISSING, dataclass, field
import os
from pathlib import Path
import sys
from contextlib import suppress
from typing import Type, Union
from dman import log


from dman.persistent.record import Context, Record, record
from dman.persistent.serializables import deserialize, is_serializable, serialize
from dman.persistent.storables import is_storable
from dman.utils import sjson
from dman.verbose import context
from dman.path import get_root_path, prepare


def store(key: str, obj, *, subdir: os.PathLike = '', cluster: bool = False, verbose: int = -1, gitignore: bool = True, generator: str = MISSING, base: os.PathLike = None, context: Type[Context] = Context):
    """
    Save a storable object.
        The path of the file is determined as described below.

            If the files are clustered then the path is ``<base>/<generator>/<subdir>/<key>/<key>.<ext>``
            If cluster is set to False then the path is ``<base>/<generator>/<subdir>/<key>.<ext>``

            When base is not provided then it is set to .dman if 
            it does not exist an exception is raised.

            When generator is not provided it will automatically be set based on 
            the location of the script relative to the .dman folder
            (again raising an exception if it is not found). For example
            if the script is located in ``<project-root>/examples/folder/script.py``
            and .dman is located in ``<project-root>/.dman``.
            Then generator is set to cache/examples:folder:script (i.e.
            the / is replaced by : in the output).

    :param str key: Key for the file.
    :param str obj: The serializable object.
    :param bool subdir: Specifies optional subdirectory in generator folder
    :param bool cluster: A subfolder ``key`` is automatically created when set to True.
    :param int verbose: Level of verbosity (1 == print log).
    :param bool gitignore: Automatically adds a .gitignore file to ignore the created object when set to True.
    :param str generator: Specifies the generator that created the file. 
    :param str base: Specifies the root folder (.dman by default).
    :param Type[Context] context: Serialization context.

    :raises RuntimeError: if either generator or base is not provided and no .dman folder exists.
    :raises ValueError: if the provided object is not storable
    """    
    if not is_storable(obj):
        raise ValueError('Can only store storable objects.')

    rec = record(obj, stem=key)
    dir = prepare(
        key, 
        suffix=rec.config.suffix, 
        subdir=subdir, 
        cluster=cluster, 
        verbose=verbose,
        gitignore=gitignore, 
        generator=generator, 
        base=base
    )
    ctx = context(dir)
    target = os.path.join(dir, rec.config.name)
    log.emphasize('store', f'storing {type(obj).__name__} with key {key} to "{target}".')
    ser = serialize(rec, context=ctx)
    log.emphasize('store', f'finished storing {type(obj).__name__} with key {key} to "{target}".')
    return ser
  

def save(key: str, obj, *, subdir: os.PathLike = '', cluster: bool = True, verbose: int = -1, gitignore: bool = True, generator: str = MISSING, base: os.PathLike = None, context: Type[Context] = Context):
    """
    Save a serializable object to a file.
        The path of the file is determined as described below.

            If the files are clustered then the path is ``<base>/<generator>/<subdir>/<key>/<key>.json``
            If cluster is set to False then the path is ``<base>/<generator>/<subdir>/<key>.json``

            When base is not provided then it is set to .dman if 
            it does not exist an exception is raised.

            When generator is not provided it will automatically be set based on 
            the location of the script relative to the .dman folder
            (again raising an exception if it is not found). For example
            if the script is located in ``<project-root>/examples/folder/script.py``
            and .dman is located in ``<project-root>/.dman``.
            Then generator is set to cache/examples:folder:script (i.e.
            the / is replaced by : in the output).

    :param str key: Key for the file.
    :param str obj: The serializable object.
    :param bool subdir: Specifies optional subdirectory in generator folder
    :param bool cluster: A subfolder ``key`` is automatically created when set to True.
    :param int verbose: Level of verbosity (1 == print log).
    :param bool gitignore: Automatically adds a .gitignore file to ignore the created object when set to True.
    :param str generator: Specifies the generator that created the file. 
    :param str base: Specifies the root folder (.dman by default).
    :param Type[Context] context: Serialization context.

    :raises RuntimeError: if either generator or base is not provided and no .dman folder exists.
    :raises ValueError: if the provided object is not serializable
    """    
    if not is_serializable(obj):
        raise ValueError('Can only save serializable objects.')

    dir = prepare(
        key, 
        suffix='.json', 
        subdir=subdir, 
        cluster=cluster, 
        verbose=verbose,
        gitignore=gitignore, 
        generator=generator, 
        base=base
    )
    ctx = context(dir)
    target = os.path.join(dir, key+'.json')
    log.emphasize(f'saving {type(obj).__name__} with key {key} to "{target}".', 'save')
    ser = serialize(obj, context=ctx)
    with open(target, 'w') as f:
        sjson.dump(ser, f, indent=4)
    log.emphasize(f'finished saving {type(obj).__name__} with key {key} to "{target}".', 'save')
    return ser


def load(key: str, *, default=MISSING, default_factory=MISSING, subdir: os.PathLike = '', cluster: bool = True, verbose: int = -1, gitignore: bool = True, generator: str = MISSING, base: os.PathLike = None, context: Type[Context] = Context):
    """
    Load a serializable or storable object from a file.
        A default value can be provided, which is returned when no file is found.
        Similarly default_factory is a function without arguments that 
        is called instead of default. If both default and default_factory
        are specified then the value in default is returned.

        The path of the file is determined as described below.

            If the files are clustered then the path is ``<base>/<generator>/<subdir>/<key>/<key>.json``
            If cluster is set to False then the path is ``<base>/<generator>/<subdir>/<key>.json``

            When base is not provided then it is set to .dman if 
            it does not exist an exception is raised.

            When generator is not provided it will automatically be set based on 
            the location of the script relative to the .dman folder
            (again raising an exception if it is not found). For example
            if the script is located in ``<project-root>/examples/folder/script.py``
            and .dman is located in ``<project-root>/.dman``.
            Then generator is set to cache/examples:folder:script (i.e.
            the / is replaced by : in the output).

        If the object is storable, it will automatically be wrapped in a 
        record before serialization. 

    :param str key: Key for the file.
    :param default: Default value.
    :param default_factory: Method with no argument that produces the default value.
    :param bool subdir: Specifies optional subdirectory in generator folder
    :param bool cluster: A subfolder ``key`` is automatically created when set to True.
    :param int verbose: Level of verbosity (1 == print log).
    :param bool gitignore: Automatically adds a .gitignore file to ignore the created object when set to True.
    :param str generator: Specifies the generator that created the file. 
    :param str base: Specifies the root folder (.dman by default).
    :param Type[Context] context: Serialization context.

    :returns: Loaded object or default value if file does not exist.

    :raises RuntimeError: if either generator or base is not provided and no .dman folder exists.
    """
    dir = prepare(
        key, 
        suffix='.json', 
        subdir=subdir, 
        cluster=cluster, 
        verbose=verbose,
        gitignore=gitignore, 
        generator=generator, 
        base=base
    )
    ctx = context(dir)
    target = os.path.join(dir, key+'.json')

    if not os.path.exists(target):
        log.emphasize(f'file not available at "{target}", using default', 'load')
        if default is MISSING and default_factory is MISSING:
            raise FileNotFoundError(f'could not find tracked file "{target}".')
        elif default is MISSING:
            return default_factory()
        else:
            return default

    log.emphasize(f'loading with key {key} from "{target}".', 'load')
    with open(target, 'r') as f:
        ser = sjson.load(f)
    res = deserialize(ser, context=ctx)
    log.emphasize(f'finished loading with key {key} from "{target}".', 'load')
    return res


class Track:
    def __init__(self, key: str, default, default_factory, subdir: os.PathLike, cluster: bool, verbose: int, gitignore: bool, generator: str, base: os.PathLike, context: Type[Context]) -> None:
        self.key = key
        self._content = None
        self.default = default
        self.default_factory = default_factory
        self.subdir = subdir
        self.cluster = cluster
        self.gitignore = gitignore
        self.generator = generator
        self.base = base
        self.verbose = verbose
        self.context = context

    @property
    def content(self):
        if self._content is None: self.load()
        return self._content

    def save(self, unload: bool = False):
        save(self.key, self._content, subdir=self.subdir, gitignore=self.gitignore,
                generator=self.generator, base=self.base, cluster=self.cluster, verbose=self.verbose, context=self.context)
        if unload: return self.load()
    
    def load(self):
        self._content = load(self.key, default=self.default, 
            default_factory=self.default_factory, subdir=self.subdir, 
            generator=self.generator, base=self.base, cluster=self.cluster, 
            gitignore=self.gitignore, verbose=self.verbose, context=self.context)
        return self._content

    def __enter__(self):
        return self.load()
    
    def __exit__(self, *_):
        return self.save()


def track(key: str, *, default = MISSING, default_factory = MISSING, subdir: os.PathLike = '', cluster: bool = True, verbose: int = -1, gitignore: bool = True, generator: str = MISSING, base: os.PathLike = None, context: Type[Context] = Context):
    """
        Create track a serializable or storable object with a file.
            Ideally track is used as a context: i.e. ``with track(...) as obj: ...``.
            When the context is entered the object is loaded from a file 
            (or default value is returned as described below). When the context
            exits, then the file is saved.

            If the object is storable, it will automatically be wrapped in a 
            record before serialization. 

            The path of the file is determined as described below.

                If the files are clustered then the path is ``<base>/<generator>/<subdir>/<key>/<key>.json``
                If cluster is set to False then the path is ``<base>/<generator>/<subdir>/<key>.json``

                When base is not provided then it is set to .dman if 
                it does not exist an exception is raised.

                When generator is not provided it will automatically be set based on 
                the location of the script relative to the .dman folder
                (again raising an exception if it is not found). For example
                if the script is located in ``<project-root>/examples/folder/script.py``
                and .dman is located in ``<project-root>/.dman``.
                Then generator is set to cache/examples:folder:script (i.e.
                the / is replaced by : in the output).

        :param str key: Key for the file.
        :param default: Default value.
        :param default_factory: Method with no argument that produces the default value.
        :param bool subdir: Specifies optional subdirectory in generator folder
        :param bool cluster: A subfolder ``key`` is automatically created when set to True.
        :param int verbose: Level of verbosity (1 == print log).
        :param bool gitignore: Automatically adds a .gitignore file to ignore the created object when set to True.
        :param str generator: Specifies the generator that created the file. 
        :param str base: Specifies the root folder (.dman by default).
        :param Type[Context] context: Serialization context.

        :raises RuntimeError: if either generator or base is not provided and no .dman folder exists.
    """
    return Track(key, default, default_factory, subdir, cluster, verbose, gitignore, generator, base, context)
        
