import os
import logging
import subprocess



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
