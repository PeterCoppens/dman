import os

from dataclasses import asdict, dataclass, field, is_dataclass
from typing import Any
import uuid
from dman import log
from dman.persistent.serializables import BaseInvalid, deserialize, is_serializable, serializable, BaseContext, serialize
from dman.persistent.serializables import ExcUndeserializable, ExcUnserializable, Unserializable, Undeserializable
from dman.utils.smartdataclasses import AUTO, overrideable
from dman.persistent.storables import is_storable, storable_type, read, write


REMOVE = '__remove__'


@serializable(name='__no_file')
class NoFile(ExcUndeserializable):
    def __repr__(self):
        return f'NoFile: {self.type}'


@serializable(name='__un_writable')
class UnWritable(Unserializable):
    def __repr__(self):
        return f'UnWritable: {self.type}'


@serializable(name='__exc_un_writable')
class ExcUnWritable(ExcUnserializable):
    def __repr__(self):
        return f'UnWritable: {self.type}'


@serializable(name='__un_readable')
class UnReadable(Undeserializable):
    def __repr__(self):
        return f'UnReadable: {self.type}'


@serializable(name='__exc_un_readable')
class ExcUnReadable(ExcUndeserializable):
    def __repr__(self):
        return f'UnReadable: {self.type}'


class Context(BaseContext):
    def __init__(self, path: os.PathLike, parent: 'Context' = None, children: dict = None, validate: bool = False):
        super().__init__(validate=validate)
        self.path = path
        self.parent = parent
        self.children = dict() if children is None else children

    def touch(self):
        self.parent.open()
        return self

    def write(self, storable):
        if self.parent is None:
            res =  UnWritable(type=type(storable), info='Cannot write to root directory.')
            self._process_invalid('An error occurred while writing.', res)
            return res
        self.touch()
        try:
            log.io(f'writing to file: "{self.path}".', 'context')
            write(storable, self.path, self.parent)
            return None
        except Exception:
            res = ExcUnWritable(
                type=type(storable), info='Exception encountered while writing.'
            )
            self._process_invalid('An error occurred while writing.', res)
            return res

    def read(self, sto_type):
        if self.parent is None:
            res = UnReadable(type=sto_type, info='Cannot read root directory.')
            self._process_invalid('An error occurred while writing.', res)
            return res
        try:
            log.io(f'reading from file: "{self.path}".', 'context')
            return read(sto_type, self.path, self.parent)
        except FileNotFoundError:
            res = NoFile(type=sto_type, info='Missing File.')
            self._process_invalid('An error occurred while writing.', res)
            return res
        except Exception:
            res = ExcUnReadable(
                type=sto_type, info='Exception encountered while reading.'
            )
            self._process_invalid('An error occurred while writing.', res)
            return res

    def delete(self, obj, remove: bool = True):
        if remove:
            self.parent.remove(obj)
        if self.parent is None:
            raise RuntimeError('Cannot delete root repository')
        if os.path.exists(self.path):
            log.io(f'deleting file: "{self.path}".', 'context')
            os.remove(self.path)
        self.parent.clean()

    def remove(self, obj):
        with log.layer(type(obj).__name__, 'removing', type(obj).__name__):
            if is_removable(obj):
                inner_remove = getattr(obj, REMOVE, None)
                if inner_remove is not None:
                    inner_remove(self)
                return

            if is_dataclass(obj):
                obj = asdict(obj)

            if isinstance(obj, (tuple, list)):
                for x in obj[:]:
                    remove(x, self)
            elif isinstance(obj, dict):
                for k in obj.keys():
                    remove(obj[k], self)
    
    def open(self):
        if not os.path.isdir(self.path):
            log.io(f'creating directory "{self.path}".')
            os.makedirs(self.path)
    
    def clean(self):
        if self.parent is None:
            return  # do not clean root
        if os.path.isdir(self.path) and len(os.listdir(self.path)) == 0:
            log.io(f'removing empty directory "{self.path}".')
            os.rmdir(self.path)
            self.parent.clean()
        
    def normalize(self, other: os.PathLike):
        return os.path.relpath(os.path.join(self.path, other), start=self.path)
    
    def join(self, other: os.PathLike) -> 'Context':
        # normalize
        other = self.normalize(other)
        if other == '.':
            return self

        head, tail = os.path.split(other)
        if len(head) > 0:
            return self.join(head).join(tail)

        res = self.children.get(other, None)
        if res is not None:
            return res

        res = self.__class__(os.path.join(self.path, other), parent=self)
        self.children[other] = res
        return res


