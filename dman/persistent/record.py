import copy
import os

from dataclasses import asdict, dataclass, field, is_dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
import uuid
from dman.persistent.serializables import deserialize, is_serializable, serializable, BaseContext, serialize
from dman.persistent.smartdataclasses import AUTO, overrideable
from dman.persistent.storeables import is_storeable, storeable_type, read, write, is_storeable_type


REMOVE = '__remove__'


class TemporaryContext(TemporaryDirectory):
    def __enter__(self) -> 'RecordContext':
        return RecordContext(super().__enter__())
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        return super().__exit__(exc_type, exc_val, exc_tb)


@dataclass
class RecordContext(BaseContext):
    path: os.PathLike
    parent: 'RecordContext' = field(default=None, repr=False)
    children: dict = field(default_factory=dict, repr=False, init=False)

    def track(self, *args, **kwargs):
        if self.parent is None:
            raise RuntimeError('cannot track root repository')
        if not os.path.isdir(self.parent.path):
            os.makedirs(self.path)
    
    def clean(self):
        if self.parent is None:
            return  # do not clean root
        if os.path.isdir(self.path) and len(os.listdir(self.path)) == 0:
            os.rmdir(self.path)
            self.parent.clean()

    def untrack(self, *args, **kwargs):
        self.parent.clean()
        
    def normalize(self, other: os.PathLike):
        return os.path.relpath(os.path.join(self.path, other), start=self.path)
    
    def remove_child(self, other: 'RecordContext'):
        other = self.normalize(other.path)
        del self.children[other]

    @classmethod
    def class_join(cls, self: 'RecordContext', other: os.PathLike):
        # normalize
        other = self.normalize(other)
        if other == '.':
            return self

        head, tail = os.path.split(other)
        if len(head) > 0:
            return self.join(head).join(tail)

        res: cls = self.children.get(other, None)
        if res is not None:
            return res

        res = cls(os.path.join(self.path, other), parent=self)
        self.children[other] = res
        return res

    def join(self, other: os.PathLike) -> 'RecordContext':
        return self.__class__.class_join(self, other)


@serializable(name='__ser_rec_config')
@overrideable(frozen=True)
class RecordConfig:
    subdir: os.PathLike
    suffix: str
    stem: str

    @classmethod
    def from_name(cls, /, *, name: str, subdir: os.PathLike = AUTO):
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
    
    def __serialize__(self):
        res = {'stem': self.stem}
        if self.subdir != '' and self.subdir != AUTO:
            res['subdir'] = self.subdir
        if self.suffix != '' and self.suffix != AUTO:
            res['suffix'] = self.suffix
        return res
    
    @classmethod
    def __deserialize__(cls, serialized: dict):
        stem = serialized.get('stem')
        subdir = serialized.get('subdir', '')
        suffix = serialized.get('suffix', '')
        return cls(stem=stem, subdir=subdir, suffix=suffix)


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

    def __init__(self, content: Any, config: RecordConfig = None, preload: bool = False, context_options: dict = None):
        self._content = content

        if config is None:
            config = RecordConfig()
        self._config = config
        self._evaluated = False

        self.preload = preload

        if context_options is None:
            context_options = dict()
        self.context_options = context_options

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
        if not is_storeable(value):
            raise ValueError('expected storable type')
        self._content = value

    def __repr__(self) -> str:
        content = self._content
        if content is None:
            return f'Record(content=None, config={self.config}, preload={self.preload})'
        if is_unloaded(content):
            return f'Record(content={content}, command={self.config}, preload={self.preload})'
        return f'Record(content={storeable_type(content)}, command={self.config}, preload={self.preload})'
    
    @staticmethod
    def __parse(config: RecordConfig, context: RecordContext):
        local = context.join(config.subdir)
        target = local.join(config.name)
        return local, target
    

    def __remove__(self, context: BaseContext):
        if isinstance(context, RecordContext):
            local, target = Record.__parse(self.config, context)
            if os.path.exists(target.path):
                # remove all subfiles of content
                remove(self.content, local)
                
                # remove file itself
                os.remove(target.path)
                target.untrack(**self.context_options)

                # clean up the subdir (if empty)
                steps = Path(self.config.subdir).joinpath('_').parents
                for step in steps:
                    if step == '.': continue
                    step_dir = context.join(step).path
                    if len(os.listdir(step_dir)) == 0:
                        os.rmdir(step_dir)
                
        

    def __serialize__(self, context: BaseContext):
        sto_type = storeable_type(self._content)
        if is_unloaded(self._content):
            unloaded: Unloaded = self._content
            sto_type = unloaded.type
            local = unloaded.context
        elif isinstance(context, RecordContext):
            local, target = Record.__parse(self.config, context)
            if not os.path.isdir(local.path):
                os.makedirs(local.path)

            target.track(**self.context_options)
            write(self._content, target.path, context=local)
        else:
            raise RuntimeWarning(f'invalid context for serialization of record {self}')

        res = {
            'config': serialize(self.config, content_only=True),
            'sto_type': sto_type
        }
        if self.preload:
            res['preload'] = self.preload
        if len(self.context_options) > 0:
            res = res | self.context_options
        return res

    @classmethod
    def __deserialize__(cls, serialized: dict, context: BaseContext):
        serialized = copy.deepcopy(serialized)

        config = deserialize(serialized.pop('config', dict()), ser_type=RecordConfig)
        sto_type = serialized.pop('sto_type')
        preload = serialized.pop('preload', False)
        options = serialized

        if not is_storeable_type(sto_type):
            raise ValueError('record does not contain storeable type.')

        content = None
        if isinstance(context, RecordContext):
            local, target = Record.__parse(config, context)
            if preload:
                content = read(sto_type, target.path, context=local)
            else:
                content = Unloaded(sto_type, target.path, local)

        return cls(content=content, config=config, preload=preload, context_options=options)


def record(content: Any, /, *, stem: str = AUTO, suffix: str = AUTO, name: str = AUTO, subdir: os.PathLike = '', preload: str = False, **options):
    if name != AUTO and (stem != AUTO or suffix != AUTO):
        raise ValueError('either provide a name or suffix + stem.')

    config = RecordConfig.from_name(name=name, subdir=subdir)
    config = config << RecordConfig(stem=stem, suffix=suffix)
    return Record(content, config, preload, options)


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

