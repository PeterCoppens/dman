import os
from typing import Dict, Union

from dman.persistent.storeables import PLAN_FIELD, StoragePlan, StoringConfig, StoringSerializer, get_serialized_record_path, is_storeable, read, storeable, storeable_type
from dman.persistent.serializables import BaseContext, serializable, deserialize, serialize
from dman.persistent.modelclasses import _bdict, modelclass, recordfield, record, smdict
from dman.persistent.configclasses import configclass, section, dictsection
from dman.persistent.smartdataclasses import AUTO, Wrapper, wrapfield

from dman.utils import get_git_hash, get_root_folder

from dataclasses import dataclass, field, is_dataclass, asdict
from datetime import datetime

import logging
import copy
import shutil
import json

ROOT_FOLDER = '.dman'
REPO_FILE = 'repo'
MGR_FILE = 'dman'
RUN_FOLDER = 'runs'
CACHE_FOLDER = 'cache'


class Recorder(StoringSerializer):
    def store(self, content, filename: str = AUTO, extension: str = AUTO, *, plan: StoragePlan = None):
        if plan is None: plan = StoragePlan()
        rec = record(content, plan = plan << StoragePlan(filename=filename, extension=extension))
        rec = serialize(rec, self)    
        return get_serialized_record_path(rec)
    
    def load(self, type, filename: str):
        if not is_storeable(type):
            raise ValueError(f'requested reading of non storeable type {type}') 
        
        sto_type = storeable_type(type)

        req= self.request(getattr(type, PLAN_FIELD, StoragePlan()) << StoragePlan(filename=filename, preload=True))
        return req.read(sto_type)


@storeable(name='_sto__repository')
@serializable(name='_ser__repository')
class Repository(StoringSerializer):
    __plan__ = StoringSerializer.__plan__ << StoragePlan(filename=REPO_FILE)

    @staticmethod
    def get_directory(directory: str = None):
        if directory is None:
            directory = get_root_folder(ROOT_FOLDER) 
            if directory is None:
                raise RuntimeError(f'could not find root folder {ROOT_FOLDER}')
            directory = os.path.join(directory, ROOT_FOLDER)
        return directory

    def __init__(self, directory: str = None, config: StoringConfig = None, baseplan: StoragePlan = None):
        if config is None: config = StoringConfig()

        StoringSerializer.__init__(
            self, 
            Repository.get_directory(directory), 
            config=StoringConfig(store_on_close=True) << config, 
            baseplan=StoragePlan(extension='') << baseplan
        )
    
    def cachedir(self, subdirectory: str, *, config: StoringConfig = None, baseplan: StoragePlan = None):      
        if config is None: config = StoringConfig()
        if baseplan is None: baseplan = StoragePlan()

        subdirectory = os.path.join(CACHE_FOLDER, subdirectory)

        req = self.request(self.baseplan << StoragePlan(filename=subdirectory, extension=''))
        return Recorder(
            directory=req.path,
            parent=self,
            config=self.config << StoringConfig(store_on_close=False) << config,
            baseplan=self.baseplan << baseplan
        )
        
    @classmethod
    def load(cls, directory: str = None) -> 'Repository':
        return read(
            type=storeable_type(Repository), 
            path=os.path.join(Repository.get_directory(directory), f'{REPO_FILE}.json'), 
            serializer = BaseContext()
        )
    
    def __repr__(self):
        return f'Repository(directory={self.directory})'
    
    def __serialize__(self, serializer: BaseContext = None):
        return {
            'directory': self.directory,
            'config': serialize(self.config, serializer),
            'baseplan': serialize(self.baseplan, serializer)
        }
    
    @classmethod
    def __deserialize__(cls, serialized: dict, serializer: BaseContext = None):
        directory = serialized['directory']
        config = deserialize(serialized['config'], serializer)
        baseplan = deserialize(serialized['baseplan'], serializer)
        return cls(directory=directory, config=config, baseplan=baseplan)


@modelclass(name='_ser__stamp_config')
class ManagerInfo:
    latest: str = field(default='')
    dependencies: dict = field(default_factory=dict)
    generators: dict = field(default_factory=dict)


@configclass(name='_sto__sec')
class Stamp:
    @section(name='_sec__stamp')
    class Info:
        LABEL_FORMAT = "%y%m%d%H%M%S"
        DISPLAY_FORMAT = "%d/%m/%y %H:%M:%S"
        
        name: str = field(default='error')
        description: str = field(default='')
        time: str = field(default_factory=datetime.now)
        hash: str = field(default_factory=get_git_hash)

        def __serialize__(self):
            return {
                'name': self.name, 
                'description': self.description,
                'time': datetime.strftime(self.time, self.DISPLAY_FORMAT),
                'hash': self.hash
            }
        
        @classmethod
        def __deserialize__(cls, serialized: dict):
            return cls(
                serialized['name'],
                serialized['description'],
                datetime.strptime(serialized['time'], cls.DISPLAY_FORMAT),
                serialized['hash']     
            )
        
        @property
        def label(self):
            return f'{self.name}-{datetime.strftime(self.time, self.LABEL_FORMAT)}'

    info: Info
    dependencies: dictsection

    @property
    def name(self):
        return self.info.name

    @property
    def time(self):
        return self.info.time
    
    @property
    def label(self):
        return self.info.label
    
    @classmethod
    def create(cls, name: str, description: str = '', dependencies: dict = None):
        if dependencies is None: dependencies = dict()
        return cls(
            cls.Info(name=name, description=description),
            dependencies
        )


