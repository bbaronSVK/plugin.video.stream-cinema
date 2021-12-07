# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals

import datetime
import time

from resources.lib.common.cache import SimpleCache, use_cache
from resources.lib.common.logger import debug, info
from resources.lib.constants import BASE_URL, API_VERSION, SC
from resources.lib.kodiutils import get_uuid, get_skin_name, get_setting_as_bool, get_setting_as_int, get_setting
from resources.lib.system import user_agent, Http, SYSTEM_LANG_CODE

try:
    # Python 3
    from urllib.parse import urlparse, parse_qs
except ImportError:
    # Python 2
    from urlparse import urlparse, parse_qs


class Sc:
    RATING_MAP = {
        "0": 0,
        "1": 6,
        "2": 12,
        "3": 15,
        "4": 18,
    }

    cache = SimpleCache()

    @staticmethod
    def get(path, params=None):
        sorted_values, url = Sc.prepare(params, path)
        key = '{}{}'.format(url, sorted_values)
        debug('CALL {} PARAMS {} KEY {}'.format(url, sorted_values, key))
        start = time.time()
        ret = Sc.cache.get(key)
        if ret is None:
            res = Http.get(url, headers=Sc.headers(), params=sorted_values)
            res.raise_for_status()
            ret = res.json()
            Sc.save_cache(ret, key)
        else:
            info('GET from cache')
        end = time.time()

        debug('GET took {0:.2f}ms'.format((end - start) * 1000))
        return ret

    @staticmethod
    def prepare(params, path):
        url = BASE_URL + path
        o = urlparse(url)
        query = parse_qs(o.query)
        url = o._replace(query=None).geturl()
        p = Sc.default_params()
        # debug('p: {}'.format(p))
        query.update(p)
        if params is not None:
            query.update(params)
        sorted_values = sorted(query.items(), key=lambda val: val[0])
        # debug('sorted: {}'.format(sorted_values))
        return sorted_values, url

    @staticmethod
    def post(path, **kwargs):
        sorted_values, url = Sc.prepare(path=path, params={})
        start = time.time()
        res = Http.post(url, params=sorted_values, headers=Sc.headers(), **kwargs)
        end = time.time()
        debug('POST took {0:.2f}ms'.format((end - start) * 1000))
        return res.json()

    @staticmethod
    def default_params():
        params = {
            'ver': API_VERSION,
            'uid': get_uuid(),
            'skin': get_skin_name(),
            'lang': SYSTEM_LANG_CODE
        }
        # plugin_url = 'plugin://{}/{}'.format(ADDON_ID, query.params.orig_args if query.params.orig_args else '')
        # try:
        #     kv = KodiViewModeDb()
        #     sort = kv.get_sort(plugin_url)
        # except:
        #     sort = (0, 1)
        # try:
        #     if sort is not None:
        #         params.update({'sm': '{},{}'.format(sort[0], sort[1])})
        # except:
        #     debug('ERR API SORT: {}'.format(traceback.format_exc()))
        #     pass
        parental_control = Sc.parental_control_is_active()
        if get_setting_as_bool('stream.dubed') or (parental_control and get_setting_as_bool('parental.control.dubed')):
            params.update({'dub': 1})

        if not parental_control and get_setting_as_bool('stream.dubed.titles'):
            params.update({'dub': 1, "tit": 1})

        if parental_control:
            params.update({"m": Sc.RATING_MAP.get(get_setting('parental.control.rating'))})

        if get_setting_as_bool('plugin.show.genre'):
            params.update({'gen': 1})

        if get_setting_as_bool('plugin.show.old.menu'):
            params.update({'old': 1})

        return params

    @staticmethod
    def parental_control_is_active():
        now = datetime.datetime.now()
        hour_start = get_setting_as_int('parental.control.start')
        hour_now = now.hour
        hour_end = get_setting_as_int('parental.control.end')
        return get_setting_as_bool('parental.control.enabled') and hour_start <= hour_now <= hour_end

    @staticmethod
    def headers():
        return {
            'User-Agent': user_agent(),
            'X-Uuid': get_uuid(),
        }

    @staticmethod
    def up_next(id, s, e):
        url = '/upNext/{}/{}/{}'.format(id, s, e)
        try:
            data = Sc.get(url)
        except:
            data = {'error': 'error'}
        return data

    @staticmethod
    def save_cache(ret, key):
        ttl = 1800
        if SC.ITEM_SYSTEM in ret and 'TTL' in ret[SC.ITEM_SYSTEM]:
            ttl = int(ret[SC.ITEM_SYSTEM]['TTL'])

        info('SAVE TO CACHE {} / {}'.format(ttl, key))
        Sc.cache.set(key, ret, datetime.timedelta(seconds=ttl))
