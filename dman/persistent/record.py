import os

from dataclasses import MISSING, dataclass, is_dataclass
from tempfile import TemporaryDirectory
from typing import Any
import uuid
from dman.persistent.serializables import is_serializable, serializable, BaseContext, serialize, deserialize
from dman.persistent.smartdataclasses import AUTO, overrideable
from dman.persistent.storeables import is_storeable, storeable_type, read, write, is_storeable_type


class TemporaryContext(TemporaryDirectory):
    def __enter__(self):
        return RecordContext(super().__enter__())
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        return super().__exit__(exc_type, exc_val, exc_tb)


@dataclass(frozen=True)
class RecordContext(BaseContext):
    path: str

    def join(self, other: str):
        return RecordContext(os.path.join(self.path, other))

    @property
    def parent(self):
        return os.path.dirname(self.path)

    @property
    def name(self):
        return os.path.dirname(self.name)


@serializable(name='__ser_rec_config')
@overrideable(frozen=True)
class RecordConfig:
    subdir: str
    suffix: str
    stem: str

    @classmethod
    def from_name(cls, /, *, name: str, subdir: str = AUTO):
        split = name.split('.')
        if len(split) == 1:
            split.append('')

        *stem, suffix = split
        return cls(subdir=subdir, suffix=suffix, stem=''.join(stem))

    @property
    def name(self):
        if self.stem == AUTO or self.suffix == AUTO:
            return AUTO
        return self.stem + self.suffix


def is_unloaded(obj):
    return isinstance(obj, Unloaded)


@dataclass
class Unloaded:
    type: str
    path: str
    context: BaseContext

    def __load__(self):
        print(f'loading {self}')
        return read(self.type, self.path, context=self.context)


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

    @property
    def config(self):
        if self._evaluated:
            return self._config

        base = RecordConfig(stem=f'{uuid.uuid4()}', subdir='')
        if is_serializable(self._content) or is_dataclass(self._content):
            base = base << RecordConfig(suffix='.json')

        request = RecordConfig(suffix=getattr(
            self._content, Record.EXTENSION, AUTO))

        self._config: RecordConfig = base << self._config << request
        self._evaluated = True

        return self._config

    @property
    def content(self):
        if is_unloaded(self._content):
            ul: Unloaded = self._content
            return ul.__load__()
        return self._content

    @content.setter
    def content(self, value: Any):
        if not is_storeable(value):
            raise ValueError('expected storable type')
        self._content = value

    def __repr__(self) -> str:
        content = self._content
        if content is None:
            return f'Record(content=None, command={self.config}, preload={self.preload})'
        if is_unloaded(content):
            return f'Record(content={content}, command={self.config}, preload={self.preload})'
        return f'Record(content={storeable_type(content)}, command={self.config}, preload={self.preload})'
    
    @staticmethod
    def __parse(config: RecordConfig, context: RecordContext):
        local = context.join(config.subdir)
        path = local.join(config.name).path
        return local, path
        

    def __serialize__(self, context: BaseContext):
        if not is_unloaded(self._content) and isinstance(context, RecordContext):
            local, path = Record.__parse(self.config, context)
            write(self._content, path, context=local)

        sto_type = storeable_type(self._content)
        if is_unloaded(self._content):
            unloaded: Unloaded = self._content
            sto_type = unloaded.type
            local = unloaded.context

        return {
            'config': serialize(self.config, context),
            'sto_type': sto_type,
            'preload': self.preload,
            'context': local.path
        }

    @classmethod
    def __deserialize__(cls, serialized: dict, context: BaseContext):
        config: RecordConfig = deserialize(serialized['config'])
        sto_type = serialized['sto_type']
        preload = serialized['preload']

        if not is_storeable_type(sto_type):
            raise ValueError('record does not contain storeable type.')

        content = None
        if isinstance(context, RecordContext):
            local, path = Record.__parse(config, context)
            if preload:
                content = read(sto_type, path, context=local)
            else:
                content = Unloaded(sto_type, path, local)

        return cls(content=content, config=config, preload=preload)


def record(content: Any, /, *, stem: str = AUTO, suffix: str = AUTO, name: str = AUTO, subdir: str = '', preload: str = False):
    if name != AUTO and (stem != AUTO or suffix != AUTO):
        raise ValueError('either provide a name or suffix + stem.')

    config = RecordConfig.from_name(name=name, subdir=subdir)
    config = config << RecordConfig(stem=stem, suffix=suffix)
    return Record(content, config, preload)
