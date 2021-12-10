from pathlib import Path
from typing import Union

from dataclasses import dataclass, field
from dman.persistent.smartdataclasses import AUTO, overrideable
from dman.persistent.serializables import SER_CONTENT, serializable, serialize, BaseContext

import os
import uuid

ROOT_FOLDER = '.dman'


def get_root_path():
    root_path = None
    cwd = Path.cwd()

    current_path = cwd
    while root_path is None:
        if current_path.joinpath(ROOT_FOLDER).is_dir():
            root_path = current_path.joinpath(ROOT_FOLDER)
        else:
            current_path = current_path.parent
            if current_path.parent == current_path:
                return cwd

    return root_path


@serializable(name='__ser_ctx')
class Context(BaseContext):
    def __init__(self, path: Union[str, Path], parent: 'Context'):
        self.path = Path(path)
        self.parent = parent
    
    def resolve(self) -> Path:
        return self.parent.resolve().joinpath(self.path)
        
    def joinpath(self, other: Union[str, Path]):
        return Context(path=other, parent=self)
    
    def __repr__(self) -> str:
        return f'Context(path={self.path.__repr__()})'
    
    def __serialize__(self, context: 'Context'):
        if self is context:
            return {'path': '.'}

        if self.parent is not context:
            raise ValueError('invalid context for serialization')

        return {'path': str(self.path)}
    
    @classmethod
    def __deserialize__(cls, serialized: dict, context: 'Context'):
        if serialized['path'] == '.':
            return context
        return cls(path=serialized['path'], parent=context)
    

class RootContext(Context):
    def __init__(self, path: Union[Path, str] = None):
        if path is None: path = get_root_path()
        Context.__init__(self, path=path, parent=None)

    @classmethod
    def at_script(cls):
        import sys
        return cls(path=Path(sys.argv[0]).parent)
    
    def resolve(self):
        return self.path.resolve()
    
    def __serialize__(self, context: 'Context'):
        raise RuntimeError('cannot serialize root context')


def root():
    return RootContext()


@serializable(name='__ser_ctx_cmd')
@overrideable()
class ContextCommand:
    subdir: str
    suffix: str
    stem: str

    @classmethod
    def from_name(cls, /, *, name: str, subdir: str = AUTO):
        if name != AUTO:
            split = name.split('.')
            if len(split) == 1:
                stem = split
                suffix = ''
            else:
                *stem, suffix = split
                suffix = '.' + suffix

            stem = ''.join(stem)
        else:
            stem, suffix = AUTO, AUTO

        return cls(subdir=subdir, suffix=suffix, stem=stem)
    
    @classmethod
    def from_context(cls, context: Context):
        return cls.from_name(subdir=context.path.parent, name=context.path.name)

    @property
    def name(self):
        if self.stem == AUTO or self.suffix == AUTO:
            return AUTO
        return self.stem + self.suffix
            
    def evaluate(self, ctx: Context):
        subdir = self.subdir
        if subdir == AUTO:
            subdir = ''
        if self.stem == AUTO:
            stem = f'content_{uuid.uuid4()}'
            name = stem
            if self.suffix != AUTO:
                name = name + self.suffix
        else:
            name = self.name
            
        return ctx.joinpath(Path(subdir).joinpath(name))

def command(*, subdir: str = AUTO, name: str = AUTO):
    return ContextCommand.from_name(subdir=subdir, name=name)

def clear(context: Context):
    for file in context.resolve().glob('*'):
        if file.is_dir():
            clear(context.joinpath(file))
            file.rmdir()
        else:
            file.unlink()

@dataclass
class ContextManager:
    context: Context = field(default_factory=root)
    template: ContextCommand = field(default_factory=ContextCommand)
    
    def request(self, cmd: ContextCommand):
        req: ContextCommand = self.template << cmd  # get the completed command
        ctx = req.evaluate(self.context)

        # spawn parent directory of resulting context
        if not ctx.resolve().parent.exists():
            os.makedirs(ctx.resolve().parent)

        if not ctx.resolve().exists():
            ctx.resolve().touch()

        return ctx


GITIGNORE = '.gitignore'

@dataclass
class GitContextManager(ContextManager):
    ignored: set = field(default_factory=set, init=False, repr=False)
    opened: bool = field(default=False, init=False, repr=False)

    @classmethod
    def from_manager(cls, mgr: ContextManager):
        return cls(mgr.context, mgr.template)
    
    def request(self, cmd: ContextCommand, ignore: bool = True):
        ctx = ContextManager.request(self, cmd)
        self.ignored.add(str(ctx.path))
        return ctx
    
    @property
    def gitignore(self):
        ctx = ContextManager.request(self, ContextCommand.from_name(name=GITIGNORE))
        return ctx.resolve()
    
    def open(self):
        if self.opened: return

        with self.gitignore.open() as f:
            self.ignored = set([line[:-1] for line in f.readlines()])
        
        self.opened = True
        return self
    
    def close(self):
        if not self.opened: return

        if len(self.ignored) > 0:
            self.ignored.add('.gitignore')
            with self.gitignore.open('w') as f:
                f.writelines((line + '\n' for line in self.ignored))
        
        self.opened = False
        return self
    
    def __enter__(self):
        return self.open()

    def __exit__(self, exception_type, exception_value, traceback):
        self.close()