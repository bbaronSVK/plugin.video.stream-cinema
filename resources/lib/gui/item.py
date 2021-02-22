from json import dumps

from xbmcgui import ListItem

from resources.lib.api.kraska import Kraska, ResolveException
from resources.lib.api.sc import Sc
from resources.lib.common.lists import List, SCKODIItem
from resources.lib.common.logger import info, debug
from resources.lib.constants import ADDON_ID, SC, GUI
from resources.lib.debug import try_catch
from resources.lib.gui import get_cond_visibility as gcv, home_win
from resources.lib.gui.dialog import dselect, dok
from resources.lib.kodiutils import create_plugin_url, convert_bitrate, get_setting_as_bool, get_setting_as_int, \
    get_setting
from resources.lib.language import translate as _t, Strings
from resources.lib.params import params
from resources.lib.system import SYSTEM_LANG_CODE

list_item = ListItem


def parental_history():
    return get_setting_as_bool('parental.control.enabled')  # and get_setting_as_bool('parental.control.history')


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
        elif item_type == SC.ITEM_CMD:
            self.item = SCCmd(data)
        elif item_type == SC.ITEM_ACTION:
            self.item = SCAction(data)
        elif item_type == SC.ITEM_NEXT:
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
    def __init__(self, data):
        self.item = list_item()
        self.data = data
        self.info_set = False

        if SC.ITEM_TITLE in data:
            self.item.setLabel(_t(data.get(SC.ITEM_TITLE)))

        if SC.ITEM_ART in data:
            self.set_art()
        elif SC.ITEM_I18N_ART in data:
            self.set_i18n_art()

        if SC.ITEM_INFO in data:
            self.set_info()
        elif SC.ITEM_I18N_INFO in data:
            self._set_info(self.i18n_info())

        if 'cast' in data:
            self.set_cast()

        if 'unique_ids' in data:
            self.set_unique_ids()

        if 'stream_info' in data:
            self.set_stream_info()

        if SC.ITEM_URL in data:
            url = create_plugin_url(data)
            self.item.setPath(url)

    @try_catch('set_stream_info')
    def set_stream_info(self):
        stream_info = self.data.get('stream_info')
        for k, v in enumerate(stream_info):
            self.item.addStreamInfo(v, stream_info.get(v)) if v in ['video', 'audio'] else ''

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
        try:
            if SC.ITEM_TITLE in item_info:
                title = _t(item_info.get(SC.ITEM_TITLE))
                self.item.setLabel(title)
                del (item_info[SC.ITEM_TITLE])

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
        # debug('jazyk {}'.format(lang))
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
        if 'bitrate' in data:
            label2 += '   bitrate: [B]{}[/B]'.format(convert_bitrate(int(data.get('bitrate'))))
        if 'linfo' in data:
            label2 += '   audio: [B][UPPERCASE]{}[/UPPERCASE][/B]'.format(', '.join(data['linfo']))
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


class SCDir(SCBaseItem):
    build_ctx = True

    def __init__(self, data):
        SCBaseItem.__init__(self, data)
        if SC.ITEM_URL in data:
            url = create_plugin_url(data)
            self.item.setPath(url)
        if self.build_ctx:
            self.make_ctx()

    def make_ctx(self):
        context_menu = []

        if params.args.get('url'):
            context_menu.append((Strings.txt(Strings.CONTEXT_PIN_UNPIN), 'RunPlugin({})'.format(create_plugin_url({
                SC.ITEM_ACTION: SC.ACTION_PIN,
                SC.ITEM_URL: params.args.get(SC.ITEM_URL),
                SC.ITEM_ID: self.data.get(SC.ITEM_URL)
            }))))

        if context_menu:
            debug('kontextove menu: {}'.format(context_menu))
            self.item.addContextMenuItems(context_menu)


class SCNext(SCDir):
    def __init__(self, data):
        self.build_ctx = False
        SCDir.__init__(data)
        info('Mame next polozku')
        self.item.setProperty('SpecialSort', GUI.BOTTOM)


