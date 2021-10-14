from abc import ABC, abstractmethod
import argparse
import configparser
import logging
import os
import shutil
import sys
import json
import tempfile

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List
from collections import ChainMap, OrderedDict

from dman.stamp import Manager
from dman.utils import prompt_user


@dataclass
class TimingEntry:
    DATESTR = '%d/%m/%y %H:%M:%S'

    begin: datetime
    end: datetime = field(default=None)
    
    @property
    def finished(self):
        return self.end is not None
    
    def start(self):
        self.begin = datetime.now()
        self.end = None
    
    def stop(self):
        self.end = datetime.now()
    
    def export(self, _: str = None):
        end = 'not finished'
        if self.end:
            end = self.end.strftime(TimingEntry.DATESTR)
            
        return {
            'start': self.begin.strftime(TimingEntry.DATESTR),
            'end': end
        }

    @classmethod
    def load(cls, path: str, record: dict):
        return cls(
            begin=datetime.strptime(record['start'], TimingEntry.DATESTR),
            end=datetime.strptime(record['end'], TimingEntry.DATESTR)
        )

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

    @classmethod
    def assign(cls, run: 'Run', default_file: str = None, *args, **kwargs):
        if run.config.path == '' and default_file is not None:
            # load the predetermined config
            run.config = cls.from_path(os.path.join(os.path.dirname(sys.argv[0]), default_file))
        else:
            run.config = cls(run.config.path, run.config.contents)
        
        run.config.__post_assign__(*args, **kwargs)
        return run.config

    def export(self, target: str):
        if self.path == '':
            return {}
        else:
            shutil.copy(src=self.path, dst=os.path.join(target, ConfigEntry.DEFAULT_CONFIG))
            return {
                'config': ConfigEntry.DEFAULT_CONFIG
            }
    
    @classmethod
    def load(cls, path: str, record: dict):
        return cls.from_path(os.path.join(path, record['config']))

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
    
    def __post_assign__(self, *args, **kwargs):
        pass


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
    
    @classmethod
    def load(cls, path: str, record: dict):
        return cls(
            name=record['name'],
            stamp=record['stamp'],
            msg=record['description']
        )
    
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

    def add_parser(self, *parser: str):
        base_path = os.path.realpath(os.path.dirname(sys.argv[0]))
        for p in parser:
            self.parsers.append(
                os.path.realpath(os.path.join(base_path, p))
            )
    
    def export(self, target: str):
        if self.local:
            local_gen = os.path.join(target, ScriptsEntry.DEFAULT_GENERATOR)
            shutil.copy(src=self.gen, dst=local_gen)
            self.gen = os.path.basename(local_gen)

            for i, parser in enumerate(self.parsers):
                local_parser = os.path.join(target, os.path.basename(parser))
                shutil.copy(src=parser, dst=local_parser)
                self.parsers[i] = os.path.basename(local_parser)
        else:   
            # we store path with respect to root of dman repo when not local
            root_path = Manager().root_path
            for i, parser in enumerate(self.parsers):
                self.parsers[i] = os.path.relpath(parser, start=root_path)
            self.gen = os.path.relpath(self.gen, start=root_path)

        return {
            'generator': self.gen,
            'parsers': json.dumps(self.parsers),
            'local': json.dumps(self.local)
        }
    
    @classmethod
    def load(cls, path: str, record: dict):
        islocal = json.loads(record['local'])
        path = os.path.realpath(path)
        if not islocal:
            path = Manager().root_path

        parsers = json.loads(record['parsers'])
        for i, p in enumerate(parsers):
            parsers[i] = os.path.realpath(os.path.join(path, p))
        
        genpath = os.path.realpath(os.path.join(path, record['generator']))

        return cls(
            gen=genpath,
            parsers=parsers,
            local=islocal
        )      

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


# source https://medium.com/@vadimpushtaev/python-choosing-subclass-cf5b1b67c696
class DataType(ABC):
    data_types = {}
    type: str = 'Base'

    def __init__(self, file, use_basename=True):
        if use_basename:
            file = os.path.basename(file)
        self.file = file

    @classmethod
    def register(cls, data_type): 
        def decorator(subclass):
            subclass.type = data_type
            cls.data_types[data_type] = subclass
            return subclass
        
        return decorator
    
    def export(self, target):
        self.write(target)
        return {'type': self.type, 'file': self.file}
    
    @classmethod
    def load(cls, path: str, record: dict):
        if record['type'] not in cls.data_types:
            raise ValueError(f'Bad class type {record["type"]}')
        
        return cls.data_types[record['type']].from_file(os.path.join(path, record['file']))
    
    @classmethod
    @abstractmethod
    def from_file(cls, file: str):
        raise NotImplementedError('not implemented')

    @abstractmethod
    def write(self, target: str):
        raise NotImplementedError('not implemented')



