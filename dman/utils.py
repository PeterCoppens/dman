import os
import logging
import subprocess


def get_root_folder(folder: str):
    root_path = None
    current_path = os.getcwd()
    while root_path is None:
        if os.path.exists(os.path.join(current_path, folder)):
            root_path = os.path.join(current_path)
        else:
            current_path = os.path.dirname(current_path)
            if os.path.dirname(current_path) == current_path:
                return None

    return root_path


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
    return res.find('nothing to commit') > 0
