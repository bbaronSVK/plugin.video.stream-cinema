from __future__ import print_function, unicode_literals

import re
import time
from json import dumps, loads

import xbmcvfs
from xbmcgui import ListItem

from resources.lib.api.kraska import Kraska, ResolveException
from resources.lib.api.sc import Sc
from resources.lib.common.lists import List, SCKODIItem
from resources.lib.common.logger import info, debug
from resources.lib.common.storage import preferred_lang_list
from resources.lib.constants import ADDON_ID, SC, GUI
from resources.lib.debug import try_catch
from resources.lib.gui import get_cond_visibility as gcv, home_win
from resources.lib.gui.dialog import dselect, dok
from resources.lib.kodiutils import create_plugin_url, convert_bitrate, get_setting_as_bool, get_setting_as_int, \
    get_setting, get_info_label, get_system_platform, decode, make_nfo_content, translate_path, make_legal_filename, \
    microtime, get_isp
from resources.lib.language import Strings
from resources.lib.params import params
from resources.lib.services.Settings import settings
from resources.lib.system import SYSTEM_LANG_CODE

list_item = ListItem
list_hp = List('HP')


def parental_history():
    return get_setting_as_bool('parental.control.enabled')  # and get_setting_as_bool('parental.control.history')


def get_history_item_name(item):
    return 'p-{}'.format(item) if parental_history() else item


class SCItem:
    def __init__(self, data):
        self.item = None
        self.visible = False
        if SC.ITEM_TYPE in data:
            self.item_by_type(data)
        elif SC.ITEM_STRMS in data:
            info('PLAY ITEM')
            self.item = SCPlayItem(data)
        else:
            info('Neznama polozka {}'.format(str(data)))

    def item_by_type(self, data):
        item_type = data.get(SC.ITEM_TYPE, None)
        if item_type == SC.ITEM_DIR:
            self.item = SCDir(data)
        elif item_type == SC.ITEM_VIDEO:
            self.item = SCVideo(data)
        elif item_type == SC.ITEM_HPDIR:
            self.item = SCHPDir(data)
        elif item_type == SC.ITEM_CUSTOM_FILTER:
            self.item = SCCustomFilterDir(data)
        elif item_type == SC.ITEM_CMD:
            self.item = SCCmd(data)
        elif item_type == SC.ITEM_ACTION:
            self.item = SCAction(data)
        elif item_type == SC.ITEM_NEXT:
            self.item = SCNext(data)
        elif item_type == 'ldir':
            self.item = SCLDir(data)
        elif item_type == 'add_custom_filter':
            self.item = SCAction(data)
        else:
            info('Nepodporovana polozka {} {}'.format(item_type, data))

        try:
            self.visible = self.item.visible()
        except:
            pass

    def li(self):
        return self.item.item

    def get(self):
        return self.item.get()


