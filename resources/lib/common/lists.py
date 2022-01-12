from __future__ import print_function, unicode_literals

from json import dumps
from time import time

from resources.lib.api.sc import Sc
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

    def __len__(self):
        return len(self.data)

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
    SCROBBLE_START = 'start'
    SCROBBLE_PAUSE = 'pause'
    SCROBBLE_STOP = 'stop'
    LAST_EP_KEY = 'last_ep'
    ITEM_NAME = 'SCKODIItem'
    _watched = None

    def __init__(self, name, series=None, episode=None, trakt=None):
        super(SCKODIItem, self).__init__('{}-{}'.format(self.ITEM_NAME, name))
        if series is not None:
            item = '{}/{}/{}'.format(name, series, episode)
        else:
            item = '{}'.format(name)
        kodi_path = hexlify('/Play/{}'.format(item))

        if SCKODIItem._watched is None:
            SCKODIItem._watched = List('all_watched')
            # debug('__: {}'.format(SCKODIItem._watched.get()))

        self.watched = SCKODIItem._watched
        self.item = item
        self.name = name
        self.series = series
        self.episode = episode
        self.trakt = trakt
        self.kodi_path = '%{}%'.format(kodi_path)
        self.kodi_db = None
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

    def get_last_ep(self):
        last = self[self.LAST_EP_KEY]
        if last is not None:
            last = self[self.LAST_EP_KEY].split('x')
        else:
            last = (1, 0)
        # debug('posielam LAST_EP {}'.format(last))
        return last

    def set_last_ep(self, s, e, last_time=None):
        self[self.LAST_EP_KEY] = '{}x{}'.format(s, e)
        ne = Storage('nextep')

        try:
            info = Sc.up_next(self.name, s, e)
            if 'error' in info or ('info' in info and info.get('info') is None):
                debug('nemame data k next EP')
                del (ne[self.name])
                return

            new = {
                's': s,
                'e': e,
                't': int(time()) if last_time is None else last_time,
            }
            ne[self.name] = new
        except:
            import traceback
            debug('ERR: {}'.format(traceback.format_exc()))
            del(ne[self.name])
        debug('nastavujem LAST_EP na: {} pre {}'.format(self[self.LAST_EP_KEY], self.name))

    def set_play_count(self, times, from_kodi_player=False):
        self._set('play_count', times)

        if times:
            self._watched.add(self.item)
        else:
            self._watched.add(self.item, True)

        if self.series:
            key = 'series:{}'.format(self.series)
            series = self.data.get(key, {})
            if times:
                series.update({self.episode: True})
            else:
                del series[self.episode]
            self.data[key] = series

        # if self.kodi_db:
        #     self.kodi_db.set_watched_path(self.kodi_path, times)

        if from_kodi_player and self.series:
            self.set_last_ep(self.series, self.episode)

        from resources.lib.trakt.Trakt import trakt
        if self.trakt is not None and trakt.is_enabled():
            trakt.set_watched(self.trakt, times, season=self.series, episode=self.episode)

    def scrobble(self, percent, action):
        from resources.lib.trakt.Trakt import trakt
        if self.trakt is not None and trakt.is_enabled():
            ret = trakt.scroble(self.trakt, self.series, self.episode, percent, action)
            debug('scrobble resp: {}'.format(ret))

    def get_play_count(self):
        if self.item in self._watched.get():
            return 1

        pc = self._get('play_count')
        play_count = int(pc) if pc is not None else 0
        if pc is not None:
            self._watched.add(self.item)
            return play_count

        # if self.kodi_db:
        #     res = self.kodi_db.get_watched_path(self.kodi_path)
        #     if res and res[3] is not None:
        #         kodi_play_count = int(res[3])
        #         if kodi_play_count > play_count:
        #             play_count = kodi_play_count
        #         self._watched.add(self.item)
        #         self.set_play_count(play_count)
        #     else:
        #         self.set_play_count(0)

        return play_count

        # if kodi_play_count is not None and kodi_play_count > 0 and (
        #         play_count is None or play_count == 0) and kodi_play_count != play_count:
        #     # debug('setujem item ako videny')
        #     self.set_play_count(kodi_play_count)
        #     play_count = kodi_play_count
        #     # if self.trakt:
        #     #     from resources.lib.trakt.Trakt import trakt
        #     #     trakt.set_watched(trid=self.trakt, times=kodi_play_count, season=self.series, episode=self.episode)
        # elif play_count != kodi_play_count:
        #     # debug('setujem item ako NE videny {}/{}'.format(kodi_play_count, play_count))
        #     self.set_play_count(kodi_play_count)
        #     # if self.trakt:
        #     #     from resources.lib.trakt.Trakt import trakt
        #     #     trakt.set_watched(trid=self.trakt, times=kodi_play_count, season=self.series, episode=self.episode)
        #     play_count = kodi_play_count
        #
        # # debug('return play count: {}'.format(play_count))
        # return play_count


