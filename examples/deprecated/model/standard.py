import dman


@dman.storable
@dman.serializable
class TestSto:
    __ext__ = '.tst'

    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return f'TestSto({self.name})'

    def __serialize__(self):
        return {'name': self.name}

    @classmethod
    def __deserialize__(cls, ser):
        return cls(**ser)

    def __write__(self, path):
        with open(path, 'w') as f:
            f.write(self.name)

    @classmethod
    def __read__(cls, path):
        with open(path, 'r') as f:
            return cls(f.read())

def main():
    lst = [TestSto('test')]
    dman.save('lst', lst)
    print(dman.load('lst')[0])

    dct = {'a': TestSto('test')}
    dman.save('dct', dct)
    print(dman.load('dct')['a'])


if __name__ == '__main__':
    main()