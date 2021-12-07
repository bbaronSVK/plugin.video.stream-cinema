from __future__ import print_function, unicode_literals


def _encode(val):
    if not isinstance(val, str):
        val = val.encode('utf8')
    return str(val)


def _decode(val):
    if not isinstance(val, str):
        val = val.decode('utf8')
    return str(val)
