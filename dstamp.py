from posixpath import abspath
import subprocess
import argparse
import configparser
import logging
import os
import json
import sys

from datetime import datetime
from dataclasses import dataclass, field

ROOT_FOLDER = '.dman'
STAMP_FOLDER='stamps'
STAMP_CONFIG = 'config.ini'
STAMP_NAME = 'dstamp'


def prompt_user(question, default=None, loglevel=logging.WARNING):
    """Ask a yes/no question via raw_input() and return their answer.

    "question" is a string that is presented to the user.
    "default" is the presumed answer if the user just hits <Enter>.
            It must be "yes" (the default), "no" or None (meaning
            an answer is required of the user).

    The "answer" return value is True for "yes" or False for "no".
    """
    if not logging.root.isEnabledFor(loglevel):
        return True

    valid = {"yes": True, "y": True, "ye": True, "no": False, "n": False}
    if default is None:
        prompt = " [y/n] "
    elif default == "yes":
        prompt = " [Y/n] "
    elif default == "no":
        prompt = " [y/N] "
    else:
        raise ValueError("invalid default answer: '%s'" % default)

    while True:
        logging.log(loglevel, question + prompt)
        choice = input().lower()
        if default is not None and choice == "":
            return valid[default]
        elif choice in valid:
            return valid[choice]
        else:
            logging.error("Please respond with 'yes' or 'no' " "(or 'y' or 'n').")

def get_git_hash(cwd = None):
    if cwd is None: cwd = os.getcwd()
    return subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=cwd).decode('ascii').strip()

def get_git_url(cwd = None):
    if cwd is None: cwd = os.getcwd()
    return subprocess.check_output(['git', 'config', '--get', 'remote.origin.url'], cwd=cwd).decode('ascii').strip()

def check_git_committed(cwd = None):
    if cwd is None: cwd = os.getcwd()
    res = subprocess.check_output(['git', 'status'], cwd=cwd).decode('ascii').strip()
    if res.find('nothing to commit') > 0:
        return True
    return prompt_user(f'Git repository at {cwd} has unstaged changes. Do you want to proceed?')


@dataclass
class Stamp:
    name: str
    msg: str
    hash: str
    time: datetime

    @property
    def str_time(self):
        return self.time.strftime("%d/%m/%y %H:%M:%S")
    
    @property
    def label(self):
        return f'{self.name}-{self.time.strftime("%y%m%d%H%M%S")}'
    
    def export(self):
        return {
            'name': self.name,
            'description': self.msg,
            'time': self.str_time,
            'hash': self.hash
        }

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
        value = json.loads(value)
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

        return json.dumps(res)

class Manager:
    def __init__(self):
        self.root_path = None
        current_path = os.getcwd()
        while self.root_path is None:
            if os.path.exists(os.path.join(current_path, ROOT_FOLDER)):
                self.root_path = os.path.join(current_path)
            else:
                current_path = os.path.dirname(current_path)
                if os.path.dirname(current_path) == current_path:
                    logging.error(f'could not find {ROOT_FOLDER} folder')
                    return
        
        self.config = configparser.ConfigParser()
        self.config.read(os.path.join(self.root_path, ROOT_FOLDER, STAMP_CONFIG))

        self.dependencies = dict(self.config['Dependencies'])
        for key in self.dependencies:
            self.dependencies[key] = Dependecy.load(mgr=self, value=self.dependencies[key])

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
        with open(os.path.join(self.root_path, ROOT_FOLDER, STAMP_CONFIG), 'w') as configfile:
            self.config.write(configfile)
    
    def check_repositories(self):
        # check this repository
        if not check_git_committed():
            return False

        # check dependend repositories
        for v in self.dependencies.values():
            if not check_git_committed(cwd=os.path.join(self.root_path, v.path)):
                return False
        
        return True
    
    def stamp(self, name, msg, prompt=True):
        if not prompt and not self.check_repositories():
            logging.info('canceled stamp.')
            return

        git_hash = get_git_hash()
        time_stamp = datetime.now()
        stamp = Stamp(name, msg, git_hash, time_stamp)
        logging.info(
            f"""created stamp
            * name: {stamp.name} at {stamp.str_time}
            * hash: {stamp.hash}"""
        )

        contents = configparser.ConfigParser()
        contents['Stamp'] = stamp.export()
        contents['Dependencies'] = {k: v.export(mgr=self, do_stamp=True) for k, v in self.dependencies.items()}
        with open(os.path.join(self.root_path, ROOT_FOLDER, STAMP_FOLDER, stamp.label), 'w') as f:
            contents.write(f)