class SCBaseItem:
    def __init__(self, data, debug=False):
        self.item = list_item()
        self.data = data
        self.info_set = False
        self.info = {}
        self.debug = debug

        if SC.ITEM_TITLE in data:
            self.item.setLabel(data.get(SC.ITEM_TITLE))

        if SC.ITEM_URL in data:
            url = create_plugin_url(data)
            self.item.setPath(url)

        if SC.ITEM_ART in data:
            self.set_art()
        elif SC.ITEM_I18N_ART in data:
            self.set_i18n_art()

        if SC.ITEM_INFO in data:
            self.set_info()
        elif SC.ITEM_I18N_INFO in data:
            self._set_info(self.i18n_info({}))

        if 'cast' in data:
            self.set_cast()

        if 'unique_ids' in data:
            self.set_unique_ids()

        if 'stream_info' in data:
            self.set_stream_info()

    @try_catch('set_stream_info')
    def set_stream_info(self):
        stream_info = self.data.get('stream_info')
        for k, v in enumerate(stream_info):
            self.item.addStreamInfo(v, stream_info.get(v)) if v in ['video', 'audio'] else ''

        if 'fvideo' in stream_info:
            debug('FVIDEO: {}'.format(stream_info['fvideo']))
            self.item.setProperty('video', stream_info['fvideo'])

        if 'faudio' in stream_info:
            self.item.setProperty('audio', stream_info['faudio'])

    @try_catch('set_unique_ids')
    def set_unique_ids(self):
        self.item.setUniqueIDs(self.data.get('unique_ids'))

    @try_catch('set_cast')
    def set_cast(self):
        self.item.setCast(self.data.get('cast', []))

    @try_catch('set_art')
    def set_art(self):
        self.item.setArt(self.data.get(SC.ITEM_ART, {}))

    @try_catch('set_i18n_art')
    def set_i18n_art(self):
        i18n = self.data.get(SC.ITEM_I18N_ART)
        lang = SYSTEM_LANG_CODE
        if lang not in i18n:
            debug('jazyk {} nemame, tak nastavujem cs'.format(lang))
            lang = SC.DEFAULT_LANG
        # debug('jazyk {}'.format(lang))
        self.item.setArt(i18n.get(lang))

    @try_catch('_set_info')
    def _set_info(self, item_info):
        if self.debug:
            debug('set_info {}'.format(item_info))
        self.info.update(item_info)
        try:
            if SC.ITEM_TITLE in item_info:
                title = '{}'.format(item_info.get(SC.ITEM_TITLE))
                self.item.setLabel(title)

            if self.data.get('play'):
                if 'otitle' in item_info:
                    item_info.update({SC.ITEM_TITLE: item_info['otitle']})
                    del item_info['otitle']

                if 'epname' in item_info:
                    item_info.update({SC.ITEM_TITLE: item_info['epname']})
                    del item_info['epname']
            else:
                if 'epname' in item_info:
                    del item_info['epname']

                if 'otitle' in item_info:
                    del item_info['otitle']

            for i, e in enumerate(item_info):
                # debug('set info {} {}'.format(i, e))
                self.item.setProperty(e, '{}'.format(item_info[e]))

            if item_info.get('mediatype', '') == 'season' and item_info.get('episode'):
                item = SCKODIItem(self.data.get(SC.ITEM_ID))
                data = item.data
                total_episodes = item_info.get('episode')
                watched = len(data.get('series:{}'.format(item_info.get('season')), {}))
                debug('Mame seriu {} s {}/{} epizodami'.format(item_info.get('season'), watched, total_episodes))
                if watched >= total_episodes:
                    item_info.update({'playcount': '1'})

            self.item.setInfo('video', item_info)
            self.item.setProperty('original_title', item_info.get('originaltitle'))
            self.info_set = True
        except Exception as e:
            import traceback
            info('-----------------------------------------------------------------')
            info('set info error [{}]'.format(str(traceback.format_exc())))
            info('-----------------------------------------------------------------')

    @try_catch('set_info')
    def set_info(self):
        item_info = self.data.get(SC.ITEM_INFO, {})
        if SC.ITEM_I18N_INFO in self.data:
            item_info = self.i18n_info(item_info)
        self._set_info(item_info)

    @try_catch('i18n_info')
    def i18n_info(self, item_info={}):
        i18n = self.data.get(SC.ITEM_I18N_INFO)
        lang = SYSTEM_LANG_CODE
        if lang not in i18n:
            debug('jazyk {} nemame, tak nastavujem cs'.format(lang))
            lang = SC.DEFAULT_LANG
        item_info.update(i18n.get(lang))
        return item_info

    @try_catch('get')
    def get(self):
        if self.info_set is False:
            self._set_info({SC.MEDIA_TYPE: SC.MEDIA_TYPE_VIDEO})
        return self.item.getPath(), self.item, True

    @try_catch('visible')
    def visible(self):
        visible = True
        if SC.ITEM_VISIBLE in self.data:
            visible = gcv(self.data.get(SC.ITEM_VISIBLE))

        return visible


class SCStreamSelect(SCBaseItem):
    def __init__(self, data):
        SCBaseItem.__init__(self, data)
        label2 = ''
        strm_nfo = data.get('stream_info', {})
        titulky = True if [x for x in strm_nfo.get('langs', "") if '+tit' in x] else False

        if 'bitrate' in data:
            label2 += 'bitrate: [B]{}[/B]'.format(convert_bitrate(int(data.get('bitrate'))))
        if 'linfo' in data:
            label2 += '   audio: [B][UPPERCASE]{}[/UPPERCASE][/B]'.format(', '.join(data['linfo']))
            if titulky:
                label2 += ', [B]+tit[/B]'

        if 'grp' in strm_nfo:
            label2 += '   grp: [B]{}[/B]'.format(strm_nfo['grp'])

        if 'src' in strm_nfo:
            label2 += '   src: [B]{}[/B]'.format(strm_nfo['src'])

        if 'video' in strm_nfo and 'aspect' in strm_nfo['video'] and 'ratio' in strm_nfo['video']:
            label2 += '   asp: [B]{}[/B]'.format(strm_nfo['video']['ratio'])

        if SC.ITEM_URL in data:
            url = data.get(SC.ITEM_URL)
            self.item.setPath(url)
        if SC.ITEM_PROVIDER in data:
            self.item.setProperty(SC.ITEM_PROVIDER, data.get(SC.ITEM_PROVIDER))
        if SC.ITEM_SUBS in data:
            self.item.setProperty(SC.ITEM_SUBS, data.get(SC.ITEM_SUBS))
        if SC.ITEM_ID in data:
            self.item.setProperty(SC.ITEM_ID, data.get('id'))
        self.item.setLabel2(label2)


class SCDirContext:
    def __init__(self):
        pass


class SCLDir(SCBaseItem):
    def __init__(self, data):
        SCBaseItem.__init__(self, data)
        if SC.ITEM_URL in data:
            url = self.translate_path(data[SC.ITEM_URL])
            self.item.setPath(url)

    def translate_path(self, path):
        import re
        found = re.search('sc://(?P<typ>[^\(]+)\((?P<param1>[^\s,\)]+)\)', path)
        if found.group('typ') == 'config':
            path = make_legal_filename(translate_path(get_setting(found.group('param1'))))
        return path


