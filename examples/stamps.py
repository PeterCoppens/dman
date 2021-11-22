from dman.core import Stamp

if __name__ == '__main__':
    print(Stamp.create(name='hello', dependencies={'test': 'test'}))