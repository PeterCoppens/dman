import json
from typing import Callable, Type


def _default(o):
    convert = __translate_atomic.get(
        type(o), 
        lambda o: f"<un-serializable: {type(o).__qualname__}>"
    )
    return convert(o)


def dumps(obj, *args, **kwargs):
    return json.dumps(obj, *args, default=_default, **kwargs)


def dump(obj, *args, **kwargs):
    return json.dump(obj, *args, default=_default, **kwargs)


def load(fp, *, cls=None, object_hook=None, parse_float=None,
        parse_int=None, parse_constant=None, object_pairs_hook=None, **kw):
    return json.load(
        fp, cls=cls, object_hook=object_hook, 
        parse_float=parse_float, parse_int=parse_int, 
        parse_constant=parse_constant, 
        object_pairs_hook=object_pairs_hook, **kw
    )


def loads(s, *, cls=None, object_hook=None, parse_float=None,
          parse_int=None, parse_constant=None, object_pairs_hook=None, **kw):
    return json.loads(
        s, cls=cls, object_hook=object_hook,
        parse_float=parse_float, parse_int=parse_int,
        parse_constant=parse_constant,
        object_pairs_hook=object_pairs_hook, **kw
    )


atomic_types = [
    str, int, float, bool, type(None)
]

__translate_atomic = {}


def atomic_type(obj):
    return isinstance(obj, tuple(atomic_types))


def register_atomic_alias(obj: Type, convert: Callable):
    atomic_types.append(obj)
    __translate_atomic[obj] = convert
