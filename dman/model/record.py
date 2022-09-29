import copy
import os

from dataclasses import asdict, dataclass, is_dataclass
from typing import Any
import uuid
from dman.core import log
from dman.core.serializables import SER_CONTENT, SER_TYPE, BaseInvalid, deserialize, is_serializable, serializable, BaseContext, serialize, ValidationError
from dman.core.serializables import ExcUndeserializable, ExcUnserializable, Unserializable, Undeserializable
from dman.utils.smartdataclasses import AUTO, overrideable
from dman.core.storables import is_storable, storable_type, read, write
from dman.core.path import logger_context, normalize_path


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
    def __init__(self, directory: os.PathLike, parent: 'Context' = None, children: dict = None, validate: bool = None):
        super().__init__(validate=validate)
        self.directory = directory
        self.parent = parent
        self.children = dict() if children is None else children
    
    def _serialize__list(self, ser: list):
        res = []
        is_model = False
        for itm in ser:
            if is_storable(itm):
                itm = record(itm)
                is_model = True
            res.append(self.serialize(itm))
        if is_model:
            res = {SER_TYPE: '_ser__mlist', SER_CONTENT: {'store': res}}
        return res
    
    def _serialize__dict(self, ser: dict):
        res = {}
        is_model = False
        for k, v in ser.items():
            if is_storable(v):
                v = record(v)
                is_model = True
            k = self.serialize(k)
            res[k] = self.serialize(v)
        if is_model:
            res = {SER_TYPE: '_ser__mdict', SER_CONTENT: {'store': res}}
        return res
    
    def _serialize__object(self, ser):
        return super()._serialize__object(ser)

    def write(self, target: str, storable):
        self.open()
        try:
            path = os.path.join(self.directory, target)
            log.io(f'writing to file: "{normalize_path(path)}".', 'context')
            write(storable, path, self)
            return None
        except Exception as e:
            if isinstance(e, ValidationError):
                raise e
            res = ExcUnWritable(
                type=type(storable), info='Exception encountered while writing.'
            )
            self._process_invalid('An error occurred while writing.', res)
            return res

    def read(self, target: str, sto_type):
        try:
            path = os.path.join(self.directory, target)
            log.io(f'reading from file: "{normalize_path(path)}".', 'context')
            return read(sto_type, path, self)
        except FileNotFoundError:
            res = NoFile(type=sto_type, info='Missing File.')
            self._process_invalid('An error occurred while writing.', res)
            return res
        except Exception as e:
            if isinstance(e, ValidationError):
                raise e
            res = ExcUnReadable(
                type=sto_type, info='Exception encountered while reading.'
            )
            self._process_invalid('An error occurred while writing.', res)
            return res

    def delete(self, target: str):
        path = os.path.join(self.directory, target)
        if os.path.exists(path):
            log.io(f'deleting file: "{normalize_path(path)}".', 'context')
            os.remove(path)
        self.clean()

    def remove(self, obj):
        original = obj
        if is_removable(obj):
            with log.layer(type(obj).__name__, 'remove'):
                inner_remove = getattr(obj, REMOVE, None)
                if inner_remove is not None:
                    inner_remove(self)
                return

        if is_dataclass(obj):
            obj = asdict(obj)
        
        if isinstance(obj, (tuple, list)):
            with log.layer(type(obj).__name__, 'remove'):
                for x in obj[:]:
                    self.remove(x)
        elif isinstance(obj, dict):
            with log.layer(type(original).__name__, 'remove'):
                for k in obj.keys():
                    self.remove(obj[k])
    
    def open(self):
        if not os.path.isdir(self.directory):
            log.io(f'creating directory "{normalize_path(self.directory)}".')
            os.makedirs(self.directory)
    
    def clean(self):
        if self.parent is None:
            return  # do not clean root
        if os.path.isdir(self.directory) and len(os.listdir(self.directory)) == 0:
            log.io(f'removing empty directory "{normalize_path(self.directory)}".')
            os.rmdir(self.directory)
            self.parent.clean()
        
    def normalize(self, other: os.PathLike):
        return os.path.relpath(os.path.join(self.directory, other), start=self.directory)
    
    def make_child(self, other: os.PathLike):
        res = self.__class__(os.path.join(self.directory, other), parent=self)
        self.children[other] = res
        res.validate = self.validate
        return res
    
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

        return self.make_child(other)


