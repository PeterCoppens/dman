from dataclasses import dataclass
from dman.persistent.record import Record, record
from dman.persistent.context import clear, RootContext
from dman.persistent.serializables import serialize, deserialize
from dman.persistent.storeables import storeable

import json


@storeable
@dataclass
class TestSto:
    name: str
    

if __name__ == '__main__':
    rt = RootContext.at_script().joinpath('_record')
    clear(rt)

    rec = record(TestSto(name='hello'), preload=True)
    ser = serialize(rec, rt)
    print(json.dumps(ser, indent=4))
    rrec: Record = deserialize(ser, rt)
    rser = serialize(rrec, rt)
    print(json.dumps(rser, indent=4))
    print('name: ', rrec.content.name)
    rrser = serialize(rrec, rt)
    print(json.dumps(rrser, indent=4))
