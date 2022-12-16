# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals

import os
import sqlite3
from json import loads, dumps

from resources.lib.constants import ADDON, KodiDbMap, ADDON_ID, SC
from resources.lib.common.logger import debug
from resources.lib.gui.dialog import dok, dprogressgb
from resources.lib.kodiutils import translate_path, get_skin_name
from resources.lib.system import SYSTEM_VERSION

import xbmcvfs

checked = False
_storage_cache = {}
_connection_cache = {}


class Sqlite(object):
    def __init__(self, path):
        self._path = translate_path(path)
        self._connection = None
        # debug('db file: {}'.format(self._path))

    def _get_conn(self):
        if self._connection is None:
            self._connection = sqlite3.Connection(self._path, timeout=1, check_same_thread=False)
        try:
            self._connection.cursor()
        except sqlite3.ProgrammingError:
            self._connection = None
            return self._get_conn()
        return self._connection

    def execute(self, query, *args):
        # debug('SQL: {} <- {}'.format(query, args))
        # debug('SQL')
        with self._get_conn() as conn:
            c = conn.cursor()
            c.execute(query, args)
            return c


class KodiAddonsDb:
    def __init__(self):
        path = 'special://database/Addons{}.db'.format(KodiDbMap.Addons[SYSTEM_VERSION])
        self._db = Sqlite(path)

    def check_repo(self):
        query = 'select id from repo where id in (' \
                'select idRepo from addonlinkrepo where idAddon in (' \
                'select id from addons where addonID=?))'
        res = self._db.execute(query, ADDON_ID).fetchone()
        if res is not None:
            return True
        return False

    def enable_auto_update(self):
        if not self.check_repo():
            from resources.lib.language import Strings
            dok(Strings.txt(Strings.SYSTEM_H1), Strings.txt(Strings.SYSTEM_NOT_INSTALLED_FROM_REPOSITORY))
        query = 'delete from update_rules where addonID=?'
        self._db.execute(query, ADDON_ID)


class KodiDb:
    _static_db = None

    def __init__(self):
        path = 'special://database/MyVideos{}.db'.format(KodiDbMap.MyVideos[SYSTEM_VERSION])
        if KodiDb._static_db is None:
            KodiDb._static_db = Sqlite(path)
        self._db = KodiDb._static_db
        # debug('tables: {}'.format(self._db.execute('SELECT name FROM sqlite_master WHERE type =\'table\'').fetchall()))

    def get_watched_path(self, path):
        try:
            sql = 'select f.* ' \
                  'from files f join path p on p.idPath = f.idPath ' \
                  'where f.strfilename like ? or p.strpath like ?'
            return self._db.execute(sql, path, path).fetchone()
        except:
            return None

    def set_watched_path(self, path, times):
        res = self.get_watched_path(path)
        if res and res[0]:
            # debug('MAME PATH: {}'.find(path))
            sql = 'update files set playcount=? where idfile=?'
            self._db.execute(sql, times, res[0])
        else:
            debug('Nemame PATH: {}'.format(path))
            pass

    def get_watched(self):
        try:
            query = 'select p.strPath || f.strFilename ' \
                    'from files f join path p on p.idPath = f.idPath ' \
                    'where f.playCount > 0'
            return self._db.execute(query).fetchall()
        except:
            return None


class TexturesDb:
    def __init__(self):
        path = 'special://database/Textures{}.db'.format(KodiDbMap.Textures[SYSTEM_VERSION])
        self._db = Sqlite(path)

    def clean(self):
        zoznam = self.to_clean()
        total = len(zoznam)
        d = dprogressgb()
        d.create('mazanie', 'mazem')
        for pos, i in enumerate(zoznam):
            p = int(pos/total*100)
            debug('item: {}/{} {}'.format(pos, total, TexturesDb.file_name(i)))
            self.remove_item(i)
            d.update(p, 'mazanie', 'mazem {}'.format(i[1]))
        d.close()

    @staticmethod
    def file_name(item):
        return translate_path("special://masterprofile/Thumbnails/{}".format(item[1]))

    def remove_item(self, item):
        xbmcvfs.delete(TexturesDb.file_name(item))
        self._db.execute('delete from sizes where idtexture=?', item[0])
        self._db.execute('delete from texture where id=?', item[0])

    def to_clean(self):
        q = "SELECT s.idtexture, t.cachedurl, s.lastusetime FROM sizes AS s JOIN texture t ON (t.id=s.idtexture) WHERE lastusetime <= DATETIME('now', '-1 month') ORDER BY 3 ASC"
        return self._db.execute(q).fetchall()


class Storage(object):
    _sql_create = (
        'CREATE TABLE IF NOT EXISTS storage '
        '('
        '  item_key VARCHAR(255) PRIMARY KEY ,'
        '  item_value BLOB'
        ')'
    )
    _sql_set = 'INSERT OR REPLACE INTO storage (item_key, item_value) VALUES (?, ?)'
    _sql_get = 'SELECT item_value FROM storage WHERE item_key = ?'
    _sql_del = 'DELETE FROM storage WHERE item_key = ?'
    _data = {}
    _static_db = None

    def __init__(self, name):
        path = ADDON.getAddonInfo("profile")
        if not xbmcvfs.exists(path):
            debug("storage path: {}".format(repr(path)))
            xbmcvfs.mkdir(path)
        path = os.path.join(path, 'storage.db')
        if Storage._static_db is None:
            Storage._static_db = Sqlite(path=path)
        self._db = Storage._static_db
        global checked
        self._data = {}
        self._last_saved = {}
        self._name = name
        if not checked:
            checked = True
            self._db.execute(self._sql_create)
        self.load()

    def __setitem__(self, key, value):
        if value is not None:
            self._data[key] = value
        else:
            if key in self._data:
                del self._data[key]
        self.save()

    def __getitem__(self, item):
        return self._data.get(item)

    def __delitem__(self, key):
        if key in self._data:
            del self._data[key]
        self.save()

    def get(self, name):
        if name in self._data:
            return self._data[name]
        return None

    def update(self, up):
        debug('updatujem {} o {}'.format(self._name, up))
        self._data.update(up)
        self.save()

    def save(self):
        # if self._data == self._last_saved:
        #     debug('stare aj nove data su rovnake, neupdatujem {}'.format(self._name))
        #     return
        self._last_saved = self._data
        self._db.execute(self._sql_set, '{}'.format(self._name), '{}'.format(dumps(self._data)))
        _storage_cache[self._name] = self._data

    def load(self, force=False):
        # debug('name {}'.format(self._name))
        if force is False and self._name in _storage_cache:
            self._data = _storage_cache.get(self._name)
            self._last_saved = self._data
            return
        # debug('storage cache: {}'.format(_storage_cache))
        try:
            val = self._db.execute(self._sql_get, self._name).fetchone()
            # debug('load: {}'.format(val))
            self._data = loads(val[0])
        except:
            self._data = {}
        _storage_cache[self._name] = self._data
        self._last_saved = self._data
        # debug('loaded data {}'.format(self._data))

    @property
    def data(self):
        return self._data


class KodiViewModeDb:
    def __init__(self):
        path = 'special://database/ViewModes{}.db'.format(KodiDbMap.ViewModes[SYSTEM_VERSION])
        self._db = Sqlite(path)

    def get_sort(self, url):
        query = 'select sortMethod, sortOrder from view where path=? and skin=?'
        return self._db.execute(query, url, get_skin_name()).fetchone()


preferred_lang_list = Storage(SC.ITEM_PREFERRED_LANG)