from dman import track, modelclass, dataclass
from dman.numeric import barray, barrayfield

import numpy as np

from dman.persistent.serializables import serializable

@dataclass
class Base:
    data: np.ndarray


@modelclass(name='template')
class Template:
    data: barray = barrayfield(stem='data')


@modelclass(name='sub', template=Template)
class Sub(Base): ...


class BaseManual:
    def __init__(self, a: str = 'hello'):
        self.a = a


@serializable(name='template_manual')
class TemplateManual:
    def __init__(self, a: str = 'hello'):
        self.a = a
    
    def __serialize__(self):
        return self.a

    @classmethod
    def __deserialize__(cls, ser):
        return cls(ser)
    
    @classmethod
    def __convert__(cls, other: BaseManual):
        return cls(other.a)


@serializable(name='sub_manual', template=TemplateManual)
class SubManual(BaseManual):
    @classmethod
    def __convert__(cls, other: TemplateManual):
        return cls(other.a)


    
def main():
    with track('sub', default_factory=lambda: Sub(np.eye(2)), verbose=True) as sub:
        sub: Sub = sub
        print(sub.data)
        sub.data = np.eye(2)

    with track('sub_manual', default_factory=lambda: SubManual(), verbose=True) as sub: ...
    

if __name__ == '__main__':
    main()