class _GenerateContext(Context):
    def __init__(self, verbose: bool, **kwargs):
        super().__init__(**kwargs)
        self._logger_context = logger_context(verbose)
        self._logger_context.__enter__()

    def __enter__(self):
        return self
    
    def __exit__(self, *_):
        self._logger_context.__exit__(*_)
    
    def make_child(self, other: os.PathLike):
        res = Context(os.path.join(self.directory, other), parent=self)
        self.children[other] = res
        res.validate = self.validate
        return res


def context(directory: str = None, *, verbose: bool = None, validate: bool = None):
    """Create a context factory.

    :param directory (str): if specified a context instance at the directory is provided. 
        Otherwise a factory is returned.
    :param verbose (int): verbosity level, defaults to the current level
    :param validate (bool): validate the output, defaults to False
    """
    return _GenerateContext(verbose, directory=directory, validate=validate)
        

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
    
    def __serialize__(self, context: Context):
        log.info(f'target={self.target}', 'record')
        return self.target
    
    @classmethod
    def __deserialize__(cls, serialized, context: Context):
        log.info(f'target={serialized}', 'record')
        return cls.from_target(target=serialized)


def is_unloaded(obj):
    return isinstance(obj, Unloaded)


@dataclass
class Unloaded:
    type: str
    target: str
    base: str
    context: Context

    @property
    def path(self):
        return os.path.join(self.base, self.target)

    def __load__(self):
        return self.context.read(self.target, self.type)
    
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
    def target(self):
        return self.config.target

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
            with log.layer(ul.type, 'deferred load'):
                self._content = ul.__load__()
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
            return f'Record(None, target={self.target}{preload_str})'
        if is_unloaded(content):
            return f'Record({content}, target={self.target}{preload_str})'
        return f'Record({storable_type(content)}, target={self.target}{preload_str})'
    
    @staticmethod
    def __parse(config: RecordConfig, context: Context):
        return config.name, context.join(config.subdir)
    
    def __remove__(self, context: BaseContext):
        if isinstance(context, Context):
            target, local = Record.__parse(self.config, context)
            # remove all subfiles of content
            if is_unloaded(self._content):
                ul: Unloaded = self._content
                with log.layer(ul.type, 'deferred load'):
                    self._content = ul.__load__()
            if isinstance(self._content, BaseInvalid):
                log.error('loaded content is invalid:', 'record')
                log.error(str(self._content), 'record')
            else:
                local.remove(self._content)  # remove contents
                local.delete(target)   # remove this file

    def __serialize__(self, context: BaseContext):
        sto_type = storable_type(self._content)
        target, local = Record.__parse(self.config, context)

        if is_unloaded(self._content):
            unloaded: Unloaded = self._content
            sto_type = unloaded.type
            log.info(f'serializing record with storable type: {sto_type} ...', 'record')
            if isinstance(context, Context) and unloaded.base != context.directory:
                self.content
        else:
            log.info(f'serializing record with storable type: {sto_type} ...', 'record')

        if not is_unloaded(self._content):
            if not isinstance(context, Context):
                return serialize(Unserializable(type='_ser__record', info='Invalid context passed.'), context)
            log.info('content is loaded, executing write ...', 'record')
            exc = local.write(target, self._content)
            if exc is not None:
                log.error(f'exception encountered while writing to {os.path.join(local.directory, target)}.', 'record')
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
            target, local = Record.__parse(config, context)
            if preload:
                log.info('preload enabled, loading from file ...', 'record')
                content = local.read(target, sto_type)
            else:
                log.info('preload disabled, load deferred', 'record')
                log.info(f'path: "{normalize_path(os.path.join(local.directory, target))}"', f'record')
                content = Unloaded(
                    sto_type, 
                    target, 
                    context.directory,
                    local
                )

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
        The target path is specified as:
        
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

