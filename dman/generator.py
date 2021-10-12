import argparse
import configparser
import os
import shutil
import logging
import sys

from dataclasses import dataclass, field
from collections import namedtuple
from datetime import datetime
from typing import List

from dman.stamp import Manager


DEFAULT_GENERATOR = 'gen.py'
DEFAULT_CONFIG = 'config.ini'
DEFAULT_META = 'info.ini'
DEFAULT_RUN_DATE_STRING = '%y-%m-%d-%H%M%S'
DEFAULT_OUTPUT = '.dman/runs'


@dataclass
class Timeframe:
    begin: datetime
    end: datetime = field(default=None)
    datestr: str = field(default='%d/%m/%y %H:%M:%S')

    @property
    def begin_string(self):
        return self.begin.strftime(self.datestr)

    @property
    def end_string(self):
        if self.end:
            return self.end.strftime(self.datestr)
        return 'not finished'


@dataclass
class Run:
    name: str
    gen: str
    config: str 
    timing: Timeframe
    parsers: List[str] = field(default_factory=list)
    msg: str = field(default=None)

    def export(self, path: str):
        config = configparser.ConfigParser()
        config['Meta-data'] = {}
        config['Meta-data']['Name'] = self.name
        if self.config:
            config['Meta-data']['Config-File'] = self.config
        if self.msg:
            config['Meta-data']['Description'] = self.msg

        config['Scripts'] = {}
        config['Scripts']['Generator'] = self.gen
        if len(self.parsers) > 0:
            config['Scripts']['Parsers'] = str(self.parsers)

        config['Timing'] = {}
        config['Timing']['Start'] = self.timing.begin_string
        config['Timing']['End'] = self.timing.end_string

        # config['RNG'] = {'State': str(random.getstate())}

        with open(path, 'w') as configfile:
            config.write(configfile)


class Generator:
    """
    Usage: 
        >>> with Generator(name='name'):
        >>>     ...
    """
    Config = namedtuple("Config", "path contents")

    def __init__(self, name, version=None) -> None:
        self.name = name
        self.version = version

        self.args = None
        self.timing = None
        self.finished = False

        self.mgr = Manager()
        if not self.mgr.valid:
            sys.exit()

        self.parser = argparse.ArgumentParser(f'{name} generator')

        def configFile(string):
            if not os.path.exists(string):
                self.parser.error(f'Could not find config file at {string}.')

            config = configparser.ConfigParser()
            config.read(string)

            res = self.Config(path=string, contents=config)
            return res

        self.parser.add_argument(
            '--config', 
            dest='config',
            default=self.Config(path=None, contents={}),
            type=configFile,
            help='path of config file'
        )

        self.parser.add_argument(
            '--path',
            dest='path',
            default=os.path.join(self.mgr.root_path, DEFAULT_OUTPUT),
            type=str,
            help='specify the folder to store the run in'
        )
            
        default_run_name = f'run-{name}-{datetime.now().strftime(DEFAULT_RUN_DATE_STRING)}'
        if version:
            default_run_name = f'run-{name}-v{version}-{datetime.now().strftime(DEFAULT_RUN_DATE_STRING)}'

        self.parser.add_argument(
            '--run-name',
            dest='output',
            default=default_run_name,
            type=str,
            help='specify a custom run name'
        )

        self.parser.add_argument(
            '-m',
            dest='msg',
            default='',
            type=str,
            help='specify run details.'
        )

        self.parser.add_argument(
            '-y',
            dest='prompt',
            action='store_true',
            help='accept prompts automatically'
        )

        self.parser.add_argument(
            '--parser-list',
            dest='parsers',
            nargs='+',
            default=[],
            help='path to parser scripts to store in meta data'
        )

        self.parser.add_argument(
            '--store-gen',
            dest='store',
            action='store_true',
            help='store the generator and parser scripts in the output folder'
        )

        self.parser.add_argument(
            '--override',
            dest='override',
            action='store_true',
            help='override the contents of the output folder if it exists'
        )

        # self.parser.add_argument(
        #     '--stamp',
        #     dest='stamp',
        #     action='store_true',
        #     help='automatically create a stamp with the same name as the run'
        # )
    
    def parse(self):
        self.args = self.parser.parse_args()

        if (not self.args.override) and os.path.exists(self.path):
            raise self.parser.error(f'Output folder already exists: {self.path}. Use --override if you want to overwrite its contents.')

    @property
    def config(self):
        return self.args.config.contents

    @property
    def path(self):
        return os.path.join(self.runFolder, self.args.output)

    @property
    def runFolder(self):
        return self.args.path

    def start_timing(self):
        self.finished = False
        self.timing = Timeframe(datetime.now())

    def stop_timing(self):
        if self.finished:
            return  # stop timing was already called
        self.finished = True
        self.timing.end = datetime.now()

    def write(self):
        if not os.path.exists(self.runFolder):
            os.mkdir(self.runFolder)
            logging.info(f'Created output directory at {self.runFolder}')
            
        if not os.path.exists(self.path):
            os.mkdir(self.path)
            logging.info(f'Created run directory at {self.path}')

        timing = self.timing
        if timing is None:
            timing = Timeframe(start = datetime.now())

        if self.args.config.path is not None:
            shutil.copy(src=self.args.config.path, dst=os.path.join(self.path, DEFAULT_CONFIG))
        if self.args.store:
            shutil.copy(src=__file__, dst=os.path.join(self.path, DEFAULT_GENERATOR))
            for parser in self.args.parsers:
                shutil.copy(src=parser, dst=os.path.join(self.path, os.path.basename(parser)))

            Run(
                name=self.args.output, 
                gen=DEFAULT_GENERATOR, 
                config=DEFAULT_CONFIG if self.args.config.path else None,
                timing=timing,
                parsers=[os.path.basename(parser) for parser in self.args.parsers],
                msg=self.args.msg
            ).export(os.path.join(self.path, DEFAULT_META))
        else:
            Run(
                name=self.args.output, 
                gen=os.path.realpath(__file__), 
                config=DEFAULT_CONFIG if self.args.config.path else None,
                timing=timing,
                parsers=[os.path.realpath(parser) for parser in self.args.parsers],
                msg=self.args.msg
            ).export(os.path.join(self.path, DEFAULT_META))
        
    def __enter__(self):
        self.parse()
        self.start_timing()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.stop_timing()
        self.write()


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
