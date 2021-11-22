from dataclasses import dataclass, field, is_dataclass
from typing import Any
from dman.persistent.context import Context, ContextCommand
from dman.persistent.serializables import is_serializable, serializable, BaseContext, serialize, deserialize
from dman.persistent.storeables import is_storeable, storeable_type, read, write, is_storeable_type


def isunloaded(obj):
    return isinstance(obj, Unloaded)


@dataclass
class Unloaded:
    type: str
    context: 'Context' = field(default=None, repr=False)

    def __load__(self):
        print(f'loading {self}')
        return read(self.type, self.context.resolve())


@serializable(name='_ser__record')
class Record:    
    COMMAND = '__cmd__'
    def __init__(self, content: Any, command: ContextCommand = None, preload: bool = False):
        self._content = content
        if command is None:
            command = ContextCommand()
        self.command = command
        self.preload = preload

    @property
    def content(self):
        if isunloaded(self._content):
            ul: Unloaded = self._content
            return ul.__load__()
        return self._content
    
    @content.setter
    def content(self, value: Any):
        if not is_storeable(value):
            raise ValueError('expected storable type')
        self._content = value

    def evaluate(self, context: Context) -> Context:
        base = ContextCommand()
        if is_serializable(self._content) or is_dataclass(self._content):
            base = ContextCommand(suffix='.json')
        command: ContextCommand = base << self.command << getattr(self._content, Record.COMMAND, ContextCommand())
        return command.evaluate(context)
    
    def __repr__(self) -> str:
        content = self._content
        if content is None:
            return f'Record(content=None, command={self.command}, preload={self.preload})'
        if isunloaded(content):
            return f'Record(content={content}, command={self.command}, preload={self.preload})'
        return f'Record(content={storeable_type(content)}, command={self.command}, preload={self.preload})'
    
    def __serialize__(self, context: BaseContext):
        content = self._content
        content_type = storeable_type(content)
        local = context

        if not isunloaded(content) and isinstance(context, Context):
            local = self.evaluate(context)
            write(content, local.resolve(), context=local)
        
        if isunloaded(content):
            unloaded: Unloaded = content
            local = unloaded.context
            content_type = unloaded.type

        return {
            'context': serialize(local, context),
            'type': content_type,
            'preload': self.preload
        }

    @classmethod
    def __deserialize__(cls, serialized: dict, context: BaseContext):
        local: Context = deserialize(serialized['context'], context)
        sto_type = serialized['type']
        preload = serialized['preload']

        if not is_storeable_type(sto_type):
            raise ValueError('record does not contain storeable type.')

        content = None
        if isinstance(local, Context):
            if preload:
                content = read(sto_type, local.resolve(), local)
            else:
                content = Unloaded(sto_type, local)

        return cls(content=content, command=ContextCommand.from_context(local), preload=preload)


def record(content: Any, /, *, command: ContextCommand = None, preload: str = False):
    return Record(content, command, preload)