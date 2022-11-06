import os
from pathlib import Path
from tempfile import TemporaryDirectory
from dman.model.record import Context
from dman.core.path import Target, UserQuitException, MountException


from record_test import temporary_context


def test_target_management():
    with temporary_context() as ctx:
        t = ctx.absolute('test.txt')
        assert t == 'test.txt'
        loc = ctx.join('subdir')
        t = loc.absolute('test.txt')
        assert t == os.path.join('subdir', 'test.txt')
    
    with temporary_context() as ctx:
        loc, t = ctx.prepare('test.txt')
        assert loc.subdir == ''
        assert t == 'test.txt'
        
        try:
            ctx.prepare('test.txt', choice='quit')
            assert False
        except UserQuitException:
            assert True
        
        ctx.remove('test.txt')
        ctx.prepare('test.txt', choice='quit')

        loc, t = ctx.prepare(os.path.join('subdir', 'test.txt'))
        assert loc.subdir == 'subdir'
        assert t == 'test.txt'
        
        try:
            ctx.prepare(os.path.join('subdir', 'test.txt'), choice='quit')
            assert False
        except UserQuitException:
            assert True
        
        ctx.remove(os.path.join('subdir', 'test.txt'))
        ctx.prepare(os.path.join('subdir', 'test.txt'), choice='quit')

    with temporary_context() as ctx:
        try:
            ctx.prepare('/test.txt')
            assert False
        except MountException:
            assert True

        with TemporaryDirectory() as tdir:
            path = os.path.join(tdir, 'test.txt')
            Path(path).touch()
            ctx.remove(path)
            assert os.path.exists(path)  # file was not removed

