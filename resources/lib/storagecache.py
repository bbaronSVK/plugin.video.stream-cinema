import simplecache
import util
from datetime import timedelta


class StorageCache:
    cache = None

    def __init__(self):
        self.cache = simplecache.SimpleCache()
        self.ttl = timedelta(hours=1)
        self.cache.default_timeout = self.ttl
        return None

    def _evaluate(self, data):
        try:
            util.debug("[SC] test eval")
            data = eval(data)
            return data
        except:
            return ""

    def _generateKey(self, funct, *args):
        name = repr(funct)
        if name.find(" of ") > -1:
            name = name[name.find("method") + 7:name.find(" of ")]
        elif name.find(" at ") > -1:
            name = name[name.find("function") + 9:name.find(" at ")]

        keyhash = hashlib.md5()
        for params in args:
            if isinstance(params, dict):
                for key in sorted(params.iterkeys()):
                    if key not in ["new_results_function"]:
                        keyhash.update("'%s'='%s'" % (key, params[key]))
            elif isinstance(params, list):
                keyhash.update(",".join(["%s" % el for el in params]))
            else:
                try:
                    keyhash.update(params)
                except:
                    keyhash.update(str(params))

        name += "|" + keyhash.hexdigest() + "|"

        return name

    def cacheFunction(self, funct=False, *args):
        key = self._generateKey(funct, *args)
        ret = self.get(key)
        if not ret:
            ret = funct(*args)
            self.set(key, ret)
        return ret

    def set(self, name, data, checksum="", expiration=None):
        if expiration is None:
            expiration = self.ttl
        return self.cache.set(name, data, checksum, expiration)

    def get(self, name, checksum=""):
        ret = self.cache.get(name, checksum)
        if not ret:
            ret = ""
        return ret

    def delete(self, name):
        return self.set(name, None, expiration=timedelta(seconds=1))

    def setMulti(self, name, data):
        '''
        temp = repr({"name": name, "data": data})
        self.set(name, data)
        '''
        return ""

    def getMulti(self, name, items):
        '''
        res = self.get(name)
        if res:
                res = self._evaluate(res)
                if res == " ":  # We return " " as nothing.
                    return ""
                else:
                    return res
        '''
        return ""

    def lock(self, name):
        if self.get(name) == 'lock':
            return False
        return self.set(name, 'lock')

    def unlock(self, name):
        return self.set(name, "")
