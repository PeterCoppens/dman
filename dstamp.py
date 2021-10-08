import subprocess
import argparse
import configparser
import logging
import os

from datetime import datetime

ROOT_FOLDER = '.stamp'
STAMP_FOLDER='stamps'
STAMP_CONFIG = 'config.ini'
STAMP_NAME = 'dstamp'


def get_git_hash():
    subprocess.check_output(['git', 'rev-parse', 'HEAD']).decode('ascii').strip()


def configure_log(args):
    numeric_level = getattr(logging, args.log.upper(), None)
    if not isinstance(numeric_level, int):
        raise parser.error('Invalid log level: %s' % args.log.upper())
    logging.basicConfig(level=numeric_level)


def init(args):
    if os.path.exists(ROOT_FOLDER):
        logging.info('Reinitialized existing {STAMP_NAME} project.')
        return
    logging.info(f'Initializing {STAMP_NAME} project: {ROOT_FOLDER}')
    os.mkdir(ROOT_FOLDER)
    os.mkdir(os.path.join(ROOT_FOLDER, STAMP_FOLDER))
    config = configparser.ConfigParser()
    config['Info'] = {
        'Dependencies' : [],
    }
    
    with open(os.path.join(ROOT_FOLDER, STAMP_CONFIG), 'w') as configfile:
        config.write(configfile)

def load(args):
    root_path = None
    current_path = os.getcwd()
    while root_path is None:
        if os.path.exists(os.path.join(current_path, ROOT_FOLDER)):
            root_path = os.path.join(current_path)
        else:
            current_path = os.path.dirname(current_path)
            if os.path.dirname(current_path) == current_path:
                logging.error(f'could not find {ROOT_FOLDER} folder')
                return
    
    config = configparser.ConfigParser()
    config.read(os.path.join(root_path, ROOT_FOLDER, STAMP_CONFIG))
    return config, root_path


def stamp(args):
    _, root_path = load(args)
    hash = get_git_hash()
    name = args.name
    time = datetime.now()

    file_name = f'{name}-{time.strftime("%y%m%d%H%M%S")}'

    contents = configparser.ConfigParser()
    contents['Stamp'] = {
        'name': name,
        'time': time.strftime("%d/%m/$y %H:%M:%S"),
        'hash': hash
    }

    with os.open(os.path.join(root_path, ROOT_FOLDER, STAMP_FOLDER, file_name), 'w') as f:
        contents.write(f)


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)

    parser = argparse.ArgumentParser()

    parser.add_argument(
        '--log',
        dest='log',
        default='WARNING',
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

    args = parser.parse_args()
    if hasattr(args, 'execute'):
        args.execute(args)
    else:
        parser.print_help()
    