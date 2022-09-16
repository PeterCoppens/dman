# ------------------------------------------------------------------------------
# manual definition of serializables
# ------------------------------------------------------------------------------

# serializable definition
from dman import serializable

@serializable(name='manual')
class Manual:
    def __init__(self, value: str):
        self.value = value

    def __serialize__(self):
        return {'value': self.value}

    @classmethod
    def __deserialize__(cls, ser: dict):
        return cls(ser.get('value', None))

# serialization
from dman import serialize, sjson

test = Manual(value='hello world!')
ser = serialize(test)
print(sjson.dumps(ser, indent=4))

# deserialization
from dman import deserialize
reconstructed: Manual = deserialize(ser)

# content only
ser = serialize(test, content_only=True)
reconstructed: Manual = deserialize(ser, ser_type=Manual)

# ------------------------------------------------------------------------------
# enum definition of serializables
# ------------------------------------------------------------------------------
from enum import Enum

@serializable(name='mode')
class Mode(Enum):
    RED = 1
    BLUE = 2

ser = serialize(Mode.RED)
print(sjson.dumps(ser, indent=4))

# ------------------------------------------------------------------------------
# dataclass definition of serializables
# ------------------------------------------------------------------------------

# basic construction
from dataclasses import dataclass

@serializable(name='dcl_basic')
@dataclass
class DCLBasic:
    value: str

test = DCLBasic(value='hello world!')
ser = serialize(test)
print(sjson.dumps(ser, indent=4))


# add hidden field
@serializable(name='dcl_basic')
@dataclass
class DCLBasic:
    __no_serialize__ = ['hidden']
    value: str
    hidden: int = 0

test = DCLBasic(value='hello world!')
ser = serialize(test)
print(sjson.dumps(ser, indent=4))