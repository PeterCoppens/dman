def serialize(obj):
    if isinstance(obj, dict):
        for v in obj.values():
            serialize(v)
    if isinstance(obj, list):
        for v in obj:
            serialize(v)
    obj.__serialize__()