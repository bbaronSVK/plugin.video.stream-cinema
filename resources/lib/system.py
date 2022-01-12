# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals

import requests
import xbmc

from resources.lib.constants import HTTP
from resources.lib.kodiutils import get_system_platform, get_app_name, addon
from resources.lib.language import get_language_code
from resources.lib.common.logger import info, debug

SYSTEM_BUILD_VERSION = xbmc.getInfoLabel("System.BuildVersion")
SYSTEM_VERSION = int(SYSTEM_BUILD_VERSION.split(".")[0])
SYSTEM_LANG_CODE = get_language_code()


def user_agent(system=True):
    if system is False or not hasattr(xbmc, 'getUserAgent'):

        version = SYSTEM_BUILD_VERSION
        sp = version.find(' ')
        if sp > 0:
            version = version[:sp]

        platform = get_system_platform()
        app = get_app_name()

        if platform == 'linux':
            useragent = '{}/{} (X11; U; Linux i686)'
        elif platform == 'android':
            useragent = '{}/{} (Linux; Android)'
        elif platform == 'windows':
            useragent = '{}/{} (Windows; U; Windows NT)'
        elif platform == 'ios':
            useragent = '{}/{} (iPhone; CPU iPhone OS like Mac OS X)'
        elif platform == 'osx':
            useragent = '{}/{} (Macintosh; Intel Mac OS X)'
        else:
            useragent = '{}/{} (X11; U; Unknown i686)'
        useragent = useragent.format(app, version)
    else:
        useragent = xbmc.getUserAgent()

    return '{0} ({1}; ver{2})'.format(
        useragent,
        SYSTEM_LANG_CODE,
        addon.getAddonInfo('version')
    )


def get_app_log():
    return get_app_name()


class Http:
    @staticmethod
    def request(method, url, timeout=HTTP.TIMEOUT, **kwargs):
        # info('URL {}'.format(url))
        ret = Http.req().request(
            method=method,
            url=url,
            timeout=timeout,
            **kwargs
        )
        # info('url req head: {}'.format(ret.request.headers))
        # info('url res head: {}'.format(ret.headers))
        debug('Http url: {}'.format(ret.url))
        try:
            ret.raise_for_status()
        except requests.exceptions.HTTPError as e:
            ret = e.response

        return ret

    @staticmethod
    def req():
        return requests

    @staticmethod
    def get(url, **kwargs):
        return Http.request(HTTP.GET, url, **kwargs)

    @staticmethod
    def post(url, **kwargs):
        return Http.request(HTTP.POST, url, **kwargs)

    @staticmethod
    def head(url, **kwargs):
        return Http.request(HTTP.HEAD, url, **kwargs)

    @staticmethod
    def delete(url, **kwargs):
        return Http.request(HTTP.DELETE, url, **kwargs)

    @staticmethod
    def put(url, **kwargs):
        return Http.request(HTTP.PUT, url, **kwargs)

    @staticmethod
    def patch(url, **kwargs):
        return Http.request(HTTP.PATCH, url, **kwargs)


class Sess(Http):
    @staticmethod
    def req():
        return requests.Session

