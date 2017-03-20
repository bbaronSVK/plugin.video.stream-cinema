import xbmcplugin

__scriptid__ = 'plugin.video.stream-cinema'
__scriptname__ = 'stream-cinema.online'
BASE_URL="http://stream-cinema.online/kodi"
API_VERSION="1"
player = None
uid = None
submiturl = 'http://movies.bbaron.sk/plugin/submit/'

(v1, v2, v3) = str(xbmcplugin.__version__).split('.')
if int(v1) == 2 and int(v2) <= 20:
    xbmcplugin.SORT_METHOD_VIDEO_USER_RATING = 20

# lebo medved na 4 je maco
sortmethod = {
    14:	xbmcplugin.SORT_METHOD_ALBUM,
    15:	xbmcplugin.SORT_METHOD_ALBUM_IGNORE_THE,
    11:	xbmcplugin.SORT_METHOD_ARTIST,
    13:	xbmcplugin.SORT_METHOD_ARTIST_IGNORE_THE,
    42:	xbmcplugin.SORT_METHOD_BITRATE,
    40:	xbmcplugin.SORT_METHOD_CHANNEL,
    17:	xbmcplugin.SORT_METHOD_COUNTRY,
    3:	xbmcplugin.SORT_METHOD_DATE,
    21:	xbmcplugin.SORT_METHOD_DATEADDED,
    43:	xbmcplugin.SORT_METHOD_DATE_TAKEN,
    6:	xbmcplugin.SORT_METHOD_DRIVE_TYPE,
    8:	xbmcplugin.SORT_METHOD_DURATION,
    24:	xbmcplugin.SORT_METHOD_EPISODE,
    5:	xbmcplugin.SORT_METHOD_FILE,
    34:	xbmcplugin.SORT_METHOD_FULLPATH,
    16:	xbmcplugin.SORT_METHOD_GENRE,
    1:	xbmcplugin.SORT_METHOD_LABEL,
    35:	xbmcplugin.SORT_METHOD_LABEL_IGNORE_FOLDERS,
    2:	xbmcplugin.SORT_METHOD_LABEL_IGNORE_THE,
    36:	xbmcplugin.SORT_METHOD_LASTPLAYED,
    38:	xbmcplugin.SORT_METHOD_LISTENERS,
    30:	xbmcplugin.SORT_METHOD_MPAA_RATING,
    0:	xbmcplugin.SORT_METHOD_NONE,
    37:	xbmcplugin.SORT_METHOD_PLAYCOUNT,
    23:	xbmcplugin.SORT_METHOD_PLAYLIST_ORDER,
    28:	xbmcplugin.SORT_METHOD_PRODUCTIONCODE,
    22:	xbmcplugin.SORT_METHOD_PROGRAM_COUNT,
    4:	xbmcplugin.SORT_METHOD_SIZE,
    29:	xbmcplugin.SORT_METHOD_SONG_RATING,
    32:	xbmcplugin.SORT_METHOD_STUDIO,
    33:	xbmcplugin.SORT_METHOD_STUDIO_IGNORE_THE,
    9:	xbmcplugin.SORT_METHOD_TITLE,
    10:	xbmcplugin.SORT_METHOD_TITLE_IGNORE_THE,
    7:	xbmcplugin.SORT_METHOD_TRACKNUM,
    39:	xbmcplugin.SORT_METHOD_UNSORTED,
    19:	xbmcplugin.SORT_METHOD_VIDEO_RATING,
    31:	xbmcplugin.SORT_METHOD_VIDEO_RUNTIME,
    26:	xbmcplugin.SORT_METHOD_VIDEO_SORT_TITLE,
    27:	xbmcplugin.SORT_METHOD_VIDEO_SORT_TITLE_IGNORE_THE,
    25:	xbmcplugin.SORT_METHOD_VIDEO_TITLE,
    20:	xbmcplugin.SORT_METHOD_VIDEO_USER_RATING,
    18:	xbmcplugin.SORT_METHOD_VIDEO_YEAR
}
