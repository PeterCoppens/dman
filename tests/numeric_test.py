from dman.numeric import sarray, barray, carray, np
from dman.model.modelclasses import modelclass, recordfields


def test_container():
    @modelclass
    class Container:
        a: sarray[int]
        b: sarray[float]
        c: carray[int]
        d: barray[int]

    container = Container(np.zeros(1), np.ones(1), np.ones(1), np.ones(1))
    assert isinstance(container.a, sarray)
    assert isinstance(container.a, sarray[int])
    assert not isinstance(container.a, sarray[float])
    assert isinstance(container.a[0], np.int64)

    assert isinstance(container.b, sarray)
    assert isinstance(container.b, sarray[float])
    assert isinstance(container.b[0], np.float64)

    assert isinstance(container.c, carray)
    assert isinstance(container.c, carray[int])
    assert isinstance(container.c[0], np.int64)

    assert isinstance(container.d, barray)
    assert isinstance(container.d, barray[int])
    assert isinstance(container.d[0], np.int64)
    assert 'd' in recordfields(Container)

    lst = ['a', 'b']
    assert lst[container.a[0]] == 'a'
    assert lst[container.c[0]] == 'b'