class SCDir(SCBaseItem):
    build_ctx = True

    def __init__(self, data):
        SCBaseItem.__init__(self, data)
        self.lib = List(SC.ITEM_LIBRARY)
        item_id = self.data.get(SC.ITEM_ID)
        if item_id and item_id in self.lib.get():
            label = "[COLOR red]*[/COLOR] {0}".format(self.item.getLabel())
            self.item.setLabel(label)

        if SC.ITEM_URL in data:
            url = create_plugin_url(data)
            self.item.setPath(url)
        if self.build_ctx:
            self.make_ctx()

    def make_ctx(self):
        context_menu = []

        if 'listType' in params.args:
            context_menu.append([Strings.txt(Strings.CONTEXT_REMOVE), 'RunPlugin({})'.format(create_plugin_url({
                SC.ACTION: SC.ACTION_REMOVE_FROM_LIST,
                SC.ITEM_ID: self.data.get(SC.ITEM_ID),
                SC.ITEM_PAGE: get_history_item_name(self.data.get('lid'))
            }))])

        item_id = self.data.get(SC.ITEM_URL)
        # debug('ITEM: {}'.format(item_id))
        if 0 and item_id and settings.get_setting('tvshow.library.path'):

            if item_id and item_id in self.lib.get():
                debug('Uz je v kniznici s odberom')
                context_menu.append(
                    (Strings.txt(Strings.CONTEXT_REMOVE_FROM_SUB), 'RunPlugin({})'.format(create_plugin_url({
                        SC.ITEM_ACTION: SC.ACTION_REMOVE_FROM_SUBSCRIPTION,
                        SC.ITEM_ID: item_id
                    }))))
            else:
                debug('Este nieje v odbere')
                context_menu.append(
                    (Strings.txt(Strings.CONTEXT_ADD_TO_LIBRARY_WITH_SUB), 'RunPlugin({})'.format(create_plugin_url({
                        SC.ITEM_ACTION: SC.ACTION_ADD_TO_LIBRARY_WITH_SUBSCRIPTION,
                        SC.ITEM_ID: item_id
                    }))))

            context_menu.append((Strings.txt(Strings.CONTEXT_ADD_TO_LIBRARY), 'RunPlugin({})'.format(create_plugin_url({
                SC.ITEM_ACTION: SC.ACTION_ADD_TO_LIBRARY,
                SC.ITEM_ID: self.data.get(item_id)
            }))))

        if params.args.get('url'):
            context_menu.append((Strings.txt(Strings.CONTEXT_PIN_UNPIN), 'RunPlugin({})'.format(create_plugin_url({
                SC.ITEM_ACTION: SC.ACTION_PIN,
                SC.ITEM_URL: params.args.get(SC.ITEM_URL),
                SC.ITEM_ID: self.data.get(SC.ITEM_URL)
            }))))

            if get_system_platform() == 'android':
                context_menu.append(
                    (Strings.txt(Strings.CONTEXT_ADD_TO_ANDROID_TV), 'RunPlugin({})'.format(create_plugin_url({
                        SC.ITEM_ACTION: SC.ACTION_ANDROID,
                        SC.ITEM_URL: self.data.get(SC.ITEM_URL),
                        SC.ITEM_ID: self.item.getLabel()
                    }))))

            context_menu.append((Strings.txt(Strings.CONTEXT_PIN_TO_HP), 'RunPlugin({})'.format(create_plugin_url({
                SC.ITEM_ACTION: SC.ACTION_ADD2HP,
                SC.ITEM_URL: self.data.get(SC.ITEM_URL),
                SC.ITEM_ID: self.item.getLabel()
            }))))

        if get_setting_as_bool('stream.autoselect'):
            # debug('data: {}'.format(self.data))
            mediatype = self.data.get(SC.ITEM_INFO, {}).get('mediatype')
            if mediatype == 'tvshow' or mediatype == 'movie':
                item_id = self.data.get(SC.ITEM_ID)
                st = preferred_lang_list
                if st.get(item_id) is not None:
                    context_menu.append((Strings.txt(Strings.CONTEXT_DEL_PREF_LANG).format(st[item_id]),
                                         'RunPlugin({})'.format(create_plugin_url({
                                             SC.ITEM_ACTION: SC.ACTION_DEL_PREFERRED_LANGUAGE,
                                             SC.ITEM_ID: self.data.get(SC.ITEM_ID)
                                         }))))
                else:
                    context_menu.append(
                        (Strings.txt(Strings.CONTEXT_ADD_PREF_LANG), 'RunPlugin({})'.format(create_plugin_url({
                            SC.ITEM_ACTION: SC.ACTION_SET_PREFERRED_LANGUAGE,
                            SC.ITEM_ID: self.data.get(SC.ITEM_ID)
                        }))))

        if context_menu:
            self.item.addContextMenuItems(context_menu)


