from dman.utils.smartdataclasses import wrapfield, wrappedclass
import inspect


def test_getter():
    class T_Descriptor:
        validate = False

        def __get__(self, obj, objtype=None):
            self.__class__.validate = True

    @wrappedclass
    class Boo:
        a: str = wrapfield(T_Descriptor())

    # field a not added to init by default.
    p = inspect.signature(Boo.__init__).parameters
    assert "a" not in p and "self" in p

    # check if get is called
    Boo().a
    assert T_Descriptor.validate


def test_setter():
    class T_Descriptor:
        def __set__(self, obj, value):
            setattr(obj, "_wrapped", value)

    descr = T_Descriptor()

    @wrappedclass
    class Boo:
        a: str = wrapfield(descr)

    # field a is added to init.
    p = inspect.signature(Boo.__init__).parameters
    assert "a" in p and "self" in p
    boo = Boo(a="test")
    assert getattr(boo, "_wrapped") == "test"
    assert boo.a is descr


def test_name():
    class T_Descriptor:
        last = None

        def __set_name__(self, owner, name):
            self.__class__.last = "name"
            self.public_name = name
            self.private_name = f"_{name}"

        def __get__(self, obj, objtype=None):
            self.__class__.last = "get"
            return getattr(obj, self.private_name)

        def __set__(self, obj, value):
            self.__class__.last = "set"
            setattr(obj, self.private_name, value)

    descr = T_Descriptor()

    @wrappedclass
    class Boo:
        a: str = wrapfield(descr)

    assert T_Descriptor.last == "name"

    # field a is added to init.
    p = inspect.signature(Boo.__init__).parameters
    assert "a" in p and "self" in p

    boo = Boo(a="test0")
    assert getattr(boo, "_a") == "test0"
    assert T_Descriptor.last == "set"
    assert boo.a == "test0"
    assert T_Descriptor.last == "get"
    boo.a = "test1"
    assert getattr(boo, "_a") == "test1"
    assert T_Descriptor.last == "set"
    assert boo.a == "test1"
    assert T_Descriptor.last == "get"


def test_property():
    descr = property(lambda obj: getattr(obj, '_a'), lambda obj, value: setattr(obj, '_a', value))

    @wrappedclass
    class Boo:
        a: str = wrapfield(descr)

    # field a is added to init.
    p = inspect.signature(Boo.__init__).parameters
    assert "a" in p and "self" in p

    boo = Boo(a="test0")
    assert getattr(boo, "_a") == "test0"
    assert boo.a == "test0"
    boo.a = "test1"
    assert getattr(boo, "_a") == "test1"
    assert boo.a == "test1"


if __name__ == '__main__':
    test_name()