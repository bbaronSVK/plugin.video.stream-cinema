from __future__ import print_function, unicode_literals

import functools
import time
import traceback

from resources.lib.common.logger import info


def performance(name):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start = time.time()
            ret = func(*args, **kwargs)
            end = time.time()
            info('{0} took {1:.2f}ms'.format(name, (end - start) * 1000))
            return ret
        return wrapper
    return decorator


def try_catch(name):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except:
                info('error in {} | {}'.format(name, str(traceback.format_exc())))
                return None
        return wrapper
    return decorator
