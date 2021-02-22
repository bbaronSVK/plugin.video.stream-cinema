# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals

import sys

import xbmcplugin
import xbmcaddon

python_version = sys.version_info[0]
PY2 = python_version == 2
PY3 = python_version == 3
try:
    HANDLE = int(sys.argv[1])
except:
    HANDLE = -1

ADDON_ID = 'plugin.video.stream-cinema'
ADDON = xbmcaddon.Addon(id=ADDON_ID)
BASE_URL = 'https://stream-cinema.online/kodi'
API_VERSION = '2.0'


class GUI:
    BOTTOM = 'bottom'
    TOP = 'top'


class SC:
    ACTION = 'action'
    ACTION_CMD = 'cmd'
    ACTION_CSEARCH = 'csearch'
    ACTION_DEBUG = 'debug'
    ACTION_LAST = 'last'
    ACTION_PIN = 'pin'
    ACTION_PLAY_URL = 'playUrl'
    ACTION_SELECT_STREAM = 'selectStream'
    CMD = 'cmd'
    DEFAULT_LANG = 'cs'
    ITEM_ACTION = 'action'
    ITEM_ART = 'art'
    ITEM_AUDIO_INFO = 'ainfo'
    ITEM_BITRATE = 'bitrate'
    ITEM_CMD = 'cmd'
    ITEM_DIR = 'dir'
    ITEM_FOCUS = 'focus'
    ITEM_I18N_ART = 'i18n_art'
    ITEM_I18N_INFO = 'i18n_info'
    ITEM_ID = 'id'
    ITEM_IDENT = 'ident'
    ITEM_INFO = 'info'
    ITEM_LANG = 'lang'
    ITEM_MENU = 'menu'
    ITEM_NEXT = 'next'
    ITEM_PROVIDER = 'provider'
    ITEM_QUALITY = 'quality'
    ITEM_SIZE = 'size'
    ITEM_STRMS = 'strms'
    ITEM_SUBS = 'subs'
    ITEM_SYSTEM = 'system'
    ITEM_TITLE = 'title'
    ITEM_TYPE = 'type'
    ITEM_URL = 'url'
    ITEM_VIDEO = 'video'
    ITEM_VIDEO_INFO = 'vinfo'
    ITEM_VISIBLE = 'visible'
    MEDIA_TYPE = 'mediatype'
    MEDIA_TYPE_AUDIO = 'audio'
    MEDIA_TYPE_EPISODE = 'episode'
    MEDIA_TYPE_FILE = 'file'
    MEDIA_TYPE_SEASON = 'season'
    MEDIA_TYPE_TV_SHOW = 'tvshow'
    MEDIA_TYPE_VIDEO = 'video'
    NEXT = 'next'
    PROVIDER = 'kraska'
    RUN_PLUGIN = 'RunPlugin({})'
    TXT_PINNED = 'p-{}'
    TRAKT_CACHE_WATCHET_ACTIVITY = 'SC:watched:activity'


class HTTP:
    TIMEOUT = 10
    GET = 'get'
    POST = 'post'
    HEAD = 'head'
    OPTION = 'option'
    PUT = 'put'
    DELETE = 'delete'
    PATCH = 'patch'


class KodiDbMap:
    MyVideos = {16: 99, 17: 107, 18: 116, 19: 119}
    MyMusic = {16: 56, 17: 60, 18: 72, 19: 82}
    Textures = {16: 13, 17: 13, 18: 13, 19: 13}
    Addons = {16: 20, 17: 27, 18: 27, 19: 33}
    ViewModes = {16: 6, 17: 6, 18: 6, 19: 6}


SORT_METHODS = {
    14: xbmcplugin.SORT_METHOD_ALBUM,
    15: xbmcplugin.SORT_METHOD_ALBUM_IGNORE_THE,
    11: xbmcplugin.SORT_METHOD_ARTIST,
    13: xbmcplugin.SORT_METHOD_ARTIST_IGNORE_THE,
    42: xbmcplugin.SORT_METHOD_BITRATE,
    40: xbmcplugin.SORT_METHOD_CHANNEL,
    17: xbmcplugin.SORT_METHOD_COUNTRY,
    3: xbmcplugin.SORT_METHOD_DATE,
    21: xbmcplugin.SORT_METHOD_DATEADDED,
    43: xbmcplugin.SORT_METHOD_DATE_TAKEN,
    6: xbmcplugin.SORT_METHOD_DRIVE_TYPE,
    8: xbmcplugin.SORT_METHOD_DURATION,
    24: xbmcplugin.SORT_METHOD_EPISODE,
    5: xbmcplugin.SORT_METHOD_FILE,
    34: xbmcplugin.SORT_METHOD_FULLPATH,
    16: xbmcplugin.SORT_METHOD_GENRE,
    1: xbmcplugin.SORT_METHOD_LABEL,
    35: xbmcplugin.SORT_METHOD_LABEL_IGNORE_FOLDERS,
    2: xbmcplugin.SORT_METHOD_LABEL_IGNORE_THE,
    36: xbmcplugin.SORT_METHOD_LASTPLAYED,
    38: xbmcplugin.SORT_METHOD_LISTENERS,
    30: xbmcplugin.SORT_METHOD_MPAA_RATING,
    0: xbmcplugin.SORT_METHOD_NONE,
    37: xbmcplugin.SORT_METHOD_PLAYCOUNT,
    23: xbmcplugin.SORT_METHOD_PLAYLIST_ORDER,
    28: xbmcplugin.SORT_METHOD_PRODUCTIONCODE,
    22: xbmcplugin.SORT_METHOD_PROGRAM_COUNT,
    4: xbmcplugin.SORT_METHOD_SIZE,
    29: xbmcplugin.SORT_METHOD_SONG_RATING,
    32: xbmcplugin.SORT_METHOD_STUDIO,
    33: xbmcplugin.SORT_METHOD_STUDIO_IGNORE_THE,
    9: xbmcplugin.SORT_METHOD_TITLE,
    10: xbmcplugin.SORT_METHOD_TITLE_IGNORE_THE,
    7: xbmcplugin.SORT_METHOD_TRACKNUM,
    39: xbmcplugin.SORT_METHOD_UNSORTED,
    19: xbmcplugin.SORT_METHOD_VIDEO_RATING,
    31: xbmcplugin.SORT_METHOD_VIDEO_RUNTIME,
    26: xbmcplugin.SORT_METHOD_VIDEO_SORT_TITLE,
    27: xbmcplugin.SORT_METHOD_VIDEO_SORT_TITLE_IGNORE_THE,
    25: xbmcplugin.SORT_METHOD_VIDEO_TITLE,
    20: xbmcplugin.SORT_METHOD_VIDEO_USER_RATING,
    18: xbmcplugin.SORT_METHOD_VIDEO_YEAR
}
