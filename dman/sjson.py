import json

def dumps(obj, *args, **kwargs):
    def default(o): return f"<<non-serializable: {type(o).__qualname__}>>"
    return json.dumps(obj, *args, default=default, **kwargs)


def dump(obj, *args, **kwargs):
    def default(o): return f"<<non-serializable: {type(o).__qualname__}>>"
    return json.dump(obj, *args, default=default, **kwargs)


load = json.load
loads = json.loads