class SCHPDir(SCDir):
    def __init__(self, data):
        SCDir.__init__(self, data)

    def make_ctx(self):
        context_menu = [(Strings.txt(Strings.CONTEXT_REMOVE), 'RunPlugin({})'.format(create_plugin_url({
            SC.ITEM_ACTION: SC.ACTION_DEL2HP,
            SC.ITEM_URL: self.data.get(SC.ITEM_URL),
            SC.ITEM_ID: self.item.getLabel()
        })))]

        self.item.addContextMenuItems(context_menu)


class SCCustomFilterDir(SCDir):
    def __init__(self, data):
        SCDir.__init__(self, data)

    def make_ctx(self):
        context_menu = [('Remove custom item', 'RunPlugin({})'.format(create_plugin_url({
            SC.ITEM_ACTION: SC.ACTION_DEL_CUSTOM_FILTER,
            SC.ITEM_URL: self.data.get(SC.ITEM_URL),
            SC.ITEM_TITLE: self.item.getLabel(),
            SC.ITEM_PAGE: self.data.get('self_url')
        })))]

        self.item.addContextMenuItems(context_menu)


class SCNext(SCDir):
    def __init__(self, data):
        self.build_ctx = False
        SCDir.__init__(self, data)
        self.item.setProperty('SpecialSort', GUI.BOTTOM)


class SCNFO(SCBaseItem):
    ITEMS_XML = [
        'title',
        'originaltitle',
        'sorttitle',
        'plot',
        'runtime',
        'mpaa',
        'genre',
        'country',
        'director',
        'year',
        'studio',
        'trailer',
        'dateadded',
    ]

    XML_ITEM = '\n<{0}>{1}</{0}>'
    XML_ACTOR = '<actor><name>{name:}</name><role>{role:}</role><order>{order:}</order><thumb>{thumbnail:}</thumb></actor>'
    XML_THUMB = '<thumb aspect="{0}">{1}</thumb>'
    XML_MOVIE = '<movie>{}</movie>'
    DEFAULT_ACTOR = {'name': '', 'role': '', 'order': '', 'thumbnail': ''}

    def __init__(self, data):
        SCBaseItem.__init__(self, data)

    def xml(self):
        out = []

        for pos, item in enumerate(self.info):
            if item in self.ITEMS_XML:
                if isinstance(self.info[item], list):
                    out.append(self.XML_ITEM.format(decode(item), ' / '.join(self.info[item])))
                else:
                    out.append(self.XML_ITEM.format(decode(item), decode(self.info[item])))

        for actor in self.data.get('cast', {}):
            d = self.DEFAULT_ACTOR.copy()
            d.update(actor)
            out.append(self.XML_ACTOR.format(**d))

        i18n = self.data.get(SC.ITEM_I18N_ART)
        lang = SYSTEM_LANG_CODE
        if lang not in i18n:
            lang = SC.DEFAULT_LANG

        art = i18n.get(lang)
        for pos, item in enumerate(art):
            out.append(self.XML_THUMB.format(item, art[item]))

        return decode(self.XML_MOVIE.format(''.join(out)))

    def nfo(self):
        typ = self.data(SC.ITEM_INFO, {}).get('mediatype', 'movie')
        typ = typ if typ == 'movie' else 'tvshow'
        return make_nfo_content(self.data, typ)


