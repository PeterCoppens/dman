import argparse
import configparser
import os
import shutil
import sys
import json

from dataclasses import dataclass, field
from datetime import datetime
from typing import List

from dman.stamp import Manager
from dman.utils import prompt_user


@dataclass
class TimingEntry:
    begin: datetime
    end: datetime = field(default=None)
    datestr: str = field(default='%d/%m/%y %H:%M:%S')
    
    @property
    def finished(self):
        return self.end is not None
    
    def start(self):
        self.begin = datetime.now()
        self.end = None
    
    def stop(self):
        self.end = datetime.now()
    
    def export(self, _: str):
        end = 'not finished'
        if self.end:
            end = self.end.strftime(self.datestr)
            
        return {
            'start': self.begin.strftime(self.datestr),
            'end': end
        }

    @staticmethod
    def configure_parser(_: argparse.ArgumentParser):
        pass
    
    @classmethod
    def from_argument_parser(cls, parser: argparse.ArgumentParser, args, default_start: datetime = None):
        if default_start is None:
            default_start = datetime.now()
        return cls(begin=default_start)


@dataclass
class ConfigEntry:
    DEFAULT_CONFIG = 'config.ini'

    path: str
    contents: configparser.ConfigParser

    def export(self, target: str):
        if self.path == '':
            return {}
        else:
            shutil.copy(src=self.path, dst=os.path.join(target, ConfigEntry.DEFAULT_CONFIG))
            return {
                'config': ConfigEntry.DEFAULT_CONFIG
            }

    @staticmethod
    def configure_parser(parser: argparse.ArgumentParser):
        parser.add_argument(
            '--config', 
            dest='config',
            default=None,
            type=str,
            help='path of config file'
        )
    
    @classmethod
    def from_argument_parser(cls, parser: argparse.ArgumentParser, args):
        if args.config is None:
            return cls('', configparser.ConfigParser())

        res = ConfigEntry.from_path(args.config)
        if res is None:
            raise parser.error(f'could not find valid config at {args.config}')
        return res

    @classmethod
    def from_path(cls, path: str):
        if not os.path.exists(path):
            return None
        
        config = configparser.ConfigParser()
        config.read(path)

        return cls(path=path, contents=config)


@dataclass 
class RunEntry:
    name: str
    stamp: str
    msg: str = field(default=None)

    def export(self, _: str):
        if self.stamp is None:
            mgr = Manager()
            self.stamp = mgr.stamp(name=self.name, msg=self.msg)
            mgr.save()

        return {
            'name': self.name,
            'stamp': self.stamp,
            'description': self.msg
        }
    
    @staticmethod
    def configure_parser(parser: argparse.ArgumentParser):
        parser.add_argument(
            '--run-name',
            dest='name',
            default=None,
            type=str,
            help='specify a custom run name'
        )

        parser.add_argument(
            '--stamp',
            dest='stamp',
            action='store_true',
            help='automatically create a stamp with the same name as the run'
        )

        parser.add_argument(
            '-m',
            dest='msg',
            default='',
            type=str,
            help='specify run details.'
        )

    @classmethod
    def from_argument_parser(cls, parser: argparse.ArgumentParser, args, default_name: str = None):
        name, msg = args.name, args.msg

        if name is None:
            name = default_name

        stamp = None
        if not args.stamp:
            stamp = Manager().latest

        return cls(name=name, stamp=stamp, msg=msg)

