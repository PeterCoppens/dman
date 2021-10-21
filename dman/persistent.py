import json
import copy
import uuid

import numpy as np

from abc import ABC, abstractmethod
from dataclasses import dataclass, field, fields
import os
import shutil

from typing import Dict, Type, Union


def is_serializable(obj):
    if not hasattr(obj, 'type') or not hasattr(obj, 'serialize'):
        return False
    
    return obj.type in Serializable.data_types


def is_deserializable(record: dict):
    return Serializable.TYPE_KEY in record


class Serializable(ABC):
    TYPE_KEY = 'ser_type__'

    data_types: Dict[str, 'Serializable'] = {}
    type: str = 'Base'

    @classmethod
    def register(cls, data_type): 
        def decorator(subclass):
            subclass.type = data_type
            cls.data_types[data_type] = subclass
            return subclass
        
        return decorator
    
    def serialize(self):
        return {Serializable.TYPE_KEY: self.type}
    
    @classmethod
    def deserialize(cls, record: dict):
        rec = copy.copy(record)
        tp = rec.pop(Serializable.TYPE_KEY)
        return Serializable.data_types[tp].deserialize(rec)    


@Serializable.register('model')
class Model(Serializable):
    __no_serialize__ = []

    @classmethod
    def _serialize_inner(cls, obj):
        if is_serializable(obj):
            return obj.serialize()
        elif isinstance(obj, (tuple, list)):
            return type(obj)(*[cls._serialize_inner(v) for v in obj])
        elif isinstance(obj, dict):
            return type(obj)(
                (cls._serialize_inner(k), cls._serialize_inner(v)) 
                for k, v in obj.items() if v is not None
            )
        else:
            return copy.deepcopy(obj)

    def serialize(self):
        record = Serializable.serialize(self)
        for f in fields(self):
            if f.name not in Serializable.data_types[self.type].__no_serialize__:
                value = getattr(self, f.name)
                if is_serializable(value):
                    value = self._serialize_inner(value)
                record[f.name] = self._serialize_inner(value)
        
        return record

    @classmethod
    def _deserialize_inner(cls, obj):
        if isinstance(obj, (tuple, list)):
            return type(obj)(*[cls._deserialize_inner(v) for v in obj])
        elif isinstance(obj, dict) and is_deserializable(obj):
            return Serializable.deserialize(obj)
        elif isinstance(obj, dict):
            return type(obj)(
                (cls._deserialize_inner(k), cls._deserialize_inner(v))
                for k, v in obj.items() if v is not None
            )
        else:
            return obj
    
    @classmethod
    def deserialize(cls, record: dict):
        processed = copy.deepcopy(record)
        for k, v in processed.items():
            processed[k] = cls._deserialize_inner(v)

        return cls(**processed)

    @classmethod
    def register(cls, data_type):
        def decorator(subclass):
            subclass.type = data_type
            cls.data_types[data_type] = subclass
            return dataclass(subclass)
        
        return decorator


@Serializable.register('content-manager')
class ContentManager(Serializable):
    def __init__(self, directory: str, preload: bool = False, ignored: bool = True) -> None:
        self.directory = directory
        self.preload = preload
        self.ignored = ignored

        if not os.path.exists(self.directory):
            os.makedirs(self.directory)
        
        if self.ignored:
            self.ignore()

    def __repr__(self):
        return f'ContentManager(directory={self.directory}, preload={self.preload}, ignored={self.ignored})'
    
    def serialize(self):
        return {
            **Serializable.serialize(self), 
            'directory': self.directory,
            'preload': self.preload,
            'ignored': self.ignored
        }

    @classmethod
    def deserialize(cls, record: dict):
        return cls(record['directory'], record['preload'], record['ignored'])

    def write(self, content: Union['Content', 'Serializable'], filename: str):
        path = os.path.join(self.directory, filename)
        if isinstance(content, Content):
            content.write(path)  
        else:
            with open(path, 'w') as f:
                json.dump(content.serialize(), f, indent=4)      
                
        return path
    
    def load(self, filename: str, content_type: Type['Content'] = None, preload: bool = None):
        if preload is None: preload is self.preload

        path = os.path.join(self.directory, filename)
        if content_type is None:
            with open(path, 'r') as f:
                return Serializable.deserialize(json.load(f))

        content = ContentLoader(
            wrapped=content_type, 
            path=path
        )
        if preload:
            content = content.load()
        return content
    
    def getsub(self, directory: str, preload: bool = False, ignored: bool = False):
        return ContentManager(directory=os.path.join(self.directory, directory), preload=preload, ignored=ignored)

    def clear(self):
        shutil.rmtree(self.directory)
        os.makedirs(self.directory)
    
    def ignore(self):
        self.ignored = True
        with open(os.path.join(self.directory, '.gitignore'), 'w') as f:
            f.write('*')


@Serializable.register('content')
class Content(Serializable, ABC):
    PER_TYPE_KEY = 'per_type__'

    persistent_types: Dict[str, Type['Content']] = {}
    persistent_type: str = 'Base'

    @classmethod
    def register(cls, data_type): 
        def decorator(subclass):
            subclass.persistent_type = data_type
            cls.persistent_types[data_type] = subclass
            return subclass
        
        return decorator
    
    def serialize(self):
        return {**Serializable.serialize(self), Content.PER_TYPE_KEY: self.persistent_type}
    
    @classmethod
    def deserialize(cls, record: dict):
        return cls.persistent_types[record[cls.PER_TYPE_KEY]]

    @abstractmethod
    def write(self, path):
        pass

    @classmethod
    @abstractmethod
    def read(cls, path):
        pass
            

def isloaded(obj):
    return not isinstance(obj, ContentLoader)


