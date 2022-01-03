import json


def dumps(obj, *args, **kwargs):
    def default(o): return f"<un-serializable: {type(o).__qualname__}>"
    return json.dumps(obj, *args, default=default, **kwargs)


def dump(obj, *args, **kwargs):
    def default(o): return f"<un-serializable: {type(o).__qualname__}>"
    return json.dump(obj, *args, default=default, **kwargs)


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


atomic_types = (
    str, int, float, bool, type(None)
)


def atomic_type(obj):
    return isinstance(obj, atomic_types)