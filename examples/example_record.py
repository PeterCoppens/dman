from dataclasses import dataclass
from dman.persistent.record import Record, RecordContext, record, TemporaryContext
from dman.persistent.serializables import serialize, deserialize
from dman.persistent.storeables import storeable

import json


@storeable
@dataclass
class TestSto:
    name: str
    

if __name__ == '__main__':
    with TemporaryContext() as ctx:
        rec = record(TestSto(name='hello'), preload=True)
        ser = serialize(rec, ctx)
        print('== first serialization ==')
        print(json.dumps(ser, indent=4))

        res: Record = deserialize(ser, ctx)
        ser = serialize(rec, ctx)
        print('== second serialization ==')
        print(json.dumps(ser, indent=4))

        res: Record = deserialize(ser, ctx)
        print('content: ', rec.content)
        ser = serialize(rec, ctx)
        print('== third serialization ==')
        print(json.dumps(ser, indent=4))
        
        
        

    # rec = record(TestSto(name='hello'), preload=True)
    # ser = serialize(rec, rt)
    # print(json.dumps(ser, indent=4))
    # rrec: Record = deserialize(ser, rt)
    # rser = serialize(rrec, rt)
    # print(json.dumps(rser, indent=4))
    # print('name: ', rrec.content.name)
    # rrser = serialize(rrec, rt)
    # print(json.dumps(rrser, indent=4))
