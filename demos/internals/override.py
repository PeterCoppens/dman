from dman.utils.smartdataclasses import is_complete, overrideable, dataclass


if __name__ == '__main__':
    @dataclass
    @overrideable
    class Over:
        a: str
        b: int
        c: int = 5
    
    @overrideable
    class OverOver:
        b: Over
        c: int = 25

    m1 = Over(a='test')
    m2 = Over(a='hello', b=5)

    print(is_complete(m1))
    print(is_complete(m2))

    # starting from m1, if m2 has an assigned value, override it
    # i.e., m1 is the default, m2 overrides

    # m1.a (default) = 'test << m2.b = 'hello', m1.b (default) = AUTO << m2.b = 5
    print(m1 << m2)  

    # the reverse operation
    # m2.a (default) = 'hello << m1.b = 'test', m2.b (default) = 5 remains five since m1.b = AUTO (i.e., unassigned)
    print(m2 << m1)

    m3 = OverOver(b=m1, c=38)
    m4 = OverOver(b=m2)
    print(m3 << m4)     # m1 << m2
    print(m4 << m3)     # m2 << m1

    
