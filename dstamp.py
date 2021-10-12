import argparse
import logging

from dman.stamp import Manager, Dependecy

def configure_log(args):
    numeric_level = getattr(logging, args.log.upper(), None)
    if not isinstance(numeric_level, int):
        raise parser.error('Invalid log level: %s' % args.log.upper())
    logging.basicConfig(level=numeric_level)


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
    dstamp.save()

def remove_stamp(args):
    dstamp = Manager()
    if args.label == dstamp.latest:
        logging.error(f'Cannot remove latest stamp {args.label}.')
        return
    dstamp.remove_stamp(args.label)

def list_stamps(args):
    dstamp = Manager()
    for stamp in dstamp.stamps:
        print(stamp)

def info_stamp(args):
    dstamp = Manager()
    print(dstamp.get_stamp(args.label).info)

def latest_stamp(args):
    dstamp = Manager()
    print(dstamp.get_stamp(dstamp.latest).info)


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
    init_parser.set_defaults(execute=Manager.init_repo)

    stamp_parser = subparsers.add_parser('new', help='create a stamp of the current repository state')
    stamp_parser.set_defaults(execute=stamp)
    stamp_parser.add_argument(
        'name',
        type=str,
        help='name of the stamp'
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

    rem_stamp_parser = subparsers.add_parser('remove', help='remove a stamp')
    rem_stamp_parser.set_defaults(execute=remove_stamp)
    rem_stamp_parser.add_argument(
        'label',
        type=str,
        help='label of stamp'
    )

    list_stamp_parser = subparsers.add_parser('list', help='list stamps')
    list_stamp_parser.set_defaults(execute=list_stamps)

    info_stamp_parser = subparsers.add_parser('info', help='get info on stamp')
    info_stamp_parser.set_defaults(execute=info_stamp)
    info_stamp_parser.add_argument(
        'label',
        type=str,
        help='label of stamp'
    )

    latest_stamp_parser = subparsers.add_parser('latest', help='get info on latest stamp')
    latest_stamp_parser.set_defaults(execute=latest_stamp)

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
    