@dataclass
class ScriptsEntry:
    DEFAULT_GENERATOR = 'gen.py'

    gen: str
    parsers: List[str] = field(default_factory=list)
    local: bool = field(default=False)
    
    def export(self, target: str):
        mgr = Manager()

        if self.local:
            local_gen = os.path.join(target, ScriptsEntry.DEFAULT_GENERATOR)
            shutil.copy(src=self.gen, dst=local_gen)
            self.gen = os.path.basename(local_gen)

            for i, parser in enumerate(self.parsers):
                local_parser = os.path.join(target, os.path.basename(parser))
                shutil.copy(src=parser, dst=local_parser)
                self.parsers[i] = os.path.basename(local_parser)
        else:
            for i, parser in enumerate(self.parsers):
                self.parsers[i] = os.path.relpath(parser, start=mgr.root_path)
            self.gen = os.path.relpath(self.gen, start=mgr.root_path)

        return {
            'generator': self.gen,
            'parsers': json.dumps(self.parsers)
        }
            

    @staticmethod
    def configure_parser(parser: argparse.ArgumentParser):
        parser.add_argument(
            '--parser-list',
            dest='parsers',
            nargs='+',
            default=[],
            help='path to parser scripts to store in meta data'
        )

        parser.add_argument(
            '--keep-local',
            dest='local',
            action='store_true',
            help='store the generator and parser scripts locally in the output folder'
        )
    
    @classmethod
    def from_argument_parser(cls, parser, args):
        gen = os.path.realpath(sys.argv[0])

        parsers = args.parsers
        for i, parse_script in enumerate(parsers):
            if not os.path.exists(parse_script):
                raise parser.error(f'could not find file at {parse_script}.')
            parsers[i] = os.path.realpath(parse_script)

        return cls(gen=gen, parsers=parsers, local=args.local)


class Run:
    DEFAULT_RECORD = 'info.ini'
    DEFAULT_RUN_DATE_STRING = '%y-%m-%d-%H%M%S'
    DEFAULT_RUN_TARGET = '.dman/runs'

    def __init__(self, target: str, meta: RunEntry, scripts: ScriptsEntry, config: ConfigEntry = None, timing: TimingEntry = None) -> None:
        self.target = target

        self.meta = meta
        self.scripts = scripts
        if timing is None:
            timing = TimingEntry(datetime.now())
        self.timing = timing
        self.config = config

        self.finished = False
        self.exported = False

    def export(self):
        if not os.path.exists(self.target):
            os.makedirs(self.target)

        record = configparser.ConfigParser()
        record['Info'] = {**self.meta.export(self.target), **self.config.export(self.target)}
        record['Scripts'] = self.scripts.export(self.target)
        record['Timing'] = self.timing.export(self.target)

        with open(os.path.join(self.target, Run.DEFAULT_RECORD), 'w') as configfile:
            record.write(configfile)        

    @staticmethod
    def configure_parser(parser: argparse.ArgumentParser):
        parser.add_argument(
            '--dir',
            dest='dir',
            default=None,
            type=str,
            help='specify the directory to store the run in.'
        )
        
        parser.add_argument(
            '--override',
            dest='override',
            action='store_true',
            help='override the contents of the output folder if it exists'
        )

        for entry in [RunEntry, ScriptsEntry, TimingEntry, ConfigEntry]:
            entry.configure_parser(parser)
            
    
    @classmethod
    def from_argument_parser(cls, parser, args, generator_name: str = None):
        current_time = datetime.now()
        default_name = f'run-{generator_name}-{current_time.strftime(Run.DEFAULT_RUN_DATE_STRING)}'
        
        target = args.dir
        if target is None:
            mgr = Manager()
            target = os.path.join(mgr.root_path, Run.DEFAULT_RUN_TARGET)

        meta = RunEntry.from_argument_parser(parser, args, default_name=default_name)

        target = os.path.join(target, meta.name)
        if os.path.exists(target):
            if args.override and prompt_user(f'override folder {target}'):
                shutil.rmtree(target)
                # TODO proper remove of run (including of the stamp?)
            else:
                raise parser.error(f'Output folder already exists: {target}. Use --override if you want to overwrite its contents.')
            
        scripts = ScriptsEntry.from_argument_parser(parser, args)
        config = ConfigEntry.from_argument_parser(parser, args)
        timing = TimingEntry.from_argument_parser(parser, args, default_start=current_time)
        return cls(target=target, meta=meta, scripts=scripts, config=config, timing=timing)
        

