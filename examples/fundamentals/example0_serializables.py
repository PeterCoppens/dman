"""
Defining Serializables
========================

This example describes the various ways in which one 
can construct new serializable objects.
"""

# %%
# Introduction
# -----------------
# To run the example you will need the following imports:

import dman
import numpy as np
from dataclasses import dataclass, asdict

from dman.core.serializables import serializable

# %%
# The base objects in ``dman`` are ``serializables``. Any ``serializable``
# instance is defined implicitly such that the following operations 
# return the original object.
#
# .. code-block:: python
# 
#       ser: dict = dman.serialize(obj)
#       res: str = dman.sjson.dumps(ser)
#       ser: dict = dman.sjson.loads(res)
#       assert(obj == dman.deserialize(res))
#
# The goal is that the string ``res`` can be stored in a human readable file.
#
# .. note::
# 
#       We used ``sjson`` instead of ``json`` for dumping the dictionary
#       to a string. This replaces any unserializable objects with 
#       a placeholder string. This corresponds with the ideals behind ``dman``,
#       one of which is that (some) serialization should always be produced. 
#
# By default, several types are serializable. Specifically: ``str``, ``int``,
# ``float``, ``bool``, ``NoneType``, ``list``, ``dict``, ``tuple``. Collections 
# can be nested. Note that ``tuple`` is somewhat of an exception since it 
# is deserialized as a list. We are however able to extend upon these
# basic types, which is the topic of this example.

# %% 
# Creating Serializables
# -------------------------
# There are several ways of creating a ``serializable`` class from scratch.
# You can either do it manually or use some code generation functionality
# build into ``dman``. 
# 
# Manual Definition
# ^^^^^^^^^^^^^^^^^^^
#
# The standard way of defining a serializable is as follows:

@dman.serializable(name='manual')
class Manual:
    def __init__(self, value: str):
        self.value = value

    def __repr__(self):
        return f'Manual(value={self.value})'
    
    def __serialize__(self):
        return {'value': self.value}
    
    @classmethod
    def __deserialize__(cls, ser: dict):
        return cls(**ser)

# %%
# We can serialize the object

test = Manual(value='hello world!')
ser = dman.serialize(test)
res = dman.sjson.dumps(ser, indent=4)
print(res)
# %%
# Note how the dictionary under ``_ser__content`` is the output of our ``__serialize__``
# method. The type name is also added such that the dictionary can be interpreted
# correctly. We can ``deserialize`` a dictionary created like this as follows:

ser = dman.sjson.loads(res)
test = dman.deserialize(ser)
print(test)

# %%
# .. note::
#     It is possible to not include the serializable type and deserialize
#     by specifying the type manually using the following syntax
#
#     .. code-block:: python
#
#         ser = dman.serialize(test, content_only=True)
#         reconstructed: Manual = dman.deserialize(ser, ser_type=Manual)

# %%
# .. warning::
#     The name provided to ``@serializable`` should be unique within
#     your library. It is used as the identifier of the class by ``dman``
#     when deserializing.


# %%
# Automatic Generation
# ^^^^^^^^^^^^^^^^^^^^^^
# Of course it would not be convenient to manually specify the ``__serialize__``
# and ``__deserialize__`` methods. Hence, the ``serializable`` decorator
# has been implemented to automatically generate them whenever 
# the class is an instance of ``Enum`` or a ``dataclass`` (and when no prior ``__serialize__``
# and ``__deserialize__`` methods are specified). 
#
# So in the case of enums:

from enum import Enum

@dman.serializable(name='mode')
class Mode(Enum):
    RED = 1
    BLUE = 2

ser = dman.serialize(Mode.RED)
print(dman.sjson.dumps(ser, indent=4))

# %%
# In the case of ``dataclasses`` we get the following:

from dataclasses import dataclass

@dman.serializable(name='dcl_basic')
@dataclass
class DCLBasic:
    value: str

test = DCLBasic(value='hello world!')
ser = dman.serialize(test)
print(dman.sjson.dumps(ser, indent=4))


# %%
# As long as all of the fields in the dataclass are serializable, the whole
# will be as well. 
#
# .. warning::
#
#     Be careful when specifying the name that it is unique. It 
#     is used to reconstruct an instance of a class based on the 
#     ``_ser__type`` string. If a name is left unspecified, the value 
#     under ``__name__`` in the class will be used.
#
#
# .. warning::
#
#     In almost all cases it will be better to use ``@dman.modelclass``
#     when converting a ``dataclass`` into a ``serializable``.
#     This is mostly important when some fields are ``storable``,
#     in which case they will be handled automatically.  See :ref:`sphx_glr_gallery_fundamentals_example3_models.py`
#     for an overview of the ``modelclass`` decorator.
#
# .. note::
#
#     It is possible to have fields in your dataclass that you don't 
#     want serialized. ''
#
#     .. code-block:: python
#
#         from dataclasses import dataclass
#
#         @serializable(name='dcl_basic')
#         @dataclass
#         class DCLBasic:
#             __no_serialize__ = ['hidden']
#             value: str
#             hidden: int = 0
#
#     The field names in ``__no_serialize__`` will not be included 
#     in the serialized ``dict``. Note that this means that you should
#     specify a default value for these fields to support deserialization.

