# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals

import os
import sqlite3
from json import loads, dumps

from resources.lib.constants import ADDON, KodiDbMap, ADDON_ID
from resources.lib.common.logger import debug
from resources.lib.gui.dialog import dok
from resources.lib.kodiutils import translate_path
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
            self._connection = sqlite3.Connection(self._path, timeout=60)
        return self._connection

    def execute(self, query, *args):
        debug('SQL: {} <- {}'.format(query, args))
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
    def __init__(self):
        path = 'special://database/MyVideos{}.db'.format(KodiDbMap.MyVideos[SYSTEM_VERSION])
        self._db = Sqlite(path)
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
            sql = 'update files set playcount=? where idfile=?'
            self._db.execute(sql, times, res[0])

    def get_watched(self):
        try:
            query = 'select p.strPath || f.strFilename ' \
                    'from files f join path p on p.idPath = f.idPath ' \
                    'where f.playCount > 0'
            return self._db.execute(query).fetchall()
        except:
            return None


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

    def __init__(self, name):
        path = ADDON.getAddonInfo("profile")
        if not xbmcvfs.exists(path):
            debug("storage path: {}".format(repr(path)))
            xbmcvfs.mkdir(path)
        path = os.path.join(path, 'storage.db')
        self._db = Sqlite(path=path)
        global checked
        self._data = {}
        self._last_saved = {}
        self._name = name
        if not checked:
            checked = True
            self._db.execute(self._sql_create)
        self._load()

    def __setitem__(self, key, value):
        if value is not None:
            self._data[key] = value
        else:
            if key in self._data:
                del self._data[key]
        self._save()

    def __getitem__(self, item):
        return self._data.get(item)

    def __delitem__(self, key):
        if key in self._data:
            del self._data[key]
        self._save()

    def get(self, name):
        if name in self._data:
            return self._data[name]
        return None

    def update(self, up):
        debug('updatujem {} o {}'.format(self._name, up))
        self._data.update(up)
        self._save()

    def _save(self):
        # if self._data == self._last_saved:
        #     debug('stare aj nove data su rovnake, neupdatujem {}'.format(self._name))
        #     return
        self._last_saved = self._data
        self._db.execute(self._sql_set, '{}'.format(self._name), '{}'.format(dumps(self._data)))
        _storage_cache[self._name] = self._data

    def _load(self):
        # debug('name {}'.format(self._name))
        if self._name in _storage_cache:
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