class Generator:
    """
    Usage: 
        >>> with Generator(name='name'):
        >>>     ...
    """

    def __init__(self, name: str) -> None:
        self.name = name

        self.mgr = Manager()
        if not self.mgr.valid:
            sys.exit()

        self.parser = argparse.ArgumentParser(f'{name} generator')
        Run.configure_parser(self.parser)

    def parse(self):
        self.args = self.parser.parse_args()
        self.run = Run.from_argument_parser(self.parser, self.args, generator_name=f'{self.name}')
        
    def __enter__(self):
        self.parse()
        self.run.timing.start
        return self
    
    def __exit__(self, exc_type, exc_val, exc_trb):
        if exc_type is None:
            if not self.run.timing.finished: self.run.timing.stop()
        self.run.export()


# def configure_log(args):
#     numeric_level = getattr(logging, args.log.upper(), None)
#     if not isinstance(numeric_level, int):
#         raise parser.error('Invalid log level: %s' % args.log.upper())
#     logging.basicConfig(level=numeric_level)


# def init(args):
#     if os.path.exists('.dman'):
#         logging.info('Reinitialized existing dman project.')
#         return
#     logging.info(f'Initializing dman project: .dman')
#     os.mkdir('.dman')
#     config = configparser.ConfigParser()
#     config['Info'] = {
#         'Studies' : [],
#         'Study_Folder': 'studies'
#     }
    

#     with open(os.path.join('.dman', 'info.ini'), 'w') as configfile:
#         config.write(configfile)


# def load(args):
#     root_path = None
#     current_path = os.getcwd()
#     while root_path is None:
#         if os.path.exists(os.path.join(current_path, '.dman')):
#             root_path = os.path.join(current_path)
#         else:
#             current_path = os.path.dirname(current_path)
#             if os.path.dirname(current_path) == current_path:
#                 logging.error('could not find .dman folder')
#                 return
    
#     config = configparser.ConfigParser()
#     config.read(os.path.join(root_path, '.dman', 'info.ini'))
#     return config, root_path


# def spawn(args):
#     logging.info(f'creating study: {args.name}')
    
#     # load config
#     config, root_path = load(args)

#     # create study folder
#     study_path = os.path.join(root_path, config['Info']['study_folder'], args.name)
#     logging.info(f'creating study folder: {study_path}')
#     if os.path.exists(study_path):
#         logging.error('folder already exists')
#         return
#     os.mkdir(study_path)

#     # create empty config file
    

#     # register study
#     if args.name in config['Info']['studies']:
#         logging.error(f'a study at {study_path} was already registered.')
#         return
        
#     logging.info(f'registering study: {args.name}')
#     lst = json.loads(config['Info']['studies'])
#     config['Info']['studies'] = json.dumps(lst + [args.name])
    
#     with open(os.path.join(root_path, '.dman', 'info.ini'), 'w') as configfile:
#         config.write(configfile)


# if __name__ == '__main__':
#     logging.basicConfig(level=logging.DEBUG)

#     parser = argparse.ArgumentParser()

#     parser.add_argument(
#         '--log',
#         dest='log',
#         default='WARNING',
#         type=str,
#         help='specify a logging level'
#     )

#     subparsers = parser.add_subparsers(title='commands', description='dman supports the actions listed below', help='options')

#     init_parser = subparsers.add_parser('init', help='initialize dman in this folder')
#     init_parser.set_defaults(execute=init)

#     spawn_parser = subparsers.add_parser('spawn', help='spawn a study folder')
#     spawn_parser.set_defaults(execute=spawn)
#     spawn_parser.add_argument(
#         'name',
#         type=str,
#         help='set name of study'
#     )

#     args = parser.parse_args()
#     if hasattr(args, 'execute'):
#         args.execute(args)
#     else:
#         parser.print_help()
