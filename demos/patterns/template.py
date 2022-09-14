"""
Templates
------------------

These are used when you want to make a class in a library serializable 
while changing a minimal amount of the original class.

All you need to define is methods used to convert between a template 
and the original class of interest. There are a couple of ways of doing so 

1. When both are dataclasses conversion is generated automatically
2. You can add a __convert__ method to both classes 
3. You can add a __convert__ and __de_convert__ to the template class
    this is useful when you want to make the original type itself serializable.
    
"""


from dman import track, modelclass, dataclass
from dman.numeric import barray, barrayfield

import numpy as np

from dman.core.serializables import serializable

# ------------------------------------------------------------------------------
# 1. automatic generation
# ------------------------------------------------------------------------------

@dataclass
class Base:
    """
    Library class (cannot be adjusted).
    """
    data: np.ndarray


@modelclass(name='template')
class Template:
    """
    Template class defining how the ``Base`` class should be stored.
    """
    data: barray = barrayfield(stem='data')


@modelclass(name='sub', template=Template)
class Sub(Base): 
    """
    The serializable version of ``Base``. When trying to serialize an 
    instance of ``Base`` it should be converted to this type first.
    """
    ...

# ------------------------------------------------------------------------------
# 1. two __convert__
# ------------------------------------------------------------------------------

class BaseManual:
    """
    Library class (cannot be adjusted).
    """
    def __init__(self, a: str = 'hello'):
        self.a = a


@serializable(name='template_manual')
class TemplateManual:
    """
    Template class defining how the ``BaseManual`` class should be stored.
    """
    def __init__(self, a: str = 'hello'):
        self.a = a
    
    def __serialize__(self):
        return self.a

    @classmethod
    def __deserialize__(cls, ser):
        return cls(ser)
    
    @classmethod
    def __convert__(cls, other: BaseManual):
        """
        Manually defined conversion from ``BaseManual`` to this type.
        """
        return cls(other.a)


@serializable(name='sub_manual', template=TemplateManual)
class SubManual(BaseManual): 
    """
    The serializable version of ``Base``. When trying to serialize an 
    instance of ``Base`` it should be converted to this type first.
    """
    @classmethod
    def __convert__(cls, other: TemplateManual):
        """
        Manually defined conversion from ``TemplateManual`` to this type.
        """
        return cls(other.a)
    

# ------------------------------------------------------------------------------
# 1. two __convert__
# ------------------------------------------------------------------------------
@dataclass
class Direct(Base):
    """
    Library class (cannot be adjusted).
    """
    def update(self):
        self.data = 2*self.data


@modelclass(name='template_deconvert')
class SubDeconvert:
    """
    Template class defining how the ``Direct`` class should be stored.
    """
    data: barray = barrayfield(stem='data')

    @classmethod
    def __convert__(cls, other: Direct):
        """
        Manually defined conversion from ``Direct`` to this type.
        """
        return cls(other.data)
    
    def __de_convert__(self):
        """
        Manually defined conversion from this type to ``Direct``.
        """
        return Direct(self.data)


"""
We can make ``Direct`` serializable without access to its source code.
    Note that its signature is altered, since a __serialize__ and 
    __deserialize__ method are added. This is not always possible.

    The module including this line should be imported before
    running any (de)serialization as well.
"""
serializable(Direct, name='direct', template=SubDeconvert)




    
def main():
    verbose = False
    with track('sub', default_factory=lambda: Sub(np.eye(2)), verbose=verbose) as sub:
        sub: Sub = sub
        print(sub.data)
        sub.data = 2*sub.data

    with track('sub_manual', default_factory=lambda: SubManual(), verbose=verbose) as sub:
        sub: SubManual = sub
        print(sub.a)
        sub.a = sub.a + '!'

    with track('sub_deconvert', default_factory=lambda: Direct(np.ones(2)), verbose=verbose) as sub:
        sub: Direct = sub
        print(sub.data)
        sub.update()
    

if __name__ == '__main__':
    main()