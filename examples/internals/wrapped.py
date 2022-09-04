from dman.utils.smartdataclasses import wrapfield, wrappedclass


if __name__ == '__main__':
    def print_wrapper(key: str):
        def _fget(obj):
            print(f'[getting] {key} for {obj}')
            return getattr(obj, f'_{key}')

        def _fset(obj, value):
            print(f'[setting] {key} for {obj} to {value}')
            return setattr(obj, f'_{key}', value)
        
        return property(_fget, _fset)


    @wrappedclass
    class Foo:
        b: str
        a: str = wrapfield(print_wrapper, default='hi')

    foo = Foo(b='test', a='hello')
    print(foo)
    print(foo.a)
    foo.a = 'world'
    print(foo.a)