def configure_log(args):
    numeric_level = getattr(logging, args.log.upper(), None)
    if not isinstance(numeric_level, int):
        raise parser.error('Invalid log level: %s' % args.log.upper())
    logging.basicConfig(level=numeric_level)


def init(_):
    if os.path.exists(ROOT_FOLDER):
        logging.info('Reinitialized existing {STAMP_NAME} project.')
        return
    logging.info(f'Initializing {STAMP_NAME} project: {ROOT_FOLDER}')
    os.mkdir(ROOT_FOLDER)
    os.mkdir(os.path.join(ROOT_FOLDER, STAMP_FOLDER))
    config = configparser.ConfigParser()

    
    config['Dependencies'] = {}
    
    with open(os.path.join(ROOT_FOLDER, STAMP_CONFIG), 'w') as configfile:
        config.write(configfile)

def add_dependency(args):
    dstamp = Manager()
    dep = Dependecy.from_path(dstamp, args.path)
    if not dstamp.add_dependency(dep):
        logging.error(f'{dep.name} is already a dependency.')
    dstamp.save()

def remove_dependency(args):
    dstamp = Manager()
    if not dstamp.remove_dependency(args.name):
        logging.error(f'{args.name} is not a dependency.')
    dstamp.save()

def list_dependency(_):
    dstamp = Manager()
    for dep in dstamp.dependencies:
        print(dep)

def info_dependency(args):
    dstamp = Manager()
    if not args.name in dstamp.dependencies:
        logging.error(f'{args.name} is not a dependency.')
        return
    print(dstamp.dependencies[args.name])

def stamp(args):
    dstamp = Manager()
    dstamp.stamp(args.name, args.msg, prompt=args.prompt)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()

    parser.add_argument(
        '--log',
        dest='log',
        default='DEBUG',
        type=str,
        help='specify a logging level'
    )

    subparsers = parser.add_subparsers(title='commands', description='dman supports the actions listed below', help='options')

    init_parser = subparsers.add_parser('init', help='initialize dman in this folder')
    init_parser.set_defaults(execute=init)

    stamp_parser = subparsers.add_parser('stamp', help='create a stamp of the current repository state')
    stamp_parser.set_defaults(execute=stamp)
    stamp_parser.add_argument(
        'name',
        type=str,
        help='set name of the stamp'
    )
    stamp_parser.add_argument(
        '-m',
        dest='msg',
        type=str,
        default='',
        help='stamp description'
    )
    stamp_parser.add_argument(
        '-y',
        dest='prompt',
        action='store_true',
        help='accept prompts automatically'
    )

    dep_parser = subparsers.add_parser('dep', help='alter dependencies')
    dep_subparser = dep_parser.add_subparsers(title='commands', description='dman supports the actions listed below', help='options')

    add_dep_parser = dep_subparser.add_parser('add', help='add dependency')
    add_dep_parser.set_defaults(execute=add_dependency)
    add_dep_parser.add_argument(
        'path',
        type=str,
        help='path of dependency'
    )

    rem_dep_parser = dep_subparser.add_parser('remove', help='remove dependency')
    rem_dep_parser.set_defaults(execute=remove_dependency)
    rem_dep_parser.add_argument(
        'name',
        type=str,
        help='name of dependency'
    )

    info_dep_parser = dep_subparser.add_parser('info', help='get info about dependency')
    info_dep_parser.set_defaults(execute=info_dependency)
    info_dep_parser.add_argument(
        'name',
        type=str,
        help='name of dependency'
    )

    list_dep_parser = dep_subparser.add_parser('list', help='list dependencies')
    list_dep_parser.set_defaults(execute=list_dependency)

    args = parser.parse_args()
    configure_log(args)
    if hasattr(args, 'execute'):
        args.execute(args)
    else:
        parser.print_help()
    