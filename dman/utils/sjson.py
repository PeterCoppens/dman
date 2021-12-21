import json

def dumps(obj, *args, **kwargs):
    def default(o): return f"<un-serializable: {type(o).__qualname__}>"
    return json.dumps(obj, *args, default=default, **kwargs)


def dump(obj, *args, **kwargs):
    def default(o): return f"<un-serializable: {type(o).__qualname__}>"
    return json.dump(obj, *args, default=default, **kwargs)


atomic_types = (
    str, int, float, bool
)


def atomic_type(obj):
    return isinstance(obj, atomic_types)


load = json.load
loads = json.loads