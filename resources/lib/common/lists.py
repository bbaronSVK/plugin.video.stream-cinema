from __future__ import print_function, unicode_literals

from json import dumps

from resources.lib.common.storage import Storage, KodiDb
from resources.lib.common.logger import debug
from resources.lib.kodiutils import hexlify


class List(object):
    def __init__(self, name, max_items=None, sorted=True):
        self.name = name
        self.max_items = max_items
        self.sorted = sorted
        self.storage = Storage(name)
        self.data = self.storage.get('list')
        if not self.data:
            self.data = []
        # debug('List data({}) {}'.format(self.name, self.data))

    def remove(self):
        self.data = []
        self.set(self.data)

    def get(self):
        # debug('List get data {}')
        return self.data

    def add(self, item, remove_only=False):
        # debug('List add {} | {}'.format(item, remove_only))

        if item is None:
            debug('List ignore None item')
            return

        if self.sorted is True and item in self.data \
                or remove_only is True:
            # debug('--- remove {}'.format(item))
            try:
                self.data.remove(item)
            except:
                pass

        if remove_only is False \
                or (self.sorted is False and item not in self.data and remove_only is False):
            self.data.insert(0, item)
            # debug('List insert item')

        if self.max_items:
            remove = len(self.data) - self.max_items
            if remove > 0:
                # debug('List to remove {}'.format(remove))
                for i in range(remove):
                    self.data.pop()
        # debug('List end add {}'.format(self.data))
        self.set(self.data)

    def set(self, data):
        # debug('List set {}'.format(data))
        self.storage['list'] = data


class SCKODIItem(Storage):
    def __init__(self, name, series=None, episode=None, trakt=None):
        super(SCKODIItem, self).__init__('SCKODIItem-{}'.format(name))
        if series is not None:
            url = '/Play/{}/{}/{}'.format(name, series, episode)
            # debug('SCKODIItem: {}'.format(url))
            kodi_path = hexlify(url)
        else:
            kodi_path = hexlify('/Play/{}'.format(name))
        self.series = series
        self.episode = episode
        self.trakt = trakt
        self.kodi_path = '%{}%'.format(kodi_path)
        self.kodi_db = None
        if self.kodi_path is not None:
            self.kodi_db = KodiDb()

    def _set(self, key, val):
        if val is None:
            del self[self._key(key)]
        else:
            self[self._key(key)] = val

    def _get(self, key):
        return self.get(self._key(key))

    def _key(self, key):
        if self.series is not None:
            key = '{}:{}:{}'.format(key, self.series, self.episode)
        return key

    def set_watched(self, percent):
        self._set('watched', percent)

    def get_watched(self):
        return self._get('watched')

    def set_last_played(self, percent):
        self._set('last_played', percent)

    def get_last_played(self):
        return self._get('last_played')

    def set_play_count(self, times):
        self._set('play_count', times)
        if self.kodi_db:
            self.kodi_db.set_watched_path(self.kodi_path, times)
        if self.trakt:
            pass
            # from resources.lib.trakt.Trakt import trakt, TraktAPI
            # debug('trakt enabled: {} / {}'.format(TraktAPI.is_enabled(), trakt.is_enabled()))
            # if trakt.is_enabled() is True:
            #     trakt.set_watched(self.trakt, times, season=self.series, episode=self.episode)

    def get_play_count(self):
        kodi_play_count = None
        play_count = self._get('play_count')
        return play_count

        if self.kodi_db is not None:
            res = self.kodi_db.get_watched_path(self.kodi_path)
            if res and res[3] is not None:
                kodi_play_count = res[3]

        if kodi_play_count is not None and kodi_play_count > 0 and (
                play_count is None or play_count == 0) and kodi_play_count != play_count:
            # debug('setujem item ako videny')
            self.set_play_count(kodi_play_count)
            play_count = kodi_play_count
            # if self.trakt:
            #     from resources.lib.trakt.Trakt import trakt
            #     trakt.set_watched(trid=self.trakt, times=kodi_play_count, season=self.series, episode=self.episode)
        elif play_count != kodi_play_count:
            # debug('setujem item ako NE videny {}/{}'.format(kodi_play_count, play_count))
            self.set_play_count(kodi_play_count)
            # if self.trakt:
            #     from resources.lib.trakt.Trakt import trakt
            #     trakt.set_watched(trid=self.trakt, times=kodi_play_count, season=self.series, episode=self.episode)
            play_count = kodi_play_count

        # debug('return play count: {}'.format(play_count))
        return play_count