def context(path: str = None, /, *, verbose: int = -1, validate: bool = False):
    """Create a context factory.

    :param path (str): if specified a context instance at the path is provided. 
        Otherwise a factory is returned.
    :param verbose (int): verbosity level, defaults to -1
    :param validate (bool): validate the output, defaults to False
    """
    
    def context_factory(path):
        _verbose = verbose
        if verbose == True:
            _verbose = log.INFO
        if _verbose >= 0 and _verbose is not None:
            log.setLevel(_verbose)
        return Context(path=path, validate=validate)
    if path is None:
        return context_factory
    return context_factory(path)
        

@serializable(name='__ser_rec_config')
@overrideable(frozen=True)
class RecordConfig:
    subdir: os.PathLike
    suffix: str
    stem: str

    @classmethod
    def from_target(cls, /, *, target: str):
        subdir, name = os.path.split(target)
        return cls.from_name(name=name, subdir=subdir)

    @classmethod
    def from_name(cls, /, *, name: str, subdir: os.PathLike = AUTO):
        if name == AUTO:
            return cls(subdir=subdir)

        split = name.split('.')
        if len(split) == 1:
            split.append('')

        *stem, suffix = split
        if len(suffix) > 0: suffix = '.' + suffix
        return cls(subdir=subdir, suffix=suffix, stem=''.join(stem))

    @property
    def name(self):
        if self.stem == AUTO:
            return AUTO
        return self.stem + ('' if self.suffix == AUTO else self.suffix)
    
    @property
    def target(self):
        return os.path.normpath(os.path.join(".", self.subdir, self.name))
    
    def __serialize__(self):
        return self.target
    
    @classmethod
    def __deserialize__(cls, serialized):
        return cls.from_target(target=serialized)


def is_unloaded(obj):
    return isinstance(obj, Unloaded)


@dataclass
class Unloaded:
    type: str
    path: str
    base: str
    context: Context

    def __load__(self):
        return self.context.read(self.type)
    
    def __repr__(self) -> str:
        return f'UL[{self.type}]'