# %%
# Serializing Existing Types
# -----------------------------
# 
# Often you will already have some objects in a library that should 
# also be made serializable. In ``dman`` we provide some functionality 
# that makes this process simpler.
#
# Registered Definition
# ^^^^^^^^^^^^^^^^^^^^^^^^
# 
# The most flexible way of making a class serializable is by registering it 
# manually. This is especially useful when the original class definition 
# cannot be manipulated (for example for ``numpy.ndarray``).
#
# Say we have some frozen class definition:
class Frozen:    
    def __init__(self, data: int):
        self.data = data
    
    def __repr__(self):
        return f'{self.__class__.__name__}(data={self.data})'

# %%
# We can make it serializable without touching the original class 
# definition as follows:
dman.register_serializable(
    'frozen',
    Frozen,
    serialize=lambda frozen: frozen.data,
    deserialize=lambda data: Frozen(data)
)

# %%
# Now we can serialize frozen itself:
frozen = Frozen(data=42)
ser = dman.serialize(frozen)
res = dman.sjson.dumps(ser, indent=4)
print(res)

# %%
# And deserialize it
ser = dman.sjson.loads(res)
frozen = dman.deserialize(ser)
print(frozen)

# %%
# You can take a look at ``dman.numerics`` to see an example of this 
# in practice.

# %%
# Templates
# ^^^^^^^^^^^^^^^^^^^
#
# In many cases however it will be possible to alter the 
# original class.
#
# So say we have some user class that is used all throughout 
# your library:
class User:    
    def __init__(self, name: int):
        self.name = name
    
    def __repr__(self):
        return f'{self.__class__.__name__}(id={self.name})'

# %%
# We would like to make ``User`` serializable without 
# defining ``__serialize__`` and ``__deserialize__`` manually.
# We can do so using a template:
@dman.serializable
@dataclass
class UserTemplate:
    name: str

    @classmethod
    def __convert__(cls, other: 'User'):
        return cls(other.name)
    
    def __de_convert__(self):
        return User(self.name)

# %%
# A template has a method that allows conversion from the 
# original class to the template and a method 
# to undo that conversion.

# %%
# Using a template we can then make ``User`` itself serializable like this:
serializable(User, name='user', template=UserTemplate)

# %%
# Now we can serialize a user:
user = User(name='Thomas Anderson')
ser = dman.serialize(user)
res = dman.sjson.dumps(ser, indent=4)
print(res)

# %%
# However this does make an adjustment to the class.
# Specifically a field ``_ser__type`` is added:
print(getattr(User, '_ser__type'))

# %% 
# Using templates can also be useful when 
# you are able to work with subclasses of some ``Base`` class
# instead.
#
# So say you start with some ``Base`` class:
class Base:
    def __init__(self, data: int, computation: int = None):
        self.data = data
        self.computation = computation 
    
    def compute(self):
        self.computation = self.data**2
    
    def __repr__(self):
        return f'{self.__class__.__name__}(data={self.data}, computation={self.computation})'

# %% 
# We want to create a subtype of this class that is serializable without 
# defining the ``__serialize__`` method manually. 

@dman.serializable
@dataclass
class Template:
    data: int
    computation: int 

    @classmethod
    def __convert__(cls, other: 'SBase'):
        return cls(other.data, other.computation)


@dman.serializable(name='base', template=Template)
class SBase(Base): ...

# %%
# So we defined a template class with a convert method from ``Base`` and 
# similarly we defined a serializable subclass of ``Base`` that 
# can be converted from ``Template``. Now we can serialize an instance of ``SBase``
# as follows:

base = SBase(data=25)
base.compute()
ser = dman.serialize(base)
res = dman.sjson.dumps(ser, indent=4)
print(res)

# %% 
# And we can deserialize it too

ser = dman.sjson.loads(res)
base = dman.deserialize(ser)
print(base)

# %% 
# Note how we did not specify in the above example how to 
# go from an instance of ``Template`` to one of ``SBase``. 
# Such a ``__convert__`` method was actually generated automatically. 
# We could have instead specified the same behavior manually as follows:

@dman.serializable(name='base', template=Template)
class SBase(Base):
    @classmethod
    def __convert__(cls, other: Template):
        return cls(**asdict(other))

# %%
# Specifying this conversion manually could be 
# relevant if the fields of the ``Template`` dataclass
# do not match the ones for the ``__init__`` method of ``Base``. 
# For example we could have had:

class Base:
    def __init__(self, data: int):
        self.data = data
        self.computation = None 
    
    def compute(self):
        self.computation = self.data**2
    
    def __repr__(self):
        return f'{self.__class__.__name__}(data={self.data}, computation={self.computation})'

# %%
# So the value of ``computation`` cannot be passed to the constructor.
# We can however compensate for this in the ``__convert__`` method:

@dman.serializable(name='base', template=Template)
class SBase(Base):
    @classmethod
    def __convert__(cls, other: Template):
        res = cls(other.data)
        res.computation = other.computation
        return res

# %%
#
# Serializing Instances
# --------------------------------
#
# In some settings it is useful to serialize instances directly. One common
# example is methods.
from math import sqrt
@dman.register_instance(name='ell1')
def ell1(x, y):
    return abs(x) + abs(y)
@dman.register_instance(name='ell2')
def ell2(x, y):
    return sqrt(x**2 + y**2)

# %%
# When serializing the result looks as follows:
ser = dman.serialize([ell1, ell2])
dman.tui.print_serialized(ser)

# %%
# Deserialization then works as expected.
dser = dman.deserialize(ser)
print(dser)

# %%
# For specific instances we can also call `register_instance` inline. 

class Auto: ...
AUTO = Auto()
dman.register_instance(AUTO, name='auto')
dman.tui.print_serialized(dman.serialize(AUTO))