@DataType.register('cluster')
class DataCluster(DataType, OrderedDict):
    DEFAULT_CLUSTER = 'cluster.ini'

    def __init__(self, folder: str, use_basename = True, content: OrderedDict = None):
        DataType.__init__(self, folder, use_basename)
        if content is None:
            content = {}
        OrderedDict.__init__(self, **content)
    
    def append(self, entry: 'DataEntry'):
        self[entry.name] = entry
    
    def append_content(self, content: DataType, name: str = None, descr: str = None):
        if name is None:
            name = content.file.split('.')[0]

        if descr is None:
            descr = f'entry -- {name} of type {content.type}'

        self.append(DataEntry(
            name, descr, content
        ))

    @classmethod
    def from_file(cls, file: str):
        record = configparser.ConfigParser()
        record.read(os.path.join(file, DataCluster.DEFAULT_CLUSTER))
        content = DataEntry.load(file, record['Data'])
        return cls(folder=file, content=content)
    
    def write(self, target: str):
        record = configparser.ConfigParser()
        path = os.path.join(target, self.file)

        os.mkdir(path)
        record['Data'] = dict(ChainMap(*reversed([data.export(path) for data in self.values()])))

        with open(os.path.join(path, DataCluster.DEFAULT_CLUSTER), 'w') as configfile:
            record.write(configfile)


@DataType.register('list')
class DataList(DataType, list):
    DEFAULT_RECORD = 'list.ini'

    def __init__(self, folder: str, use_basename: bool = True, content: List['DataEntry'] = None):
        DataType.__init__(self, folder, use_basename)
        if content is None:
            content = []
        list.__init__(self, content)

    def append(self, item: 'DataEntry'):
        list.append(self, item)
    
    def append_content(self, content: DataType, name: str = None, descr: str = None):
        if name is None:
            name = content.file.split('.')[0]

        if descr is None:
            descr = f'entry -- {name} of type {content.type}'

        self.append(DataEntry(
            name, descr, content
        ))

    @classmethod
    def from_file(cls, file: str):
        record = configparser.ConfigParser()
        record.read(os.path.join(file, DataList.DEFAULT_RECORD))
        content = DataEntry.load(file, record['Data'])
        return cls(folder=file, content=content.values())
    
    def write(self, target: str):
        record = configparser.ConfigParser()
        path = os.path.join(target, self.file)

        os.mkdir(path)
        record['Data'] = dict(ChainMap(*reversed([data.export(path) for data in self])))

        with open(os.path.join(path, DataList.DEFAULT_RECORD), 'w') as configfile:
            record.write(configfile)
    



@dataclass
class DataEntry:
    name: str
    description: str
    content: DataType = field(compare=False)

    @abstractmethod
    def export(self, target: str):
        return {self.name : json.dumps({'description': self.description, **self.content.export(target)})}
    
    @classmethod
    def load(cls, path, record):
        res = {}
        for name, v in record.items():
            rec = json.loads(v)
            res[name] = cls(
                name = name, 
                description = rec['description'],
                content=DataType.load(path, rec)
            )
        return res