@serializable(name='_ser__record')
class Record:
    EXTENSION = '__ext__'

    def __init__(self, content: Any, config: RecordConfig = None, preload: bool = False):
        self._content = content

        if config is None:
            config = RecordConfig()
        self._config = config
        self._evaluated = False

        self.preload = preload
        self.exception = None
    
    def exists(self):
        return not isinstance(self._content, NoFile)

    @property
    def config(self):
        if self._evaluated:
            return self._config

        base = RecordConfig(stem=f'{uuid.uuid4()}', subdir=f'{uuid.uuid4()}')
        if is_serializable(self._content) or is_dataclass(self._content):
            base = base << RecordConfig(suffix='.json')

        request = RecordConfig(suffix=getattr(
            self._content, Record.EXTENSION, AUTO))

        self._config: RecordConfig = base << request << self._config
        self._evaluated = True

        return self._config

    @property
    def content(self):
        if is_unloaded(self._content):
            ul: Unloaded = self._content
            log.emphasize('record', f'loading {str(self)}')
            self._content = ul.__load__()
            log.emphasize('record', f'finished loading {str(self)}')
        return self._content

    @content.setter
    def content(self, value: Any):
        if not is_storable(value):
            raise ValueError('expected storable type')
        self._content = value

    def __repr__(self) -> str:
        content = self._content
        preload_str = ''
        if self.preload:
            preload_str=', preload'
        if content is None:
            return f'Record(None, target={self.config.target}{preload_str})'
        if is_unloaded(content):
            return f'Record({content}, target={self.config.target}{preload_str})'
        return f'Record({storable_type(content)}, target={self.config.target}{preload_str})'
    
    @staticmethod
    def __parse(config: RecordConfig, context: Context):
        local = context.join(config.subdir)
        target = local.join(config.name)
        return target
    
    def __remove__(self, context: BaseContext):
        if isinstance(context, Context):
            target = Record.__parse(self.config, context)
            # remove all subfiles of content
            content = self._content
            if is_unloaded(content):
                log.info('content unloaded: loading ...', 'record')
                ul: Unloaded = content
                content = ul.__load__()
                log.info('finished load.', 'record')
            if isinstance(content, BaseInvalid):
                log.error('loaded content is invalid:', 'record')
                log.error(content, 'record')
            else:
                target.delete(content)

    def __serialize__(self, context: BaseContext):
        sto_type = storable_type(self._content)
        target = Record.__parse(self.config, context)

        if is_unloaded(self._content):
            unloaded: Unloaded = self._content
            sto_type = unloaded.type
            log.info(f'serializing record with storable type: {sto_type} ...', 'record')
            if isinstance(context, Context) and unloaded.base != context.path:
                self.content
        else:
            log.info(f'serializing record with storable type: {sto_type} ...', 'record')


        if not is_unloaded(self._content):
            if not isinstance(context, Context):
                return serialize(Unserializable(type='_ser__record', info='Invalid context passed.'), context)
            log.info('content is loaded, executing write ...', 'record')
            exc = target.write(self._content)
            if exc is not None:
                log.error(f'exception encountered while writing to {target.path}.', 'record')
                self.exception = exc

        res = {
            'target': serialize(self.config, content_only=True),
            'sto_type': sto_type
        }
        if self.preload:
            res['preload'] = self.preload
        if self.exception is not None:
            res['exception'] = serialize(self.exception, context)
        
        return res

    @classmethod
    def __deserialize__(cls, serialized: dict, context: BaseContext):
        log.info('deserializing record ...', f'record')
        config: RecordConfig = deserialize(
            serialized.get('target', ''), ser_type=RecordConfig
        )
        sto_type = serialized.get('sto_type')
        preload = serialized.get('preload', False)
        exception = deserialize(serialized.get('exception', None))
        if isinstance(exception, BaseInvalid):
            log.error('error during earlier serialization:', 'record')
            log.error(exception, 'record')

        content = Undeserializable(type=sto_type, info=f'Could not read {config.target}')
        if isinstance(context, Context):
            target = Record.__parse(config, context)
            if preload:
                log.info('preload enabled, loading from file ...', 'record')
                content = target.read(sto_type)
            else:
                log.info('preload disabled, load deferred', 'record')
                log.info(f'path: "{target.path}"', f'record')
                content = Unloaded(sto_type, target.path, context=target, base=context.path)

        out = cls(content=content, config=config, preload=preload)
        out.exception = exception
        return out


def recordconfig(*, stem: str = AUTO, suffix: str = AUTO, name: str = AUTO, subdir: os.PathLike = ''):
    if name != AUTO and (stem != AUTO or suffix != AUTO):
        raise ValueError('either provide a name or suffix + stem.')

    config = RecordConfig.from_name(name=name, subdir=subdir)
    return config << RecordConfig(stem=stem, suffix=suffix)


def record(content: Any, /, *, stem: str = AUTO, suffix: str = AUTO, name: str = AUTO, subdir: os.PathLike = '', preload: str = False):
    """
    Wrap a storable object in a serializable record.
        The target path is specified as (the ``stem+suffix`` option takes precedence):
        
        * ``./subdir/stem+suffix`` or
        * ``./subdir/name``.

    :param content:         The storable object.
    :param str stem:        The stem of a file.
    :param str suffix:      The suffix or extension of the file (e.g. ``'.json'``).
    :param str name:        The full name of the file.
    :param str subdir:      The subdirectory in which to store te file. 
    :param bool preload:    When ``True`` the file will be loaded during deserialization.

    :raises ValueError:     if a name and a stem and/or suffix are specified. 
    """
    return Record(content, recordconfig(stem=stem, suffix=suffix, name=name, subdir=subdir), preload)


def is_removable(obj):
    return hasattr(obj, REMOVE)


def remove(obj, context: Context = None):
    if not isinstance(context, Context):
        return
    context.remove(obj)

