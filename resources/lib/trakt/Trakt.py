from __future__ import absolute_import, division, print_function

import traceback

from resources.lib.api.sc import Sc
from resources.lib.common.lists import List, SCKODIItem
from resources.lib.common.logger import debug
from resources.lib.common.storage import Storage
from resources.lib.constants import ADDON_ID
from resources.lib.gui import get_cond_visibility, home_win
from resources.lib.gui.dialog import dok, dprogress, dprogressgb
from resources.lib.gui.item import SCItem
from resources.lib.kodiutils import set_setting, get_setting_as_bool, set_setting_as_bool
from resources.lib.services.SCPlayer import player
from resources.lib.services.Settings import settings
from trakt import Trakt
from json import loads, dumps
import time
import dateutil.parser
from datetime import datetime
from dateutil.tz import tzutc
from xbmcaddon import Addon


time.strptime("1970-01-01 12:00:00", "%Y-%m-%d %H:%M:%S")

CHECK_SYNC = {
    'movies': ['watched_at', 'paused_at'],
    'episodes': ['watched_at', 'paused_at'],
}


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
    initialized = False

    def __init__(self, force=False):
        debug("TRAKT Initializing.")

        Trakt.configuration.defaults.client(
            id=self.__client_id,
            secret=self.__client_secret
        )

        Trakt.on('oauth.token_refreshed', self.on_token_refreshed)

        Trakt.configuration.defaults.oauth(refresh=True)
        Trakt.configuration.defaults.http(retry=True, timeout=90)

        from resources.lib.services.Monitor import monitor
        self.monitor = monitor

        if not get_setting_as_bool('trakt.enabled'):
            debug('Trak nieje zapnuty')
            return

        self.initialize(force=force)

    def initialize(self, force=False):
        self.initialized = True

        if settings.get_setting('trakt.authorization') and not force:
            self.authorization = loads(settings.get_setting('trakt.authorization'))
            Trakt.configuration.defaults.oauth.from_response(
                self.authorization,
                refresh=True
            )
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
        data = self.get_user()
        debug('trakt user: {}'.format(dumps(data)))
        user = data['user']['username'] if 'username' in data.get('user', {}) else data['user']['name']
        set_setting('trakt.user', user)

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

    def get_shows_history(self, start_at, end_at=None):
        with Trakt.configuration.oauth.from_response(self.authorization):
            with Trakt.configuration.http(retry=True, timeout=90):
                shows = Trakt['sync/history'].shows(start_at=start_at, page=1, per_page=100000, parse=False).json()
                shows_data = {}
                for i in shows:
                    if i['action'] == 'watch' and i['type'] == 'episode':
                        id = i['show']['ids']['trakt']
                        if id not in shows_data:
                            shows_data.update({id: []})
                        shows_data[id].append((i['episode']['season'], i['episode']['number'], i['watched_at']))
                ids = [(key, 1, sorted(items, key=lambda x: (x[2], x[0], x[1]))) for key, items in shows_data.items()]
        return ids

    def get_movies_watched(self, movies):
        with Trakt.configuration.oauth.from_response(self.authorization):
            with Trakt.configuration.http(retry=True, timeout=90):
                Trakt['sync/watched'].movies(movies, exceptions=True)
        return movies

    def get_episode_info(self, id, season, episode, extended=None):
        with Trakt.configuration.oauth.from_response(self.authorization):
            with Trakt.configuration.http(retry=True, timeout=90):
                try:
                    res = Trakt['shows'].episode(id, season, episode, extended, parse=False).json()
                except:
                    res = None
        return res

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

    def get_lists(self, user='me'):
        return Trakt['users/*/lists'].get(username=user)

    def get_list_items(self, id, user='me'):
        return Trakt['users/*/lists/*'].get(username=user, id=id)

    def get_watchlist(self, user='me'):
        return Trakt['users/*/watchlist'].get(username=user, parse=False)

    @staticmethod
    def script_trakt():
        return Addon('script.trakt')

    @staticmethod
    def is_enabled():
        return settings.get_setting_as_bool('trakt.enabled') and settings.get_setting('trakt.authorization')

    @staticmethod
    def can_check():
        return home_win.getProperty('check_trakt') == '' and TraktAPI.is_enabled() and not player.isPlaying()

    @staticmethod
    def clean_prop():
        home_win.clearProperty('check_trakt')

    def check_trakt(self, force=False):
        if TraktAPI.can_check() or force:
            home_win.setProperty('check_trakt', '1')
            if self.initialized is False:
                self.initialize()
            # debug('check trakt')
            data = self.get_last_activities()
            if data is None:
                debug('trakt data is NONE')
                self.clean_prop()
                return None

            for check in CHECK_SYNC.items():
                synced = False
                item = data.get(check[0])
                for a, i in enumerate(item):
                    if i in check[1]:
                        key = 'sync.{}'.format(check[0])
                        if self.storage[key].get(i) != item.get(i):
                            debug('zmena {}[{}] z {} na {}'.format(key, i, self.storage[key].get(i), item.get(i)))
                            if not synced:
                                synced = True
                                try:
                                    if self.sync_local(check[0], self.storage[key].get(i), force=force):
                                        self.storage[key].update({i: item.get(i)})
                                except:
                                    debug('TRAKT ERR: {}'.format(traceback.format_exc()))
                                    pass
            self.clean_prop()

    def sync_playback_movies(self, last=0):
        last_at = TraktAPI.utc2timestamp(last)
        playback = self.get_playback_movies({})
        debug('paused at {}'.format(len(playback)))
        sync = {}
        tr = []
        for m in playback:
            paused_at = TraktAPI.utc2timestamp(m['paused_at'])
            if paused_at is None or last_at is None or paused_at >= last_at:
                sync.update({m['movie']['ids']['trakt']: m})
                tr.append(m['movie']['ids']['trakt'])
        if len(sync):
            res = Sc.post('/Ftrakt2sc', data={'trakt': dumps(tr), 't': 1})
            debug('sync {} / {}     {}'.format(len(sync), len(res), res))
            max = len(res)
            dialog = dprogressgb()
            dialog.create('sync_playback_movies Trakt.Movies')
            for pos, scid in enumerate(res):
                if self.monitor.abortRequested():
                    return

                debug('trakt {}%'.format(int(pos/max*100)))
                dialog.update(int(pos/max*100))
                itm = res.get(scid)
                item = SCKODIItem(scid, trakt=itm['trakt'])
                tr = sync.get(int(itm['trakt']))
                progress = float(sync.get(int(itm['trakt']))['progress'])
                try:
                    watched = int(float(itm['duration']) * float(progress / 100))
                except:
                    watched = 0
                debug('itm {} {} {} {} {} {}'.format(scid, itm, itm['duration'], watched, progress, tr))
                item.set_watched(watched)
                d = datetime.fromtimestamp(self.utc2timestamp(tr.get('paused_at')))
                item.set_last_played(d.strftime('%Y-%m-%d %H:%M:%S'))
            dialog.close()
        pass

    def sync_local(self, type, last, force=False):
        if type == 'movies':
            return self.sync_local_movies(last)
        else:
            return self.sync_local_episodes(last, force=force)

    def scroble(self, id, season=None, episode=None, percent=0, action='stop'):
        data = {
            "action": action,
            "progress": float(percent),
            "parse": False,
        }
        if season is not None:
            # ep_info = self.get_episode_info(id, season, episode)
            data.update({"show": {"ids": {"trakt": id}}, "episode": {"season": season, "number": episode}})
        else:
            data.update({"movie": {"ids": {"trakt": id}}})
        with Trakt.configuration.oauth.from_response(self.authorization):
            with Trakt.configuration.http(retry=True):
                debug('scrobble obj: {}'.format(data))
                try:
                    result = Trakt['scrobble'].action(**data).json()
                except:
                    result = None
                return result
        pass

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

    def sync_local_episodes(self, last=0, force=False):
        last_at = TraktAPI.utc2timestamp(last)
        dialog = dprogressgb()
        dialog.create('sync_local_episodes Trakt.TVShow')
        debug('sync local episodes {} / {}'.format(last, last_at))
        if force:
            data = self.get_shows_watched({})
        else:
            data = self.get_shows_history(datetime.utcfromtimestamp(last_at))
        if data == []:
            dialog.close()
            return True
        items = {}
        for trid, num, eps in data:
            if self.abortRequested():
                dialog.close()
                return False
            items.update({trid: eps})
        res, items = self.trakt2sc(items, 3)
        pos = 0
        total = len(res)
        for scid, trid in res.items():
            if self.abortRequested():
                dialog.close()
                return False
            pos += 1
            max_time = 0
            last_ep = None
            debug('episodes: {}%'.format(int(pos / total * 100)))
            dialog.update(int(pos / total * 100))
            item = SCKODIItem(scid)
            debug('ITEM: {}'.format(item.data))
            for s, e, watched_at in items[int(trid['trakt'])]:
                item.series = s
                item.episode = e
                if self.abortRequested():
                    dialog.close()
                    return False
                wa = TraktAPI.utc2timestamp(watched_at)

                if int(wa) >= int(max_time):
                    ''' ak su epizody vsetky oznacene ako videne v rovnaky cas alebo novsie '''
                    max_time = wa
                    last_ep = (s, e)

                old = item.get_play_count()
                if force or old is None or last_at is None or wa >= last_at:
                    debug('SCID ADD {} {}x{}'.format(scid, s, e))
                    item.set_play_count('1')

            if item and last_ep is not None:
                item.set_last_ep(last_ep[0], last_ep[1], max_time)
        dialog.close()
        return True

    def abortRequested(self):
        return self.monitor.abortRequested() or player.isPlayback()

    def sync_local_movies(self, last):
        self.sync_playback_movies(last)
        data = self.get_movies_watched({})
        res, movies = self.sync_get_list(data, 1)
        debug('res: {}'.format(len(res)))
        all_items = self.storage['watched.movies'].get()[:]
        # debug('na zaciatku {}'.format(all_items))
        dialog = dprogressgb()
        dialog.create('sync_local_movies Trakt.Movies 1')
        pos = 0
        max = len(res)
        for scid, trid in res.items():
            if self.monitor.abortRequested():
                return False
            pos += 1
            dialog.update(int(pos/max*100))
            # debug('SCID: {}'.format(scid))
            # debug('w {}'.format(self.storage['watched.{}'.format(type)]))
            item = SCKODIItem(scid)
            if scid not in all_items:
                debug('pridavam do zoznamu {}'.format(scid))
                self.storage['watched.movies'].add(scid)
                item.set_play_count('1')
            else:
                all_items.remove(scid)
            pass
            # debug('{} -> {}'.format(scid, movies.get(trid)))
        dialog.close()
        dialog.create('sync_local_movies Trakt.Movies 2')
        # debug('Zostali nam po synchre: {}'.format(all_items))
        if len(all_items) > 0:
            max = len(all_items)
            pos = 0
            for scid in all_items:
                if self.monitor.abortRequested():
                    return False
                pos += 1
                dialog.update(int(pos / max * 100))
                # debug('mazem {}'.format(scid))
                self.storage['watched.movies'].add(scid, remove_only=True)
                item = SCKODIItem(scid)
                item.set_play_count(None)
        dialog.close()
        return True
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
            if 'trakt' in trid:
                obj = {"movies": [{"ids": {"trakt": int(trid.get('trakt'))}}]}
            else:
                obj = {"movies": [{"ids": {"trakt": int(trid)}}]}
        else:
            ep_info = self.get_episode_info(int(trid), season, episode)
            debug('EP INFO: {}'.format(ep_info))
            if ep_info:
                obj = {"episodes": [{"ids": ep_info.get('ids', {})}]}
            else:
                obj = {"shows": [
                    {"ids": {
                        "trakt": int(trid)},
                        "seasons": {
                            "number": season,
                            "episodes": [
                                {"number": episode}
                            ]
                        }
                    }
                ]}
        debug('posielam obj: {}'.format(dumps(obj)))
        if times is not None and int(times) > 0:
            ret = self.add_to_history(obj)
        else:
            ret = self.remove_from_history(obj)
        debug('Hotovo trakt history.... {}'.format(ret))

    def show_items(self, items, sc):
        sc.url = '/Search/getTrakt'
        sc.payload = {'ids': dumps(items)}
        sc.call_url_and_response()

    def action(self, action, sc):
        from resources.lib.params import params
        debug('trakt action: {} / {}'.format(action, params.args))
        if action == 'trakt.login':
            set_setting_as_bool('trakt.enabled', True)
            self.login()
        elif action == 'trakt.logout':
            set_setting('trakt.authorization', '')
            set_setting('trakt.user', '')
        elif action == 'trakt.list':
            u = 'me' if not params.args.get('user', None) else params.args.get('user')
            if u == 'me':
                for i in ['watchlist']:
                    itm = {'type': 'action', 'title': i, 'action': 'trakt.list.items', 'id': i, 'user': u}
                    item = SCItem(itm)
                    if item.visible:
                        sc.items.append(item.get())

            for l in self.get_lists(user=u):
                # l.name = l.name.encode('utf-8')
                itm = {'type': 'action', 'title': l.name, 'action': 'trakt.list.items', 'id': l.id, 'user': u}
                item = SCItem(itm)
                if item.visible:
                    sc.items.append(item.get())
        elif action == 'trakt.sync.shows':
            self.sync_local_episodes(last=0, force=True)
        elif action == 'trakt.list.items':
            u = 'me' if not params.args.get('user', None) else params.args.get('user')
            name = params.args.get('id')
            if name == 'watchlist':
                data = self.get_watchlist(u).json()
            else:
                data = self.get_list_items(name, u).items(parse=False).json()
            items = []
            for i in data:
                t = i.get('type')
                debug('item: {} {}'.format(t, i))
                if t not in ['movie', 'tvshow', 'show']:
                    continue
                sc_type = 1 if t == 'movie' else 3
                data = i.get(t, {})
                ids = data.get('ids')
                tr = ids.get('trakt')
                itm = "{},{}".format(sc_type, tr)
                items.append(itm)
            debug('items: {}'.format(items))
            self.show_items(items, sc)
        else:
            debug('Neznama akcia trakt.tv {}'.format(action))
        sc.succeeded = True
        sc.end()


trakt = TraktAPI()