class SCVideo(SCBaseItem):
    def __init__(self, data):
        trakt = data['unique_ids']['trakt'] if 'unique_ids' in data and 'trakt' in data['unique_ids'] else None
        self.movie = SCKODIItem(data.get(SC.ITEM_ID), series=data.get('info', {}).get('season'),
                                episode=data.get('info', {}).get('episode'), trakt=trakt)
        internal_info = {}
        play_count = self.movie.get_play_count()
        if play_count is not None and int(play_count) > 0:
            internal_info.update({'playcount': play_count})
        last_played = self.movie.get_last_played()
        if last_played:
            internal_info.update({'lastplayed': last_played})
        if internal_info != {}:
            # debug('update info: {}'.format(internal_info))
            data.get(SC.ITEM_INFO).update(internal_info)

        SCBaseItem.__init__(self, data)
        self.set_properties()
        self.gen_context()

    def get(self):
        if self.info_set is False:
            self._set_info({SC.MEDIA_TYPE: SC.MEDIA_TYPE_VIDEO})
        return self.item.getPath(), self.item, False

    def set_properties(self):
        self.item.setContentLookup(False)
        self.item.setProperty('IsPlayable', 'true')
        item_info = self.data.get(SC.ITEM_INFO, {})
        if 'duration' in item_info:
            duration = item_info.get('duration')
            resume_time = self.movie.get(self._key('watched'))
            if resume_time and 0 < resume_time < duration:
                self.item.setProperty('ResumeTime', '{}'.format(resume_time))
                self.item.setProperty('PercentPlayed', '{}'.format((resume_time / duration) * 100))

    def gen_context(self):
        menu = []

        if 'listType' in params.args:
            menu.append([Strings.txt(Strings.CONTEXT_REMOVE), 'RunPlugin({})'.format(create_plugin_url({
                SC.ACTION: SC.ACTION_REMOVE_FROM_LIST,
                SC.ITEM_ID: self.data.get(SC.ITEM_ID),
                SC.ITEM_PAGE: get_history_item_name(self.data.get('lid'))
            }))])

        if get_setting('download.path'):
            menu.append([Strings.txt(Strings.CONTEXT_DOWNLOAD), 'RunPlugin({})'.format(create_plugin_url({
                SC.ACTION: SC.ACTION_DOWNLOAD,
                SC.ACTION_DOWNLOAD: self.data.get(SC.ITEM_URL),
            }))])

        menu.append([Strings.txt(Strings.CONTEXT_SELECT_STREAM), 'PlayMedia({})'.format(create_plugin_url({
            SC.ACTION_SELECT_STREAM: '1',
            SC.ITEM_URL: self.data.get(SC.ITEM_URL),
        }))])

        if get_setting_as_bool('stream.autoselect'):
            mediatype = self.data.get(SC.ITEM_INFO, {}).get('mediatype')
            if mediatype == 'tvshow' or mediatype == 'movie':
                item_id = self.data.get(SC.ITEM_ID)
                st = preferred_lang_list
                if st.get(item_id) is not None:
                    menu.append((Strings.txt(Strings.CONTEXT_DEL_PREF_LANG).format(st[item_id]),
                                 'RunPlugin({})'.format(create_plugin_url({
                                     SC.ITEM_ACTION: SC.ACTION_DEL_PREFERRED_LANGUAGE,
                                     SC.ITEM_ID: self.data.get(SC.ITEM_ID)
                                 }))))
                else:
                    menu.append((Strings.txt(Strings.CONTEXT_ADD_PREF_LANG), 'RunPlugin({})'.format(create_plugin_url({
                        SC.ITEM_ACTION: SC.ACTION_SET_PREFERRED_LANGUAGE,
                        SC.ITEM_ID: self.data.get(SC.ITEM_ID)
                    }))))

        if self.data.get(SC.ITEM_INFO, {}).get('trailer'):
            menu.append(['Trailer', 'PlayMedia({})'.format(self.data.get(SC.ITEM_INFO, {}).get('trailer'))])

        self.item.addContextMenuItems(items=menu)

    def _key(self, name):
        nfo = self.data.get(SC.ITEM_INFO)
        if 'season' in nfo:
            return '{}:{}:{}'.format(name, nfo.get('season'), nfo.get('episode'))
        return name


class SCCmd(SCBaseItem):
    def __init__(self, data):
        data.update({SC.ACTION: SC.CMD})
        SCBaseItem.__init__(self, data)


class SCAction(SCBaseItem):
    def __init__(self, data):
        SCBaseItem.__init__(self, data)
        self.item.setPath(create_plugin_url(data))


