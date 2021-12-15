from dman.utils.smartdataclasses import Wrapper, MISSING, wrapfield, wrappedclass


if __name__ == '__main__':
    class PrintWrapper(Wrapper):
        def __process__(self, obj, wrapped):
            print(f'[processing] {wrapped} for {obj}')
            return wrapped

        def __store__(self, obj, value, currentvalue):
            if currentvalue is not MISSING:
                print(f'[storing] {value} for {obj} from {currentvalue}')
            else:
                print(f'[storing] {value} for {obj}')
            return value

    @wrappedclass
    class Foo:
        a: str = wrapfield(PrintWrapper(), default='hi')

    foo = Foo(a='hello')
    print(foo)
    print(foo.a)
    foo.a = 'world'
    print(foo.a)