class ContentLoader(Serializable):
    def __init__(self, wrapped: Type[Content], path: str) -> None:
        self.wrapped = wrapped
        self.path = path
        self.type = wrapped.type    # acts like its wrapped type (we do not register it)
    
    def __repr__(self) -> str:
        return f'ContentLoader(wrapped={str(self.type)}, path={str(self.path)})'

    def load(self):
        print(f'loading {self} ...')
        return self.wrapped.read(self.path)

    def serialize(self):
        return self.wrapped.serialize()
    
    @classmethod
    def deserialize(cls, record: dict):
        raise RuntimeError(f'record of type {record.type} cannot be deserialized as a ContentLoader')    


@Serializable.register('persistent')
class Persistent(Serializable):
    def __init__(self, filename: str, contentmgr: ContentManager, content: 'Content'):
        self.filename = filename
        self.contentmgr = contentmgr
        self._content = content

    def __repr__(self):
        return f'Persistent(filename={self.filename}, contentmgr={str(self.contentmgr)}, content={str(self._content)})'

    @property
    def content(self):
        if not isloaded(self._content):
            self._content = self._content.load()
        return self._content
    
    @content.setter
    def content(self, value: Content):
        self._content = value
    
    def serialize(self):
        self.contentmgr.write(self.content, self.filename)
        return {
            **Serializable.serialize(self),
            'filename': self.filename,
            'contentmgr': self.contentmgr.serialize(),
            'content': self._content.serialize()
        }
    
    @classmethod
    def deserialize(cls, record: dict):
        record['contentmgr'] = Serializable.deserialize(record['contentmgr'])
        record['content'] = Serializable.deserialize(record['content'])
        res = cls(**record)
        res._content = res.contentmgr.load(res.filename, res._content)
        return res


@Serializable.register('content-register')
class ContentRegister(Serializable):
    def __init__(self, contentmgr: ContentManager, registry: Dict[str, 'Serializable'] = None):
        self.contentmgr = contentmgr
        if registry is None: registry = dict()
        self.registry = registry

    def store(self, content: Union['Content', 'Serializable'], label: str = None, extension: str = None):
        if label is None:
            label = f'{content.type}_{uuid.uuid4()}'

        entry = content
        if isinstance(content, Content):
            filename = f'{content.persistent_type}_{uuid.uuid4()}'
            if extension is not None:
                filename = f'{filename}{extension}'

            entry = Persistent(
                filename=filename, contentmgr=self.contentmgr, content=content
            )
        
        self.registry[label] = entry
    
    def __getitem__(self, key):
        res = self.registry[key]
        if isinstance(res, Persistent):
            return res.content
        return res

    def serialize(self):
        return {
            **Serializable.serialize(self),
            'contentmgr': self.contentmgr.serialize(),
            'registry': Model._serialize_inner(self.registry)
        }
    
    @classmethod
    def deserialize(cls, record: dict):
        return cls(**Model._deserialize_inner(record))


if __name__ == '__main__':
    # content types
    @Content.register('file')
    class FileContent(Content):
        def __init__(self, value: str) -> None:
            self.value = value

        def write(self, path):
            with open(path, 'w') as f:
                f.write(self.value)
        
        @classmethod
        def read(cls, path):
            with open(path, 'r') as f:
                res = f.readline()
                return cls(value=res)

    @Content.register('ndarray')
    class ArrayContent(Content, np.ndarray):
        def write(self, path):
            with open(path, 'wb') as f:
                np.save(f, self)
        
        @classmethod
        def read(cls, path):
            with open(path, 'rb') as f:
                return np.load(f).view(cls)
                
    # content managers
    mainmgr = ContentManager(directory='out')
    mainmgr.clear()
    mgr = mainmgr.getsub(directory='run')

    # serialize persistent content
    entry = Persistent(filename='test', contentmgr=mgr, content=FileContent('blabla'))
    record = entry.serialize()
    print(json.dumps(record, indent=4))

    # deserialize persistent content
    res = Serializable.deserialize(record)
    print(res)
    print(res.content.value)  # content is automatically populated from file when needed

    # creating serializable models
    @Model.register('test')
    class Test(Model):
        a: int
        b: str
        c: str = field(default='test')

    @Model.register('nested')
    class Nested(Model):
        __no_serialize__ = ['c']    # we can stop fields from being serialized

        a: int
        b: Test
        c: str = 'hello world'

    # use of content registers
    reg = ContentRegister(contentmgr=mgr)
    reg.store(content=FileContent('blabla'), label='a')
    reg.store(entry, label='b')
    test = Test(a=5, b='hello', c='bla')
    reg.store(test)
    reg.store(Nested(a=25, b=test, c='donotstoreme'))

    record = reg.serialize()
    print(json.dumps(record, indent=4))

    reg2 = Serializable.deserialize(record)
    print(reg2)
    print(reg2.registry['a'].content.value)
    print(reg2['a'].value)
    reg2['a'].value = 'updated'
    record = reg2.serialize()

    reg3 = Serializable.deserialize(record)
    print(reg3['a'].value)

    # using nested content registers 
    nestedreg = ContentRegister(contentmgr=mainmgr)
    nestedreg.store(reg3, label='main')

    nestedreg.store(np.eye(4).view(ArrayContent), label='mat', extension='.npy')
    
    # writing serializable to file
    path = mainmgr.write(nestedreg, 'main.json')
    resreg = mainmgr.load('main.json')
    print('final ......')
    print(resreg)
    print(resreg['main']['a'].value)
    print(resreg['mat'])

    # manual content writing and reading
    man = mainmgr.write(np.eye(5).view(ArrayContent), filename='mat.npy')
    print(mainmgr.load('mat.npy', ArrayContent, preload=True))
    