@storeable(name='_sto__run_dict')
@serializable(name='_ser__run_dict')
class RunDict(_bdict):
    def __key_plan__(self, k):
        return StoragePlan(filename=k, subdir=k)
    
    def __getitem__(self, key) -> 'Run':
        return super().__getitem__(key)
    
    def __setitem__(self, k: str, v: 'Run') -> None:
        return super().__setitem__(k, v)


@modelclass(name='_dman__manager', storeable=True)
class Manager:
    __plan__ = StoragePlan(filename=MGR_FILE, extension='.json')

    repo: Repository = recordfield(default_factory=Repository, plan=StoragePlan(filename=REPO_FILE, preload=True), repr=True)
    runs: RunDict = recordfield(default_factory=RunDict, plan=StoragePlan(filename='runs', subdir='runs'))

    info: ManagerInfo = field(default_factory=ManagerInfo)
    stamps: smdict = recordfield(default_factory=smdict, plan=StoragePlan(filename='stamps', subdir='stamps'))

    def __post_init__(self):
        # manager handles storing of repo
        self.repo.config = self.repo.config << StoringConfig(store_on_close=False)

        # configure storing behaviour of stamps dictionary
        self.stamps.store_by_key()
        self.stamps.plan = self.stamps.plan << StoragePlan(extension='')

    def stamp(self, name: str, description: str = ''):
        stmp = Stamp.create(name=name, description=description, dependencies=dictsection(self.info.dependencies))
        self.stamps[stmp.label] = stmp
        self.info.latest = stmp.label

    @property
    def latest_stamp(self):
        return self.info.latest
    
    @classmethod
    def load(cls, directory: str = None) -> 'Manager':
        with Repository.load(directory) as repo:
            return read(
                type=storeable_type(Manager), 
                path=os.path.join(repo.directory, f'{MGR_FILE}.json'), 
                serializer=repo
            )

    def open(self):
        self.repo.open()
    
    def close(self):
        rec = record(self)
        serialize(rec, self.repo)
        self.repo.close()
        
    def __enter__(self) -> 'Manager':
        self.open()
        return self

    def __exit__(self, exception_type, exception_value, traceback):
        self.close()


@serializable
@dataclass
class Component:
    path: str
    description: str = ''

    
@section(name='_sec__components')
class Components(list):
    LOCAL_FIELD = '__local__'
    def __init__(self, local: bool = False, content: list = None):
        if content is None:
            content = list()
        list.__init__(self, content)
        self.local = local
    
    def __setitem__(self, i, o: Union[Component, str]):
        if not isinstance(o, Component):
            o = Component(path=o)
        list.__setitem__(self, i, o)
    
    def append(self, o: Union[Component, str]):
        if not isinstance(o, Component):
            o = Component(path=o)
        list.append(self, o)

    def __serialize__(self, serializer: BaseContext = None):
        res = {}
        for v in self:
            component: Component = v
            filename: str = os.path.basename(component.path)
            if self.local and isinstance(serializer, StoringSerializer):
                with serializer.subdirectory('components') as sr:
                    req = sr.request(StoragePlan(filename=filename))
                    shutil.copyfile(src=component.path, dst=req.path)
                    component.path = req.path
                
            k = filename.split('.')[0]
            res[k] = json.dumps(asdict(component))

        res[self.LOCAL_FIELD] = self.local
        return res
    
    @classmethod
    def __deserialize__(cls, serialized: dict, serializer: BaseContext = None):
        ser = copy.deepcopy(serialized)
        local = ser.pop(cls.LOCAL_FIELD)
        res = []
        for v in ser.values():
            res.append(Component(**json.loads(v)))
        return cls(local=local, content=res)
        

@configclass
class Run:
    @section(name='_sec__meta')
    class Meta:
        name: str = ''
        stamp: str = ''
        description: str = ''
    
    @section(name='_sec__time')
    class Timing:
        FORMAT = "%d/%m/%y %H:%M:%S"
        begin: datetime = field(default_factory=datetime.now)
        end: datetime = field(default=None)

        def __serialize__(self):
            res = {'begin': datetime.strftime(self.begin, self.FORMAT)}
            if self.end is not None:
                res['end'] = datetime.strftime(self.end, self.FORMAT)
            return res

        @classmethod
        def __deserialize__(cls, serialized: dict):
            end = serialized.get('end')
            if end is not None: end = datetime.strptime(end, cls.FORMAT)
            return cls(datetime.strptime(serialized['begin'], cls.FORMAT), end)

        def start(self):
            self.begin = datetime.now()
            self.end = None

        def stop(self):
            self.end = datetime.now()

    meta: Meta
    timing: Timing
    components: Components

    @classmethod
    def create(cls, name: str, description: str = '', stamp: str = ''):
        meta = cls.Meta(name=name, description=description, stamp=stamp)
        timing = cls.Timing(begin=datetime.now())
        return cls(meta=meta, timing=timing)

    




