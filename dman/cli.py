import argparse
from dman.core.path import get_root_path



def init_dman():
    get_root_path(create=True)

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

    # == parse arguments =======================================================
    args = parser.parse_args()
    execute = getattr(args, 'execute', None)
    if execute:
        execute(args)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()