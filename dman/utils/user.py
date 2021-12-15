import argparse
from dataclasses import field, fields
import logging
import copy


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


PARSE = '__parse__'


def arg(name=None, **kwargs):
    res = field(init=True, repr=True, metadata={
        '__is_arg': True, 'name': name, 'kwargs': kwargs
    })
    return res


def parse(cls, args):
    res = dict()
    for f in fields(cls):
        res[f.name] = getattr(args, f.name, None)
    return cls(**res)

def add_to_parser(cls, parser: argparse.ArgumentParser):
    for f in fields(cls):
        if f.metadata.get('__is_arg', False):
            name = f.metadata['name']
            if name is None:
                name = f.name
                
            kwargs: dict = copy.copy(f.metadata['kwargs'])
            action = kwargs.get('action', None)
            if not action:
                kwargs['type'] = f.type

            if len(name) > 0 and name[0] == '-':
                parser.add_argument(name, dest=f.name, **kwargs)
            else:
                parser.add_argument(name, **kwargs)

