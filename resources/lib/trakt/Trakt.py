from __future__ import absolute_import, division, print_function

from resources.lib.common.logger import debug
from resources.lib.kodiutils import get_setting, set_setting, get_setting_as_bool
from resources.lib.gui.dialog import dok, dprogress
from resources.lib.common.storage import Storage
from resources.lib.common.lists import List, SCKODIItem
from resources.lib.services.SCPlayer import player
from resources.lib.api.sc import Sc

from trakt import Trakt
from json import loads, dumps
import time
import dateutil.parser
from datetime import datetime
from dateutil.tz import tzutc
from xbmcaddon import Addon

time.strptime("1970-01-01 12:00:00", "%Y-%m-%d %H:%M:%S")


class TraktAPI(object):
    __client_id = "bb21f3665cf0fa07f2a1a420ec6990317c49dee91af8e012cb836d66674e75c4"
    __client_secret = "fcc25d240d560326147cfb32fc0554868333dc954dc150ea2519f0a2a259f6e2"
    authDialog = None
    authPollProgress = None
    storage = {
        'sync.movies': Storage('trakt.sync.movies'),
        'sync.episodes': Storage('trakt.sync.episodes'),
        'watched.movies': List('trakt.watched.movies', sorted=False),
        'watched.shows': List('trakt.watched.shows', sorted=False),
    }
    authorization = {}

    def __init__(self, force=False):
        debug("TRAKT Initializing.")

        if not get_setting_as_bool('trakt.enabled'):
            return

        Trakt.configuration.defaults.client(
            id=self.__client_id,
            secret=self.__client_secret
        )

        Trakt.on('oauth.token_refreshed', self.on_token_refreshed)

        Trakt.configuration.defaults.oauth(refresh=True)
        Trakt.configuration.defaults.http(retry=True, timeout=90)

        if get_setting('trakt.authorization') and not force:
            self.authorization = loads(get_setting('trakt.authorization'))
        else:
            self.login()

    def login(self):
        with Trakt.configuration.http(timeout=90):
            code = Trakt['oauth/device'].code()

            if not code:
                debug('TRAKT Error can not reach trakt')
                dok('ERROR', 'Trakt.tv error')
            else:
                # Construct device authentication poller
                poller = Trakt['oauth/device'].poll(**code) \
                    .on('aborted', self.on_aborted) \
                    .on('authenticated', self.on_authenticated) \
                    .on('expired', self.on_expired) \
                    .on('poll', self.on_poll)

                debug('TRAKT Enter the code "%s" at %s to authenticate your account' % (
                    code.get('user_code'),
                    code.get('verification_url')
                ))

                self.authDialog = dprogress()
                self.authDialog.create('Trakt', '{} -> {}'.format(code.get('verification_url'), code.get('user_code')))

                self.authPollProgress = [float(code.get('expires_in')),
                                         float(code.get('interval')), 0]

                # Start polling for authentication token
                poller.start(daemon=False)

    def on_aborted(self):
        debug('TRAKT Authentication aborted')
        self.authDialog.close()

    def on_authenticated(self, token):
        self.authorization = token
        set_setting('trakt.authorization', dumps(self.authorization))
        debug('TRAKT Authentication complete: %r' % token)
        self.authDialog.close()
        dok('Trakt', 'Autorizacia uspesna')
        self.update_user()

    def on_expired(self):
        debug('TRAKT Authentication expired')
        self.authDialog.close()

    def on_poll(self, callback):
        debug('TRAKT poll')
        if self.authDialog.iscanceled():
            callback(False)
        else:
            self.authPollProgress[2] += self.authPollProgress[1]
            exp, _, current = self.authPollProgress
            self.authDialog.update(int(current / exp * 100))
            callback(True)

    def on_token_refreshed(self, response):
        # OAuth token refreshed, save token for future calls
        self.authorization = response
        set_setting('trakt.authorization', dumps(self.authorization))

    # ##################################################################################################################

    def update_user(self):
        user = self.get_user()
        set_setting('trakt.user', user)
        pass

    def get_user(self):
        with Trakt.configuration.oauth.from_response(self.authorization):
            with Trakt.configuration.http(retry=True):
                result = Trakt['users/settings'].get()
                return result

    def get_playback_movies(self, movies):
        with Trakt.configuration.oauth.from_response(self.authorization):
            with Trakt.configuration.http(retry=True):
                movies = Trakt['sync/playback'].movies(parse=False).json()
        return movies

    def get_shows_watched(self, ids={}):
        with Trakt.configuration.oauth.from_response(self.authorization):
            with Trakt.configuration.http(retry=True, timeout=90):
                shows = Trakt['sync/watched'].shows(extended='full', parse=False).json()
                ids = [(i['show']['ids']['trakt'], i['show']['aired_episodes'],
                        sum([[(s['number'], e['number'], e['last_watched_at']) for e in s['episodes']]
                             for s in i['seasons']], [])) for i in shows]

        return ids

    def get_movies_watched(self, movies):
        with Trakt.configuration.oauth.from_response(self.authorization):
            with Trakt.configuration.http(retry=True, timeout=90):
                Trakt['sync/watched'].movies(movies, exceptions=True)
        return movies

    def get_last_activities(self):
        with Trakt.configuration.oauth.from_response(self.authorization):
            with Trakt.configuration.http(retry=True):
                result = Trakt['sync'].last_activities()
                return result

    def add_to_history(self, item):
        with Trakt.configuration.oauth.from_response(self.authorization):
            with Trakt.configuration.http(retry=True):
                result = Trakt['sync/history'].add(item)
                return result

    def remove_from_history(self, item):
        with Trakt.configuration.oauth.from_response(self.authorization):
            with Trakt.configuration.http(retry=True):
                result = Trakt['sync/history'].remove(item)
                return result

    @staticmethod
    def script_trakt():
        return Addon('script.trakt')

    @staticmethod
    def is_enabled():
        return False
        # return get_setting_as_bool('trakt.enabled') and get_setting('trakt.authorization')

    @staticmethod
    def can_check():
        return TraktAPI.is_enabled() and not player.isPlaying()

    def check_trakt(self):
        if TraktAPI.can_check():
            debug('check trakt')
            data = trakt.get_last_activities()
            for b in ['movies', 'episodes']:
                synced = False
                item = data.get(b)
                for a, i in enumerate(item):
                    # debug('{} {} -> {}'.format(b, i, TraktAPI.utc2timestamp(item.get(i))))
                    key = 'sync.{}'.format(b)
                    if self.storage[key].get(i) != item.get(i):
                        debug('zmena {}[{}] z {} na {}'.format(key, i, self.storage[key].get(i), item.get(i)))
                        if not synced:
                            self.sync_local(b, self.storage[key].get(i))
                            synced = True
                        self.storage[key].update({i: item.get(i)})

    def sync_playback_movies(self, last=0):
        last_at = TraktAPI.utc2timestamp(last)
        playback = self.get_playback_movies({})
        debug('paused at {}'.format(len(playback)))
        sync = {}
        tr = []
        for m in playback:
            paused_at = TraktAPI.utc2timestamp(m['paused_at'])
            if paused_at >= last_at:
                sync.update({m['movie']['ids']['trakt']: m})
                tr.append(m['movie']['ids']['trakt'])
        if len(sync):
            res = Sc.post('/Ftrakt2sc', data={'trakt': dumps(tr), 't': 1})
            debug('sync {} / {}     {}'.format(len(sync), len(res), res))
            for _, scid in enumerate(res):
                itm = res.get(scid)
                item = SCKODIItem(scid, trakt=itm['trakt'])
                tr = sync.get(int(itm['trakt']))
                progress = float(sync.get(int(itm['trakt']))['progress'])
                watched = int(float(itm['duration']) * float(progress / 100))
                debug('itm {} {} {} {} {} {}'.format(scid, itm, itm['duration'], watched, progress, tr))
                item.set_watched(watched)
                d = datetime.fromtimestamp(self.utc2timestamp(tr.get('paused_at')))
                item.set_last_played(d.strftime('%Y-%m-%d %H:%M:%S'))
        pass

    def sync_local(self, type, last):
        if type == 'movies':
            self.sync_local_movies(last)
        else:
            self.sync_local_episodes(last)

    def sync_get_list(self, data, typ):
        data = list(data.items())
        items = {}
        for _, item in data:
            item = item.to_dict()
            # debug("------ film\n{}".format(movie))
            tr = item['ids']['trakt']
            items.update({tr: item})
        return self.trakt2sc(items, typ)

    def trakt2sc(self, items, typ):
        debug('items {}'.format(len(items)))
        res = Sc.post('/Ftrakt2sc', data={'trakt': dumps(list(items.keys())), 't': typ})
        debug('res: {}'.format(len(res)))
        return res, items

    def sync_local_episodes(self, last=0):
        last_at = TraktAPI.utc2timestamp(last)
        data = self.get_shows_watched({})
        items = {}
        for trid, num, eps in data:
            items.update({trid: eps})
        res, items = self.trakt2sc(items, 3)
        for scid, trid in res.items():
            for s, e, watched_at in items[int(trid['trakt'])]:
                wa = TraktAPI.utc2timestamp(watched_at)
                item = SCKODIItem(scid, series=s, episode=e)
                old = item.get_play_count()
                if old is None or wa >= last_at:
                    debug('SCID ADD {} {}x{}'.format(scid, s, e))
                    item.set_play_count('1')

        pass

    def sync_local_movies(self, last):
        self.sync_playback_movies(last)
        data = self.get_movies_watched({})
        res, movies = self.sync_get_list(data, 1)
        debug('res: {}'.format(len(res)))
        all_items = self.storage['watched.movies'].get()[:]
        # debug('na zaciatku {}'.format(all_items))
        for scid, trid in res.items():
            # debug('SCID: {}'.format(scid))
            # debug('w {}'.format(self.storage['watched.{}'.format(type)]))
            item = SCKODIItem(scid, trakt=trid)
            if scid not in all_items:
                debug('pridavam do zoznamu {}'.format(scid))
                self.storage['watched.movies'].add(scid)
                item.set_play_count('1')
            else:
                all_items.remove(scid)
            pass
            # debug('{} -> {}'.format(scid, movies.get(trid)))
        # debug('Zostali nam po synchre: {}'.format(all_items))
        if len(all_items) > 0:
            for scid in all_items:
                # debug('mazem {}'.format(scid))
                self.storage['watched.movies'].add(scid, remove_only=True)
                item = SCKODIItem(scid)
                item.set_play_count(None)
        # debug('res: {}/{}'.format(len(res), res))

    @staticmethod
    def utc2timestamp(to_convert):
        if to_convert:
            date_format = "%s"
            try:
                naive = dateutil.parser.parse(to_convert)
                utc = naive.replace(tzinfo=tzutc())
            except ValueError:
                debug('utc2timestamp() problem, nastavujem aktualny cas')
                utc = datetime.now()
            try:
                to_convert = int(utc.strftime(date_format))
            except:
                to_convert = int(utc.timestamp())

        return to_convert

    def set_watched(self, trid, times=None, season=None, episode=None):
        if season is None:
            obj = {"movies": [{"ids": {"trakt": trid}}]}
        else:
            obj = {"shows": [{"ids": {"trakt": trid}, "seasons": {"number": season, "episodes": [{"number": episode}]}}]}
        debug('posielam obj: {}'.format(dumps(obj)))
        if times is not None and int(times) > 0:
            self.add_to_history(obj)
        else:
            self.remove_from_history(obj)
        debug('Hotovo trakt history....')


trakt = TraktAPI()
# trakt.sync_playback_movies(0)
# trakt.sync_local_episodes(0)
