"""
Error handling
========================

We show how errors are handled within ``dman``.
"""

# %%
# Below are some general import statements required for this script.
import sys
from tempfile import TemporaryDirectory
import traceback
import dman
from dman import tui
from dman import log

# turn off warnings
log.defaultConfig(level=log.CRITICAL)  

# %%
# Serializables
# ---------------------------------------

# %%
# We provide an overview of some basic error behavior implemented in ``dman``
# and how this is represented.
#
# We first serialize an unserializable type:


class Base:
    ...


ser = dman.serialize(Base())
tui.print_serialized(ser)


# %%
# Next let's try serialization of an object with an erroneous implementation
# of `__serialize__`.


@dman.serializable(name="base")
class Base:
    def __serialize__(self):
        raise RuntimeError("Invalid implementation")

    @classmethod
    def __deserialize__(cls, ser):
        ...


ser = dman.serialize(Base())
tui.print_serialized(ser)
err = dman.deserialize(ser)
print(err)

# %%
# We also detect `__serialize__` methods with invalid signatures.


@dman.serializable(name="base")
class Base:
    # `__serialize__` should either have no or two arguments besides `self`.
    def __serialize__(self, arg1, arg2):
        return 'Base'

    @classmethod
    def __deserialize__(cls, ser):
        raise RuntimeError('Invalid implementation')


ser = dman.serialize(Base())
tui.print_serialized(ser)

# %%
# Now we move on to deserialization.


@dman.serializable(name="base")
class Base:
    def __serialize__(self):
        return '<base>'

    @classmethod
    def __deserialize__(cls, ser):
        raise RuntimeError('Invalid implementation')


ser = dman.serialize(Base())
tui.print_serialized(ser)
err = dman.deserialize(ser)
print(err)

# %%
# Note how the error contains information about what was serialized.
# The error is serializable.
ser = dman.serialize(ser)
tui.print_serialized(ser)

# %%
# Moreover when we try to deserialize it again, now with a valid 
# class definition, things work. This sometimes allows for data restoration.


@dman.serializable(name="base")
class Base:
    def __serialize__(self):
        return '<base>'

    @classmethod
    def __deserialize__(cls, ser):
        return cls()

base = dman.deserialize(ser)
print(base)


# %% 
# We can nest unserializable objects in containers as well.
# The info detailing what went wrong with serialization will be stored 
# in the corresponding location. The rest of the serialization process is unaffected.

class Base:
    ...


container = [
    {
        'base': Base(),
        'int': 5
    },
    'string'
]

ser = dman.serialize(container)
tui.print_serialized(ser)


# %%
# By default however, warnings will be provided when something goes wrong
# during serialization.

# temporarily set logging to default level
with dman.logger_context(level=log.WARNING):
    dman.serialize(container)

# %%
# The warning will tell you where in the stack the object is located and 
# what went wrong. If you want an actual error during runtime then you can 
# get one as follows (see also `validate` argument in `save`, `load` and `track`). 
# We advise against doing so however, since this could break your data 
# structure. It is mostly useful for debugging purposes.

try:
    dman.serialize(container, context=dman.BaseContext(validate=True))
except dman.ValidationError as e:
    traceback.print_exception(*sys.exc_info())



# %%
# Records
# ---------------------------------------
#
# Since a `record` is also serializable it should suppress errors as well
# such that the data structure is not damaged by a single erroneous item.
# We provide an overview of the errors that typically occur 
# and how they are represented within the result of the serialization.
#
# Let's begin with a storable class that cannot write to disk
@dman.storable(name='base')
class Base:
    def __write__(self, path: str):
        raise RuntimeError('Cannot write to disk.')

    @classmethod
    def __read__(cls, path: str):
        return cls()

rec = dman.record(Base())

# %% 
# If we try to serialize the object without a context we run into some issues
ser = dman.serialize(rec)
tui.print_serialized(ser)

dser = dman.deserialize(ser)
print(dser)
print(dser.content)

ser = dman.serialize(dser)
tui.print_serialized(ser)

root = TemporaryDirectory()
ctx = dman.context(root.name)
dser = dman.deserialize(ser, context=ctx)
print(dser)
print(dser.content)


# %%
# And when serializing it with a context we run into another.
ser = dman.serialize(dser, context=ctx)
tui.print_serialized(ser)

# %%
# When we cannot write instead then we get the following behavior:

@dman.storable(name='base')
class Base:
    def __write__(self, path: str):
        with open(path, 'w') as f:
            f.write('<base>')

    @classmethod
    def __read__(cls, path: str):
        raise RuntimeError('Cannot read from disk.')

rec = dman.record(Base(), preload=True)
ser = dman.serialize(rec, context=ctx)
tui.print_serialized(ser)
dser = dman.deserialize(ser, context=ctx)
print(dser)
print(dser.content)

# %%
# Note how the contents are still unloaded. We could fix `Base` and try loading 
# again. We also simulate a more advanced scenario where we first serialize 
# the invalid record again, reproducing what would happen 
# if objects became invalid and the remainder of the data structure 
# was saved to disk again. We also define a corrected version of `Base`.
ser = dman.serialize(dser, context=ctx)
tui.print_serialized(ser)
tui.walk_directory(root.name, show_content=True, console=tui.Console(width=200))

# %% 
# Brief intermission
tmp = dman.deserialize(ser, context=ctx)
print(tmp)
print(tmp.content)

@dman.storable(name='base')
class Base:
    def __write__(self, path: str):
        with open(path, 'w') as f:
            f.write('<base>')

    @classmethod
    def __read__(cls, path: str):
        return cls()

# %%
# Now we can load the contents of the original invalid record.
print(dser.content)

# %%
# And we can load the contents of the one that was serialized when
# it was invalid.
dser = dman.deserialize(ser, context=ctx)
print(dser)
print(dser.content)
