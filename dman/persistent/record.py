import os

from dataclasses import asdict, dataclass, field, is_dataclass
from typing import Any
import uuid
from dman.persistent.serializables import Unserializable, deserialize, is_serializable, serializable, BaseContext, serialize
from dman.utils.smartdataclasses import AUTO, overrideable
from dman.persistent.storables import NoFile, is_storable, storable_type, read, unreadable, write


REMOVE = '__remove__'


@dataclass
class RecordContext(BaseContext):
    path: os.PathLike
    parent: 'RecordContext' = field(default=None, repr=False)
    children: dict = field(default_factory=dict, repr=False, init=False)

    def track(self, *args, **kwargs):
        if self.parent is None:
            raise RuntimeError('cannot track root repository')
        self.parent.open()
        return self

    def untrack(self, *args, **kwargs):
        self.parent.clean()
        return self
    
    def open(self):
        if not os.path.isdir(self.path):
            os.makedirs(self.path)
    
    def clean(self):
        if self.parent is None:
            return  # do not clean root
        if os.path.isdir(self.path) and len(os.listdir(self.path)) == 0:
            os.rmdir(self.path)
            self.parent.clean()
        
    def normalize(self, other: os.PathLike):
        return os.path.relpath(os.path.join(self.path, other), start=self.path)
    
    def join(self, other: os.PathLike) -> 'RecordContext':
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


def record_context(path: str):
    return RecordContext(path=path)


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
    context: BaseContext

    def __load__(self):
        # print(f'loading {self.type} from {self.path}')
        return read(self.type, self.path, context=self.context)
    
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
    
    def exists(self):
        return not isinstance(self._content, NoFile)

    @property
    def config(self):
        if self._evaluated:
            return self._config

        base = RecordConfig(stem=f'{uuid.uuid4()}', subdir='')
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
            return f'Record(None, target={self.config.target}{preload_str})'
        if is_unloaded(content):
            return f'Record({content}, target={self.config.target}{preload_str})'
        return f'Record({storable_type(content)}, target={self.config.target}{preload_str})'
    
    @staticmethod
    def __parse(config: RecordConfig, context: RecordContext):
        local = context.join(config.subdir)
        target = local.join(config.name)
        return local, target
    
    def __remove__(self, context: BaseContext):
        if isinstance(context, RecordContext):
            local, target = Record.__parse(self.config, context)
            # remove all subfiles of content
            remove(self.content, local)

            if os.path.exists(target.path):
                # remove file itself
                os.remove(target.path)
            target.untrack()

    def __serialize__(self, context: BaseContext):
        sto_type = storable_type(self._content)
        local, target = Record.__parse(self.config, context)
        if is_unloaded(self._content):
            unloaded: Unloaded = self._content
            sto_type = unloaded.type
        elif isinstance(context, RecordContext):
            target.track()
            write(self._content, target.path, context=local)
        else:
            return serialize(Unserializable(type='_ser__record', info='Invalid context passed.'), context)

        res = {
            'target': serialize(self.config, content_only=True),
            'sto_type': sto_type
        }
        if self.preload:
            res['preload'] = self.preload
        return res

    @classmethod
    def __deserialize__(cls, serialized: dict, context: BaseContext):
        config = deserialize(serialized.get('target', ''), ser_type=RecordConfig)
        sto_type = serialized.get('sto_type')
        preload = serialized.get('preload', False)

        local, target = Record.__parse(config, context)
        content = unreadable(target.path, type=sto_type)
        if isinstance(context, RecordContext):
            if preload:
                content = read(sto_type, target.path, context=local)
            else:
                content = Unloaded(sto_type, target.path, local)

        return cls(content=content, config=config, preload=preload)


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
    if name != AUTO and (stem != AUTO or suffix != AUTO):
        raise ValueError('either provide a name or suffix + stem.')

    config = RecordConfig.from_name(name=name, subdir=subdir)
    config = config << RecordConfig(stem=stem, suffix=suffix)
    return Record(content, config, preload)


def is_removable(obj):
    return hasattr(obj, REMOVE)


def remove(obj, context: BaseContext = None):
    if context is None:
        context = BaseContext()

    if is_removable(obj):
        inner_remove = getattr(obj, REMOVE, None)
        if inner_remove is not None:
            inner_remove(context)
        return

    if is_dataclass(obj):
        obj = asdict(obj)

    if isinstance(obj, (tuple, list)):
        for x in obj[:]:
            remove(x)
    elif isinstance(obj, dict):
        for k in obj.keys():
            remove(obj[k])