class SCPlayItem(SCBaseItem):
    QUALITY_LIST = {
        'SD': 1,
        '720p': 2,
        '1080p': 3,
        '3D-SBS': 3,
        '4K': 4,
        '8K': 5
    }

    def __init__(self, data, resolve=True):
        self.input = data
        self.streams = []
        self.selected = None
        self.params = params.args
        self.hls = '#EXTM3U\n'
        item_info = self.input.get(SC.ITEM_INFO)
        item_info.update({'play': True})

        SCBaseItem.__init__(self, item_info, debug=True)
        if resolve:
            self.resolve()

    @try_catch('get')
    def get(self):
        return self.item.getPath(), self.item, True, self.selected

    @try_catch('build_hls')
    def build_hls(self):
        kr = Kraska()
        for pos, s in enumerate(self.streams):
            ident = s.get('xxx')
            debug('STREAM: {} => {}'.format(ident, s))
            url = kr.resolve(ident)
            sinfo = s.get('stream_info', {}).get('video', {})
            self.hls += '\n#EXT-X-STREAM-INF:BANDWIDTH={},RESOLUTION={}x{}'.format(s.get('bitrate'),
                                                                                   sinfo.get('width', 0),
                                                                                   sinfo.get('height', 0))
            self.hls += '\n{}\n'.format(url)
        debug('HLS: {}'.format(self.hls))
        filename = make_legal_filename('special://profile/input.m3u8')
        fs = xbmcvfs.File(filename, 'w')
        fs.write(self.hls)
        fs.close()

    @try_catch('speedtest')
    def speedtest(self, isp, ident='15VFNFJrCKHn'):
        kr = Kraska()
        url = kr.resolve(ident)
        smin = 999999999
        smax = 0
        durmin = 999999999
        hosts = ['b01', 's01', 'v01', 't01']
        for h in hosts:
            u = re.sub(r':\/\/([^.]+)', '://{}'.format(h), url)
            debug('speedtest URL {}'.format(u))
            s, dur = self.calculate_speed(u)
            debug('speedtest host {} speed: {}'.format(h, convert_bitrate(s)))
            smin = min(s, smin)
            smax = max(s, smax)
            durmin = min(dur, durmin)
            isp.update({h: s})
        debug('min/max {}/{}'.format(convert_bitrate(smin), convert_bitrate(smax)))
        debug('res: {}'.format(isp))
        try:
            st = Sc.post('/Stats/speedtest', json=isp)
            debug('Speed stats: {}'.format(st))
        except:
            pass
        speed = smin
        settings.set_setting('stream.adv.speedtest', speed)
        settings.set_setting('stream.adv.speedtest.asn', isp.get('a', 'N/A'))
        settings.set_setting('stream.adv.speedtest.last', int(time.time()))
        return (smin, smax, durmin)

    @try_catch('calculate_speed')
    def calculate_speed(self, url):
        from resources.lib.system import Http
        r = Http.get(url, stream=True)
        total_length = int(r.headers.get('content-length', 0))
        chunk = 4 * 1024 * 1024
        start = microtime()
        for _ in r.iter_content(chunk):
            debug('.')
            pass
        end = microtime()
        dur = (end - start) / 1000
        speed = int(total_length / dur * 8)
        return (speed, dur)  # bps

    @try_catch('ISP')
    def isp(self):
        return get_isp()

    @try_catch('filter')
    def filter(self):
        speedtest_last = get_setting_as_int('stream.adv.speedtest.last')
        now = time.time()
        force = True if speedtest_last is None or (speedtest_last + (24 * 3600 * 2)) < now else False

        isp = self.isp()
        asn = settings.get_setting('stream.adv.speedtest.asn')
        asn_changed = str(isp.get('a')) != str(asn)
        wrong_speed = settings.get_setting_as_int('stream.adv.speedtest') < 1
        debug('Force: {} ASN: {} / {} [{}] / SPEED: {} [{}]'.format(force, asn, isp.get('a'), asn_changed,
                                                                    settings.get_setting_as_int('stream.adv.speedtest'),
                                                                    wrong_speed))
        if force is True or (get_setting_as_int('stream.max.bitrate') == 100 and (asn_changed or wrong_speed)):
            smin, smax, dur = self.speedtest(isp)
            debug('smin {} / smax {} / dur {}'.format(smin, smax, dur))

        # @todo autoselect / filtrovanie nechcenych streamov
        if not get_setting_as_bool('stream.autoselect') \
                or SC.ACTION_SELECT_STREAM in self.params or SC.ACTION_DOWNLOAD in self.params:
            debug('nieje autoselect, alebo je vynuteny vyber streamu alebo download')
            return

        if get_setting_as_bool('stream.autoselect'):

            lang1 = get_setting('stream.lang1').lower()
            lang2 = get_setting('stream.lang2').lower()
            if Sc.parental_control_is_active():
                lang1 = get_setting('parental.control.lang1').lower()
                lang2 = get_setting('parental.control.lang2').lower()

            score = {pos: 0 for pos, s in enumerate(self.streams)}
            for pos, s in enumerate(self.streams):
                debug('-----------------------------------------------------------------------------------------------')
                debug('stream: bitrate: {} quality: {} lang: {}'.format(s.get('bitrate', 0), s.get('quality', 'N/A'),
                                                                        s.get('linfo', 'N/A')))
                self.video_score(score, pos, s)

                stream_info = s.get('stream_info', {})
                linfo = s.get('linfo', [])
                if lang1 in linfo:
                    score = self.audio_score(lang1, pos, score, stream_info, 3)
                elif lang2 in linfo:
                    score = self.audio_score(lang2, pos, score, stream_info, 1)
                else:
                    debug('Nemame primarny, ani sekundarny jazyk')

                debug('-----------------------------------------------------------------------------------------------')
                debug('final score: {}'.format(score[pos]))

            score = {k: v for k, v in sorted(score.items(), key=lambda item: item[1], reverse=True)}
            sel = list(score.keys())[0]
            debug('score: {} / {}'.format(score, sel))
            self.selected = self.streams[sel]
            self.streams = [self.selected]
            return

        debug('autoselect nic nevybral, tak nechame usera vybrat')

    def video_score(self, score, pos, s):
        megabit = 1e6
        speed = settings.get_setting_as_int('stream.adv.speedtest')
        if speed > 0:
            debug('set max_bitrate from speedtest: {}Mbps'.format(int(speed * 0.8 / megabit)))
            max_bitrate = int(speed * 0.8)
        else:
            max_bitrate = get_setting_as_int('stream.max.bitrate') * megabit
        debug('video max_bitrate: {}'.format(max_bitrate))

        quality = s.get('quality', 'SD')
        max_quality = get_setting('stream.max.quality')
        debug('qualita {} vs {} | {} >= {}'.format(quality, max_quality, self.QUALITY_LIST[max_quality],
                                                   self.QUALITY_LIST[quality]))
        if quality in self.QUALITY_LIST:
            if max_quality == '-':
                score[pos] += self.QUALITY_LIST[quality]
                debug('quality point 1: {} / {}'.format(self.QUALITY_LIST[quality], score[pos]))
            elif self.QUALITY_LIST[max_quality] >= self.QUALITY_LIST[quality]:
                w = self.QUALITY_LIST[max_quality] - (self.QUALITY_LIST[max_quality] - self.QUALITY_LIST[quality] - 1)
                score[pos] += w
                debug('quality point 2: {} / {}'.format(w, score[pos]))
            else:
                debug('nehodnotime rozlisenie 1')
        else:
            debug('nehodnotime rozlisenie 2')

        bitrate = int(s.get('bitrate', 0))
        if max_bitrate >= 100 * megabit:
            score[pos] += 1
            debug('vsetky bitrate su dobre, bitrate {} / {}'.format(bitrate, score[pos]))
        elif bitrate < max_bitrate:
            score[pos] += 1
            debug('nizsi bitrate {} < {} / {}'.format(bitrate, max_bitrate, score[pos]))
        else:
            score[pos] -= 10
            debug('prilis velky bitrate {} > {} / {}'.format(bitrate, max_bitrate, score[pos]))

        stream_info = s.get('stream_info', {})
        video = stream_info.get('video', {})
        vcodec = video.get('codec')

        if get_setting_as_bool('stream.adv'):
            if vcodec in get_setting('stream.adv.blacklist.codec'):
                score[pos] -= 10
                debug('blacklist codec {} / {}'.format(vcodec, score[pos]))

            if vcodec in get_setting('stream.adv.whitelist.codec'):
                score[pos] += 1
                debug('whitelist codec {} / {}'.format(vcodec, score[pos]))

            if get_setting_as_bool('stream.adv.exclude.3d') and '3D' in quality:
                score[pos] -= 10
                debug('penalize 3D content {}'.format(score[pos]))

            if get_setting_as_bool('stream.adv.exclude.hdr') and stream_info.get('HDR'):
                score[pos] -= 10
                debug('penalize HDR content {}'.format(score[pos]))

            if get_setting_as_bool('stream.adv.prefer.hdr') and stream_info.get('HDR'):
                score[pos] += 1
                debug('prefer HDR {}'.format(score[pos]))

        return score

    def audio_score(self, lang1, pos, score, stream_info, weight=3):
        if get_setting_as_bool('stream.adv') and 'streams' in stream_info:
            force_lang = preferred_lang_list.get(self.data.get('id'))
            ascore = {apos: 0 for apos, _ in enumerate(stream_info['streams'])}
            for apos, _ in enumerate(stream_info['streams']):
                acodec, channels, lang = _
                lang = lang.lower()

                if force_lang is not None and force_lang.lower() == lang:
                    ascore[apos] += 1000
                    debug('FORCE lang: {}'.format(force_lang.lower()))

                debug(' - lang {}/{}'.format(lang, lang1))
                if acodec in get_setting('stream.adv.whitelist.codec'):
                    debug(' - audio whitelist acodec {}'.format(acodec))
                    ascore[apos] += 1

                if acodec in get_setting('stream.adv.blacklist.codec'):
                    debug(' - audio blacklist acodec {}'.format(acodec))
                    ascore[apos] -= 10

                if lang == lang1:
                    if get_setting_as_bool('stream.adv.audio.channels'):
                        weight = weight + (channels - 3) if 3 > channels > weight else weight
                    debug(' - audio adv prefered lang {} => {}'.format(lang1, weight))
                    ascore[apos] += weight
            ascore = {k: v for k, v in sorted(ascore.items(), key=lambda item: item[1], reverse=True)}
            sel = list(ascore.keys())[0]
            score[pos] += ascore[sel]
            debug('audio score: {} -> {} / {}'.format(ascore, sel, score[pos]))
        else:
            score[pos] += weight
            debug('audio basic prefered lang {} => {} / {}'.format(lang1, weight, score[pos]))

        return score

    def resolve(self):
        data = self.data
        del (data[SC.ITEM_URL])
        self.streams = self.input.get(SC.ITEM_STRMS)
        self.filter()

        items = []
        matrix = []
        for s in self.streams:
            debug('ideme vytvorit listItems zo streamov')
            s.update(data)
            itm = SCStreamSelect(s)
            x = itm.get()
            title_items = [
                '[B]{}[/B] - '.format(s.get(SC.ITEM_LANG)),
                '[B]{}[/B] '.format(s.get(SC.ITEM_QUALITY)),
                '{} '.format(s.get(SC.ITEM_SIZE)),
                '{}{}'.format(s.get(SC.ITEM_VIDEO_INFO), s.get(SC.ITEM_AUDIO_INFO)),
            ]
            matrix.append(title_items)
            items.append(x[1])
        # matrix = make_table(matrix)
        # info('matrix: {}'.format(matrix))
        for i, itm in enumerate(items):
            itm.setProperty('old_title', itm.getLabel())
            itm.setLabel(' '.join(matrix[i]))

        if len(items) > 1 or SC.ACTION_SELECT_STREAM in self.params or SC.ACTION_DOWNLOAD in self.params:
            pos = dselect(items, heading=items[0].getProperty('old_title'), use_details=True)
            # info('post: {} | {}'.format(pos, json.dumps(self.data)))
            if pos is False or pos == -1:
                raise BaseException
            res = items[pos]
            self.selected = self.streams[pos]
        elif len(items) == 1:
            res = items[0]
            self.selected = self.streams[0] if self.selected is None else self.selected
        else:
            raise BaseException

        url = res.getPath()
        # info('vybrany stream: {} / {}'.format(res.getPath(), self.selected))
        if res.getProperty(SC.ITEM_PROVIDER) == SC.PROVIDER:
            resp = Sc.get(res.getPath())
            kr = Kraska()
            try:
                ident = resp.get(SC.ITEM_IDENT)
                debug('ideme resolvovat ident {} na kra.sk'.format(ident))
                url = kr.resolve(ident)
            except ResolveException as e:
                dok(Strings.txt(Strings.RESOLVE_ERROR_H1), Strings.txt(Strings.RESOLVE_ERROR_L1))
                raise BaseException
            except:
                raise BaseException
            if res.getProperty(SC.ITEM_SUBS):
                debug('subor ma titulky, tak ich natahujem')
                part = res.getProperty(SC.ITEM_SUBS).split('/file/')
                self.item.setSubtitles([kr.resolve(part[1])])
            else:
                info('nemame titulky')

        info('resolve: {}'.format(url))
        if 'lid' in data:
            lid = 'p-{}'.format(data.get('lid')) if parental_history() else data.get('lid')
            st = List(lid, max_items=20)
            st.add(res.getProperty(SC.ITEM_ID))
        self.item.setPath(url)
        self.item.setLabel(res.getProperty('original_title'))
        # home_win.setProperty('SC-lite-item', '{}'.format(res.getProperty(SC.ITEM_ID)))
        home_win.setProperty(SC.SELECTED_ITEM, '{}'.format(dumps(self.selected)))

        if 'unique_ids' in self.input.get(SC.ITEM_INFO):
            unique_ids = self.input.get(SC.ITEM_INFO).get('unique_ids')
            home_win.setProperty('script.trakt.ids', '{}'.format(dumps(unique_ids)))
            home_win.setProperty('{}.ids'.format(ADDON_ID), '{}'.format(dumps(unique_ids)))


