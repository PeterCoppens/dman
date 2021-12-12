import logging
import os
import sys
import configparser

from datetime import datetime
from dataclasses import dataclass, field
from typing import Dict

from dman import sjson
from dman.utils import get_root_folder, prompt_user, get_git_hash, get_git_url, check_git_committed


ROOT_FOLDER = '.dman'
STAMP_FOLDER='stamps'
STAMP_CONFIG = 'config.ini'
STAMP_NAME = 'dstamp'



@dataclass
class Stamp:
    name: str
    msg: str
    hash: str
    time: datetime
    dependencies: Dict = field(default_factory=dict)

    LABEL_DT_STRING = "%y%m%d%H%M%S"
    DESCR_DT_STRING = "%d/%m/%y %H:%M:%S"

    @property
    def str_time(self):
        return self.time.strftime(Stamp.DESCR_DT_STRING)
    
    @property
    def label(self):
        return f'{self.name}-{self.time.strftime(Stamp.LABEL_DT_STRING)}'

    @property
    def info(self):
        return \
            f"""stamp {self.label}
    * name: {self.name} at {self.str_time}
    * hash: {self.hash}"""

    def export(self):
        return {
            'name': self.name,
            'description': self.msg,
            'time': self.str_time,
            'hash': self.hash
        }
    
    def write(self, dir: str):
        contents = configparser.ConfigParser()
        contents['Stamp'] = self.export()
        contents['Dependencies'] = {k: v.export(mgr=self, do_stamp=True) for k, v in self.dependencies.items()}
        with open(os.path.join(dir, self.label), 'w') as f:
            contents.write(f)

    @classmethod
    def load(cls, mgr: 'Manager', path: str):
        config = configparser.ConfigParser()
        config.read(path)

        dependencies = dict(config['Dependencies'])
        for key in dependencies:
            dependencies[key] = Dependecy.load(mgr=mgr, value=dependencies[key])

        res = cls(
            name=config['Stamp']['name'],            
            msg=config['Stamp']['description'],
            hash=config['Stamp']['hash'],
            time=datetime.strptime(config['Stamp']['time'], Stamp.DESCR_DT_STRING),
            dependencies=dependencies
        )

        return res

@dataclass
class Dependecy:
    name: str
    path: str
    remote: str
    _hash: str = field(default=None)

    @classmethod
    def from_path(cls, mgr: 'Manager', path: str):
        # we need to select the path relative to root
        abspath = os.path.abspath(path)

        remote = get_git_url(cwd=abspath)
        base = os.path.basename(remote)
        name, _ = os.path.splitext(base)
        
        return cls(
            name=name.lower(),
            path=abspath,
            remote=remote
        )
    
    @classmethod
    def load(cls, mgr: 'Manager', value: str):
        value = sjson.loads(value)
        res = cls(
            name=value['name'],
            path=None,
            remote=value['remote']
        )
        if 'hash' in value:
            res._hash = value['hash']
        if 'path' in value:
            res.path = os.path.join(mgr.root_path, value['path'])

        return res

    @property
    def hash(self):
        if self._hash is None:
            return get_git_hash(cwd=self.path)
        return self._hash
    
    def __hash__(self) -> int:
        return hash(self.name)
    
    def export(self, mgr: 'Manager', do_stamp: bool = False):
        res = {
            'name': self.name,
            'remote': self.remote
        }
        if do_stamp:
            res['hash'] = self.hash
        else:
            res['path'] = os.path.relpath(self.path, start=mgr.root_path)

        return sjson.dumps(res)

class Manager:
    def __init__(self):
        self.root_path = get_root_folder(ROOT_FOLDER)
        self.valid = True
        if self.root_path is None:
            logging.error(f'could not find {ROOT_FOLDER} folder.')
            sys.exit()
        
        self.config = configparser.ConfigParser()
        self.config.read(self.config_path)

        self.dependencies = dict(self.config['Dependencies'])
        for key in self.dependencies:
            self.dependencies[key] = Dependecy.load(mgr=self, value=self.dependencies[key])

        self.stamps = os.listdir(self.stamp_dir)
        self.latest = self.config['Info']['latest']

    @property
    def stamp_dir(self):
        return os.path.join(self.root_path, ROOT_FOLDER, STAMP_FOLDER)

    @property
    def config_path(self):
        return os.path.join(self.root_path, ROOT_FOLDER, STAMP_CONFIG)

    @staticmethod
    def init_repo(_):
        if os.path.exists(ROOT_FOLDER):
            logging.info('Reinitialized existing {STAMP_NAME} project.')
            return
        logging.info(f'Initializing {STAMP_NAME} project: {ROOT_FOLDER}')
        os.mkdir(ROOT_FOLDER)
        os.mkdir(os.path.join(ROOT_FOLDER, STAMP_FOLDER))
        config = configparser.ConfigParser()

        config['Info'] = {'latest' : ''}
        config['Dependencies'] = {}
        
        with open(os.path.join(ROOT_FOLDER, STAMP_CONFIG), 'w') as configfile:
            config.write(configfile)

    def add_dependency(self, dep: Dependecy):
        if dep.name in self.dependencies:
            return False
        self.dependencies[dep.name] = dep
        return True     
    
    def remove_dependency(self, name):
        if name not in self.dependencies:
            return False
        self.dependencies.pop(name)   
        return True    

    def save(self):
        self.config['Dependencies'] = {k: v.export(mgr=self) for k, v in self.dependencies.items()}
        self.config['Info'] = {'latest' : self.latest}
        with open(self.config_path, 'w') as configfile:
            self.config.write(configfile)
    
    def check_repositories(self):
        # check this repository
        if not check_git_committed() and not prompt_user(f'Git repository at {os.getcwd()} has unstaged changes. Do you want to proceed?'):
            return False

        # check dependend repositories
        for v in self.dependencies.values():
            cwd = os.path.join(self.root_path, v.path)
            if not check_git_committed(cwd=cwd) and not prompt_user(f'Git repository at {cwd} has unstaged changes. Do you want to proceed?'):
                return False
        
        return True
    
    def stamp(self, name, msg, prompt=True):
        if not prompt and not self.check_repositories():
            logging.info('canceled stamp.')
            return

        git_hash = get_git_hash()
        time_stamp = datetime.now()

        stamp = Stamp(name, msg, git_hash, time_stamp, self.dependencies)
        self.latest = stamp.label

        stamp.write(dir=self.stamp_dir)
        logging.info('created stamp:')
        logging.info(stamp.info)

        return stamp.label
    
    def get_stamp(self, label):
        if label not in self.stamps:
            return None
        
        return Stamp.load(self, os.path.join(self.stamp_dir, label))

    def remove_stamp(self, label):
        if label not in self.stamps:
            return False
        
        os.remove(os.path.join(self.stamp_dir, label))
        return True