class Run:
    DEFAULT_RECORD = 'info.ini'
    DEFAULT_RUN_DATE_STRING = '%y-%m-%d-%H%M%S'
    DEFAULT_RUN_TARGET = '.dman/runs'

    def __init__(self, target: str, meta: RunEntry, scripts: ScriptsEntry, config: ConfigEntry = None, timing: TimingEntry = None, data: Dict[str, DataEntry] = None, override: bool = False) -> None:
        self.target = target

        self.meta = meta
        self.scripts = scripts
        if timing is None:
            timing = TimingEntry(datetime.now())
        self.timing = timing
        self.config = config

        self.finished = False
        self.exported = False

        self.override = override

        if data is None:
            data = {}
        self.data = data

    def append(self, data: DataEntry):
        self.data[data.name] = data
    
    def appends(self, name: str, content: DataType):
        descr = f'entry {name} of type {content.type}'
        self.append(DataEntry(
            name, descr, content
        ))

    @property
    def path(self):
        return os.path.join(self.target, self.meta.name)

    def export(self):
        path = self.path
        tmp_file = None
        if os.path.exists(path):
            if self.override:
                tmp_file = tempfile.TemporaryDirectory()
                path = tmp_file.name
            else:
                logging.error('could not export run: {path} exists.')
                return None
        else:
            os.makedirs(path)      # path should not exist at this point


        record = configparser.ConfigParser()
        record['Info'] = {**self.meta.export(path), **self.config.export(path)}
        record['Scripts'] = self.scripts.export(path)
        record['Timing'] = self.timing.export(path)
        record['Data'] = dict(ChainMap(*[data.export(path) for data in self.data.values()]))

        with open(os.path.join(path, Run.DEFAULT_RECORD), 'w') as configfile:
            record.write(configfile)

        if tmp_file is not None:
            shutil.rmtree(self.path)    # delete old run data
            shutil.copytree(src=path, dst=self.path) 
            tmp_file.cleanup()                   
        
        return self.path

    @classmethod
    def load(cls, path):
        record = configparser.ConfigParser()
        record.read(os.path.join(path, Run.DEFAULT_RECORD))

        meta = RunEntry.load(path, record['Info'])
        config = ConfigEntry.load(path, record['Info'])
        scripts = ScriptsEntry.load(path, record['Scripts'])
        timing = TimingEntry.load(path, record['Timing'])
        data = DataEntry.load(path, record['Data'])

        return cls(target=os.path.realpath(os.path.dirname(path)), meta=meta, config=config, scripts=scripts, timing=timing, data=data)

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

        dest = os.path.join(target, meta.name)
        if os.path.exists(dest) and not args.override:
                raise parser.error(f'Output folder already exists: {dest}. Use --override if you want to overwrite its contents.')
            
        scripts = ScriptsEntry.from_argument_parser(parser, args)
        config = ConfigEntry.from_argument_parser(parser, args)
        timing = TimingEntry.from_argument_parser(parser, args, default_start=current_time)
        return cls(target=target, meta=meta, scripts=scripts, config=config, timing=timing, override=args.override)
        

class GeneratorRecord:
    DEFAULT_GEN_FILE = '.dman/gen.ini'

    def __init__(self, name: str) -> None:
        self.name = name

        self.mgr = Manager()
        if not self.mgr.valid:
            sys.exit()

        self.config_path = os.path.join(self.mgr.root_path, GeneratorRecord.DEFAULT_GEN_FILE)
        self.config = configparser.ConfigParser()
        if os.path.exists(self.config_path):
            self.config.read(self.config_path)
        
        if not self.config.has_section(self.name):
            self.config[self.name] = {
                'latest': '', 'time': '', 'runs': json.dumps([])
            }
        
        self.runs : List[str] = json.loads(self.config[self.name]['runs'])

    def save(self):
        with open(self.config_path, 'w') as configfile:
            self.config.write(configfile)
    
    def update(self, path: str, time: str):
        path = os.path.relpath(path, start=self.mgr.root_path)

        # store new run in path (or push to last element)
        if path in self.runs:
            self.runs.remove(path)
        self.runs.append(path)

        # update config for this generator
        self.config[self.name] = {
            'latest': path,
            'time': time,
            'runs': json.dumps(self.runs)
        }
        self.save()
    
    @property
    def latest(self):
        return self.config[self.name]['latest']


class LatestRun:
    def __init__(self, gen_name=str, update: bool = False) -> None:
        self.record = GeneratorRecord(gen_name)
        self.run = None
        self.update = update

    def __enter__(self):
        self.run = Run.load(self.record.latest)
        return self.run
    
    def __exit__(self, exc_type, exc_val, exc_trb):
        if exc_type is not None:
            if not prompt_user('Process encountered an error, do you still want to update the run?'):
                return

        if self.update:
            self.run.override = True
            path = self.run.export()
            self.record.update(path, time=self.run.timing.export()['start'])
        

class Generator:
    """
    Usage: 
        >>> with Generator(name='name'):
        >>>     ...
    """

    def __init__(self, name: str) -> None:
        self.name = name
        self.record = GeneratorRecord(name)

        self.parser = argparse.ArgumentParser(f'{name} generator')
        Run.configure_parser(self.parser)

    def parse(self):
        self.args = self.parser.parse_args()
        self.run = Run.from_argument_parser(self.parser, self.args, generator_name=f'{self.name}')

    def __enter__(self):
        self.parse()
        self.run.timing.start
        return self.run
    
    def __exit__(self, exc_type, exc_val, exc_trb):
        if exc_type is None:
            if not self.run.timing.finished: self.run.timing.stop()

        # export run
        path = self.run.export()

        # record new run
        self.record.update(path, time=self.run.timing.export()['start'])
