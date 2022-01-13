import argparse
from dataclasses import dataclass
import logging

import os

from dman.core import DMan, Stamp, Dependency, init_dman
from dman.persistent.serializables import isvalid
from dman.repository import get_root_path
from dman.utils.git import check_git_committed
from dman.utils.user import add_to_parser, arg, parse, prompt_user


def check_repositories(dman: DMan):
    def prompt(path: os.PathLike):
        prompt_user(f'Git repository at {path} has unstaged changes. Do you want to proceed?')

    # check this repository
    if not check_git_committed() and not prompt(os.getcwd()):
        return False

    # check dependend repositories
    for v in dman.dependencies.values():
        dep: Dependency = v
        cwd = os.path.join(get_root_path(), dep.path)
        if not check_git_committed(cwd=cwd) and not prompt(cwd):
            return False

    return True


def main():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(
        title='commands', 
        description='dman supports the actions listed below', 
        help='options'
    )

    # == init command ==============================================
    init_parser = subparsers.add_parser(
        'init', 
        help='initialize dman in this folder'
    )
    init_parser.set_defaults(
        execute=lambda _: init_dman()
    )

    # == new command ===========================================================
    stamp_parser = subparsers.add_parser(
        'new', 
        help='create a stamp of the current repository state'
    )
    
    @dataclass
    class StampArgs:
        name: str = arg('--name', default=None, help='name of the stamp')
        msg: str = arg('-m', default='', help='stamp description')
        prompt: bool = arg(
            '-y', action='store_true', help='accept prompts automatically'
        )

    def stamp(args):
        args: StampArgs = parse(StampArgs, args)
        with DMan() as dman:
            if args.prompt or not check_repositories(dman):
                dman.stamp(name=args.name, msg=args.msg)
    
    stamp_parser.set_defaults(execute=stamp)
    add_to_parser(StampArgs, stamp_parser)

    # == remove stamp command ==================================================
    rem_stamp_parser = subparsers.add_parser(
        'remove',
        help='remove a stamp'
    )
    
    @dataclass
    class StampLabelArgs:
        label: str = arg(help='label of stamp to remove')
        def get(self, dman: DMan):
            if self.label not in dman.stamps:
                logging.error(f'stamp {self.label} does not exist')
                return None
            stamp: Stamp = dman.stamps[self.label]
            if not isvalid(stamp):
                logging.error(f'stamp {self.label} does not exist')
                return None
            return stamp

    
    def remove_stamp(args):
        args: StampLabelArgs = parse(StampLabelArgs, args)
        with DMan() as dman:
            stamp: Stamp = args.get(dman)
            if stamp:
                del dman.stamps[args.label]
    
    rem_stamp_parser.set_defaults(execute=remove_stamp)
    add_to_parser(StampLabelArgs, rem_stamp_parser)

    # == list stamps ===========================================================
    list_stamp_parsers = subparsers.add_parser(
        'list', help='list stamps'
    )

    def list_stamps(_):
        with DMan() as dman:
            for k in dman.stamps:
                if k != '__latest__':
                    print(k)

    list_stamp_parsers.set_defaults(execute=list_stamps)

    # == info stamps ===========================================================
    info_stamp_parser = subparsers.add_parser(
        'info', help='get info on stamp'
    )

    def info_stamp(args):
        args: StampLabelArgs = parse(StampLabelArgs, args)
        with DMan() as dman:
            stamp: Stamp = args.get(dman)
            if stamp:
                del dman.stamps[args.label]
    
    info_stamp_parser.set_defaults(execute=info_stamp)
    add_to_parser(StampLabelArgs, info_stamp_parser)

    # == latest stamp ==========================================================
    latest_stamp_parser = subparsers.add_parser(
        'latest', help='get info on latest stamp'
    )

    def latest_stamp(_):
        with DMan() as dman:
            stamp: Stamp = dman.stamps.get(dman.latest(), None)
            if stamp:
                if isvalid(stamp):
                    stamp.display()
                else:
                    logging.error('the latest stamp is invalid')
                return
            if '__latest__' in dman.stamps:
                del dman.stamps['__latest__']
                logging.error('no latest stamp could be found')
                return
            logging.error('the latest stamp is invalid')

    latest_stamp_parser.set_defaults(execute=latest_stamp)

    # == dependency parser =====================================================
    dep_parser = subparsers.add_parser(
        'dep', help='alter dependencies'
    )
    dep_subparser = dep_parser.add_subparsers(
        title='commands', description='dman supports the actions listed below', 
        help='options'
    )

    # == add dependency parser =================================================
    add_dep_parser = dep_subparser.add_parser(
        'add', help='add dependency'
    )

    @dataclass
    class DependencyArg:
        path: str = arg(help='path of dependency')
    
    def add_dependency(args):
        args: DependencyArg = parse(DependencyArg, args)
        with DMan() as dman:
            dman.add_dependency(args.path)

    add_dep_parser.set_defaults(execute=add_dependency)
    add_to_parser(DependencyArg, add_dep_parser)

    # == rem dependency parser =================================================
    rem_dep_parser = dep_subparser.add_parser(
        'remove', help='remove dependency'
    )

    @dataclass
    class DependencyNameArg:
        name: str = arg(help='name of dependency')

        def exists(self, dman: DMan):
            if self.name not in dman.dependencies:
                logging.error(f'dependency {self.name} does not exist')
                return False
            return True
    
    def remove_dependency(args):
        args: DependencyNameArg = parse(DependencyNameArg, args)
        with DMan() as dman:
            if args.exists(dman):
                del dman.dependencies[args.name]        

    rem_dep_parser.set_defaults(execute=remove_dependency)
    add_to_parser(DependencyNameArg, rem_dep_parser)
    
    # == info dependency =======================================================
    info_dep_parser = dep_subparser.add_parser(
        'info', help='get info about dependency'
    )

    def info_dependency(args):
        args: DependencyNameArg = parse(DependencyNameArg, args)
        with DMan() as dman:
            if args.exists(dman):
                dep: Dependency = dman.dependencies[args.name]
                dep.display()

    info_dep_parser.set_defaults(execute=info_dependency)
    add_to_parser(DependencyNameArg, info_dep_parser)

    # == list dependency =======================================================
    list_dep_parser = dep_subparser.add_parser(
        'list', help='list dependencies'
    )
    def list_dependency(_):
        with DMan() as dman:
            for dep in dman.dependencies:
                print(dep)

    list_dep_parser.set_defaults(execute=list_dependency)

    # == parse arguments =======================================================
    args = parser.parse_args()
    execute = getattr(args, 'execute', None)
    if execute:
        execute(args)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()