class SCVideo(SCBaseItem):
    def __init__(self, data):
        trakt = data['unique_ids']['trakt'] if 'unique_ids' in data and 'trakt' in data['unique_ids'] else None
        self.movie = SCKODIItem(data.get(SC.ITEM_ID), series=data.get('info', {}).get('season'),
                                episode=data.get('info', {}).get('episode'), trakt=trakt)
        internal_info = {}
        play_count = self.movie.get_play_count()
        if play_count is not None and play_count > 0:
            internal_info.update({'playcount': play_count})
        last_played = self.movie.get_last_played()
        if last_played:
            internal_info.update({'lastplayed': last_played})
        if internal_info != {}:
            debug('update info: {}'.format(internal_info))
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
        info = self.data.get(SC.ITEM_INFO, {})
        if 'duration' in info:
            duration = info.get('duration')
            resume_time = self.movie.get(self._key('watched'))
            if resume_time and 0 < resume_time < duration:
                self.item.setProperty('ResumeTime', '{}'.format(resume_time))
                self.item.setProperty('PercentPlayed', '{}'.format((resume_time / duration) * 100))

    def gen_context(self):
        menu = [(Strings.txt(Strings.CONTEXT__SELECT_STREAM), 'PlayMedia({})'.format(create_plugin_url({
            SC.ACTION_SELECT_STREAM: '1',
            SC.ITEM_URL: self.data.get(SC.ITEM_URL),
        })))]

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
    def __init__(self, data, resolve=True):
        self.input = data
        self.streams = []
        self.selected = None
        self.params = params.args
        item_info = self.input.get(SC.ITEM_INFO)
        SCBaseItem.__init__(self, item_info)
        if resolve:
            self.resolve()

    @try_catch('get')
    def get(self):
        return self.item.getPath(), self.item, True, self.selected

    @try_catch('filter')
    def filter(self):
        # @todo autoselect / filtrovanie nechcenych streamov
        if not get_setting_as_bool('stream.autoselect') or SC.ACTION_SELECT_STREAM in self.params:
            debug('nieje autoselect, alebo je vynuteny vyber streamu')
            return

        if get_setting_as_bool('stream.autoselect'):
            megabit = 1000000
            max_bitrate = get_setting_as_int('stream.max.bitrate') * megabit
            lang1 = get_setting('stream.lang1').lower()
            lang2 = get_setting('stream.lang2').lower()
            if Sc.parental_control_is_active():
                lang1 = get_setting('parental.control.lang1').lower()
                lang2 = get_setting('parental.control.lang2').lower()

            for pos, s in enumerate(self.streams):
                # debug('stream: {}'.format(s))
                bitrate = int(s.get('bitrate', 0))
                if max_bitrate >= 100 * megabit:
                    debug('vsetky bitrate su dobre, bitrate {}'.format(bitrate))
                    add = True
                elif bitrate < max_bitrate:
                    debug('nizsi bitrate {} < {}'.format(bitrate, max_bitrate))
                    add = True
                else:
                    debug('velky bitrate {} > {}'.format(bitrate, max_bitrate))
                    add = False

                linfo = s.get('linfo', [])
                if add and not (lang1 in linfo or lang2 in linfo):
                    debug('Nemame {} ani {} v {}'.format(lang1, lang2, linfo))
                    add = False

                if add:
                    debug('vyberam stream {} / {}'.format(pos, s))
                    self.streams = [s]
                    self.selected = s
                    return
                else:
                    debug('NE prindavam stream {}'.format(s))

        debug('autoselect nic nevybral, tak nechame usera vybrat')

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

        if len(items) > 1:
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
        info('vybrany stream: {} / {}'.format(res.getPath(), self.selected))
        if res.getProperty(SC.ITEM_PROVIDER) == SC.PROVIDER:
            resp = Sc.get(res.getPath())
            kr = Kraska()
            try:
                ident = resp.get(SC.ITEM_IDENT)
                debug('ideme resolvovat iden {} na kra.sk'.format(ident))
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

    def build(self):
        item = self.play_item.item
        next = dict(
            # episodeid='',
            # tvshowid='',
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
            # playcount='',
            # rating='',
            # firstaired='',
            # runtime=''
        )
        self.out = dict(
            next_episode=next,
            play_url=item.getPath()
        )
        debug('next_info: {}'.format(self.out))
        pass

    def get(self):
        return self.out