class SCUpNext:
    def __init__(self, data):
        self.data = data
        self.out = {}
        self.play_item = SCPlayItem(data, resolve=False)
        self.build()

    def build_cur(self):
        tvshowid = self.data.get('info', {}).get('id')
        return dict(
            episodeid='{}-{}-{}'.format(tvshowid, get_info_label('VideoPlayer.Season'), get_info_label('VideoPlayer'
                                                                                                       '.Episode')),
            tvshowid=tvshowid,
            title=get_info_label('Player.Title'),
            art={
                'tvshow.fanart': get_info_label('ListItem.Art(tvshow.fanart)'),
                'tvshow.poster': get_info_label('ListItem.Art(tvshow.poster)'),
            },
            season=get_info_label('VideoPlayer.Season'),
            episode=get_info_label('VideoPlayer.Episode'),
            showtitle=get_info_label('VideoPlayer.TVShowTitle'),
            plot=get_info_label('VideoPlayer.Plot'),
            playcount=0,
            rating=0,
            firstaired='',
        )

    def build(self):
        item = self.play_item.item
        tvshowid = self.data.get('info', {}).get('id')
        next_episode = dict(
            episodeid='{}-{}-{}'.format(tvshowid, item.getProperty('season'), item.getProperty('episode')),
            tvshowid=tvshowid,
            title=item.getLabel(),
            art={
                'thumb': item.getArt('thumb'),
                'tvshow.clearart': item.getArt('clearart'),
                'tvshow.clearlogo': item.getArt('clearlogo'),
                'tvshow.fanart': item.getArt('fanart'),
                'tvshow.poster': item.getArt('poster'),
            },
            season=item.getProperty('season'),
            episode=item.getProperty('episode'),
            showtitle=item.getProperty('showtitle'),
            plot=item.getProperty('plot'),
            playcount=0,
            rating=0,
            firstaired='',
            # runtime=''
        )
        play_info = {
            SC.ITEM_URL: '{}'.format(self.data.get('info', {}).get(SC.ITEM_URL))
        }
        self.out = dict(
            current_episode=self.build_cur(),
            next_episode=next_episode,
            # play_url=item.getPath()
            play_info=play_info
        )
        selected_item = home_win.getProperty(SC.SELECTED_ITEM)
        debug('selected_item: {}'.format(selected_item))
        if selected_item:
            selected_item = loads(selected_item)

            debug('CURRENT: {}'.format(selected_item))

            notifications = selected_item.get(SC.NOTIFICATIONS, {})
            if SC.SKIP_END_TITLES in notifications and notifications.get(SC.SKIP_END_TITLES) is not None:
                self.out.update({'notification_offset': notifications.get(SC.SKIP_END_TITLES, None)})
        debug('next_info: {}'.format(self.out))
        pass

    def get(self):
        return self.out
