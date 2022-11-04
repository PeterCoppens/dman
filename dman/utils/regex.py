import re


def substitute(pattern: str, repl: str, string: str):
    matches = []

    def _sub(match):
        matches.append(match)
        return repl

    res = re.sub(pattern, _sub, string)
    return res, matches