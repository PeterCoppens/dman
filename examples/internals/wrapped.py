from dman.utils.smartdataclasses import WrapField, wrapfield, wrappedclass


if __name__ == '__main__':
    class PrintWrapper(WrapField):
        def __call__(self, key: str):
            def _fget(obj):
                print(f'[getting] {key} for {obj}')
                return getattr(self, key)

            def _fset(obj, value):
                print(f'[setting] {key} for {obj} to {value}')
                return setattr(self, key, value)
            
            return property(_fget, _fset)


    @wrappedclass
    class Foo:
        b: str
        a: str = wrapfield(PrintWrapper(), default='hi')

    foo = Foo(b='test', a='hello')
    print(foo)
    print(foo.a)
    foo.a = 'world'
    print(foo.a)
