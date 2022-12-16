# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals

import traceback

import xbmcgui
import xbmcplugin
import xbmc
from json import dumps

from resources.lib.common.kodivideocache import set_kodi_cache_size
from resources.lib.debug import performance
from resources.lib.intro import intro
from resources.lib.kodiutils import params, container_refresh, urlencode, container_update, create_plugin_url, \
    exec_build_in, download, get_setting, update_addon, set_setting_as_bool, notify, get_setting_as_bool
from resources.lib.common.logger import info, debug
from resources.lib.common.lists import List, SCKODIItem
from resources.lib.constants import SORT_METHODS, SC, GUI, ADDON_ID
from resources.lib.api.sc import Sc
from resources.lib.gui import cur_win, home_win
from resources.lib.gui.dialog import dok, dinput, dselect
from resources.lib.gui.item import SCItem, get_history_item_name, list_hp, SCLDir, SCUpNext
from resources.lib.common.storage import Storage, KodiViewModeDb, preferred_lang_list
from resources.lib.language import Strings
from resources.lib.params import params
from resources.lib.services.next_episodes import NextEp
from resources.lib.system import SYSTEM_LANG_CODE


class Scinema:
    def __init__(self):
        self.args = params.args
        self.items_pinned = []
        self.items = []
        self.response = []
        self.succeeded = False
        self.update_listing = False
        self.cache_to_disc = False
        self.url = '/'
        self.payload = None
        self.storage = Storage('scinema')
        self.send_end = False
        self.listType = None

    def run(self):

        if SC.ITEM_URL in self.args:
            self.url = self.args.get(SC.ITEM_URL)

        if self.url == '/' and xbmc.Player().isPlayingVideo() and home_win.getProperty('{}.play'.format(ADDON_ID)):
            container_update('special://home', True)
            self.succeeded = False
            self.end_of_directory()
            return

        if SC.ITEM_URL in self.args and self.args.get(SC.ITEM_URL).startswith('http'):
            self.args.update({SC.ITEM_ACTION: SC.ACTION_PLAY_URL})

        info('Start: {} [{}]'.format(str(self.args), self.url))

        if 'title' in self.args:
            home_win.setProperty('SCTitle', self.args.get('title'))
        else:
            home_win.clearProperty('SCTitle')

        if SC.ACTION in self.args:
            exit_code = self.action()
            if exit_code is True:
                return
        elif 'play' in self.args:
            '''
            stara URL zo SC CS&SK pre play aby fungovala kniznica
            '''
            self.url = self.args.get('play')
            self.call_url_and_response()
        else:
            self.call_url_and_response()
        self.end()

    def action(self):
        action = self.args.get(SC.ITEM_ACTION)
        if action == SC.ACTION_PLAY_URL:
            self.play_url(self.args.get(SC.ITEM_URL))
            self.succeeded = True
        elif action == SC.ACTION_CMD:
            self.action_cmd()
        elif action == 'intro':
            intro(2, True)
        elif action == SC.ACTION_PIN:
            self.action_pin()
        elif action == SC.ACTION_CSEARCH:
            self.action_csearch()
        elif action == SC.ACTION_LAST:
            self.action_last()
        elif action == 'nextep':
            self.action_next_ep()
        elif action == 'update_nextep':
            self.action_update_next_ep()
            return True
        elif action == 'search_next_episodes':
            self.action_search_next_episodes()
        elif action == SC.ACTION_DEBUG:
            from resources.lib.kodiutils import check_set_debug

            check_set_debug(True)
        elif action == SC.ACTION_DOWNLOAD:
            self.url = self.args.get(SC.ITEM_DOWNLOAD)
            self.call_url_and_response()
        elif action == SC.ACTION_BUFFER:
            set_kodi_cache_size()
        elif action == SC.ACTION_ANDROID:
            self.action_android()
        elif action == SC.ACTION_ADD2HP:
            self.action_add2hp()
        elif action == SC.ACTION_DEL2HP:
            self.action_add2hp(True)
        elif action == SC.ACTION_ADD_CUSTOM_FILTER:
            self.action_add_custom_filter()
        elif action == SC.ACTION_DEL_CUSTOM_FILTER:
            self.action_add_custom_filter(True)
        elif action == SC.ACTION_REMOVE_FROM_LIST:
            self.action_remove_from_list()
        elif action == SC.ACTION_UPDATE_ADDON:
            update_addon()
        elif 'trakt.' in action:
            from resources.lib.trakt.Trakt import trakt
            trakt.action(action, self)
            return True
        elif action in ['add_to_library', 'add_to_library_sub']:
            lib = List(SC.ITEM_LIBRARY)
            lib.add(self.args.get(SC.ITEM_ID))
            if action == 'add_to_library_sub':
                sub = List(SC.ITEM_LIBRARY_SUB)
                sub.add(self.args.get(SC.ITEM_ID))
            container_refresh()
        elif action == 'remove_from_sub':
            lib = List(SC.ITEM_LIBRARY)
            lib.add(self.args.get(SC.ITEM_ID), True)
            if action == 'remove_from_sub':
                sub = List(SC.ITEM_LIBRARY_SUB)
                sub.add(self.args.get(SC.ITEM_ID), True)
            container_refresh()
        elif action == 'autocomplet':
            from resources.lib.services.autocomplete import Autocomplete
            Autocomplete(self.args)
            return True
        elif action == SC.ACTION_DEL_PREFERRED_LANGUAGE:
            del preferred_lang_list[self.args.get(SC.ITEM_ID)]
            container_refresh()
            return
        elif action == SC.ACTION_SET_PREFERRED_LANGUAGE:
            lang_list = Sc.get('/Lang/{}'.format(self.args.get(SC.ITEM_ID)))
            debug('parametre: {} / langs: {}'.format(self.args, lang_list))
            ret = dselect(lang_list, Strings.txt(Strings.CONTEXT_ADD_PREF_LANG))
            if ret > -1:
                st = preferred_lang_list
                st[self.args.get(SC.ITEM_ID)] = lang_list[ret]
                debug('znovelene: {} / {}'.format(ret, st[self.args.get(SC.ITEM_ID)]))
                container_refresh()
            return
        else:
            info('Neznama akcia: {}'.format(action))
        return False

    def action_remove_from_list(self):
        st = List(self.args[SC.ITEM_PAGE])
        st.add(self.args[SC.ITEM_ID], True)
        container_refresh()
        pass

    def action_android(self):
        st = List('android')
        st.add(self.args)

    def action_add2hp(self, remove=False):
        st = list_hp
        del self.args[SC.ACTION]
        if remove is False:
            label = dinput('Zadaj vlastny nazov', self.args[SC.ITEM_ID])
            if label == '':
                label = self.args[SC.ITEM_ID]
            self.args[SC.ITEM_ID] = label

        st.add(self.args, remove_only=remove)
        if remove is True:
            container_refresh()

    def action_add_custom_filter(self, remove=False):
        if SC.ITEM_PAGE in self.args:
            st = List(SC.TXT_CUSTOM_FORMAT.format(self.args[SC.ITEM_PAGE]))
        else:
            st = List(SC.TXT_CUSTOM_FORMAT.format(self.url))

        cfg = {
            SC.ITEM_URL: '',
            SC.ITEM_TITLE: '',
        }
        if remove is False:
            label = dinput('Zadaj nazov polozky')
            if label == '':
                label = self.args[SC.ITEM_ID]
            cfg[SC.ITEM_TITLE] = label

            url = dinput('Zadaj url pre [B]plugin[/B] z https://stream-cinema.online/filter', '')
            if url == '':
                return False
            cfg[SC.ITEM_URL] = url
        else:
            cfg.update({
                SC.ITEM_URL: self.args[SC.ITEM_URL],
                SC.ITEM_TITLE: self.args[SC.ITEM_TITLE],
            })

        st.add(cfg, remove_only=remove)
        if remove is True:
            container_refresh()

    def action_last(self):
        lid = get_history_item_name(self.args.get(SC.ITEM_ID))
        st = List(lid)
        if len(st.get()) > 0:
            self.url = '/Last'
            self.payload = {"ids": dumps(st.get())}
            self.call_url_and_response()
        else:
            if SC.ITEM_WIDGET not in self.args:
                dok(Strings.txt(Strings.EMPTY_HISTORY_H1), Strings.txt(Strings.EMPTY_HISTORY_L1))

    def action_next_ep(self):
        st = NextEp().get()
        if len(st) > 0:
            self.url = '/Last?nextep=1'
            self.payload = dict(ids=dumps(st))
            self.call_url_and_response()
        else:
            pass

    def action_update_next_ep(self):
        st = NextEp()
        st.update_items()

    def action_cmd(self):
        url = self.args.get('url')
        if url.startswith('cmd://'):
            cmd = url[6:]
            info('CMD: {}'.format(cmd))
            exec_build_in(cmd)
            self.send_end = True
            # self.succeeded = True
            # self.end_of_directory()

    def action_force_select_stream(self):
        pass

    def action_pin(self):
        pinned = self.get_pinned()
        if pinned and self.args.get(SC.ITEM_ID) in pinned:
            info('remove')
            del pinned[self.args.get(SC.ITEM_ID)]
        else:
            info('add')
            pinned.update({self.args.get(SC.ITEM_ID): True})
        self.set_pinned(pinned)
        container_refresh()

    def action_csearch(self):
        self.succeeded = True
        self.end_of_directory()
        _id = self.args.get(SC.ITEM_ID)
        home_win.setProperty('SC.search', '{}'.format(_id))
        search = dinput('', '', xbmcgui.INPUT_TYPE_TEXT)
        home_win.clearProperty('SC.search')
        info('search string: {}'.format(search))
        if search == '':
            exec_build_in('Action(Back)')
            return
        query = {'search': search, SC.ITEM_ID: _id}
        if _id.startswith('search-people'):
            query.update({'ms': '1'})
        st = List(_id)
        st.add(search)
        debug('SEARCH: _ID "{}" search for "{}" people "{}"'.format(_id, search, 1 if 'ms' in query else 0))
        url = '/Search/{}?{}'.format(_id, urlencode(query))
        info('search url: {}'.format(url))
        self.url = url
        self.call_url()
        if 'msgERROR' in self.response.get('system', {}):
            self.msg_error()
            exec_build_in('Action(Back)')
            return
        plugin_url = create_plugin_url({'url': url})
        container_update(plugin_url)
        return

    def action_search_next_episodes(self):
        NextEp().run(True)

    def msg_error(self):
        if SC.ITEM_WIDGET in self.args:
            debug('Mame error hlasku, ale sme z widgetu, tak ju nezobrazujeme')
            return

        if 'msgERROR' in self.response.get('system', {}):
            debug('ERR REPOSNSE: {}'.format(self.response))
            data = self.response.get('system').get('msgERROR')
            if isinstance(data, dict):
                lang = SYSTEM_LANG_CODE
                i18n = data.get('i18n', {})
                if lang not in i18n:
                    debug('err pre jazyk {} nemame, tak nastavujem cs'.format(lang))
                    lang = SC.DEFAULT_LANG
                dok(Strings.txt(Strings.SYSTEM_H1), '{}'.format(data['i18n'][lang]))
                pass
            else:
                dok(Strings.txt(Strings.SYSTEM_H1), '{}'.format(data))
        else:
            debug('ERROR response: {}'.format(self.response))
            dok(Strings.txt(Strings.SYSTEM_H1), Strings.txt(Strings.SYSTEM_API_ERROR_L1))

    def pinned_key(self):
        return SC.TXT_PINNED.format(self.url)

    def get_pinned(self):
        pinned = self.storage.get(self.pinned_key())
        if not pinned:
            pinned = {}
        return pinned

    def set_pinned(self, data):
        info('new pined {} for {}'.format(data, self.pinned_key()))
        self.storage[self.pinned_key()] = data

    def call_url_and_response(self):
        self.call_url()
        self.parse_response()

    def call_url(self):
        try:
            if self.payload is not None:
                debug('POST DATA: {}'.format(self.payload))
                self.response = Sc.post(self.url, data=self.payload)
            else:
                self.response = Sc.get(self.url)
        except:
            debug('CALL URL ERR: {}'.format(traceback.format_exc()))
            self.response = {}

    def parse_response(self):
        if SC.ITEM_SYSTEM in self.response:
            self.system()

        if SC.ITEM_MENU in self.response:
            self.list()
        elif SC.ITEM_STRMS in self.response:
            return self.play()
        else:
            self.msg_error()

    def pinned_hp(self):
        st = list_hp
        for itm in st.get():
            info('HP item: {}'.format(itm))
            item = SCItem({'type': SC.ITEM_HPDIR, 'title': itm.get(SC.ITEM_ID), 'url': itm.get(SC.ITEM_URL)})
            if item.visible:
                info('Pridavam item na HP: {}'.format(itm.get(SC.ITEM_ID)))
                item.li().setProperty('SpecialSort', GUI.TOP)
                self.items_pinned.append(item.get())

    def pinned_custom(self):
        st = List(SC.TXT_CUSTOM_FORMAT.format(self.url))
        for itm in st.get():
            debug('custom item: {}'.format(itm))
            cfg = {
                SC.ITEM_TYPE: SC.ITEM_CUSTOM_FILTER,
                SC.ITEM_TITLE: itm.get(SC.ITEM_TITLE),
                SC.ITEM_URL: itm.get(SC.ITEM_URL),
                'self_url': self.url,
            }
            item = SCItem(cfg)
            if item.visible:
                item.li().setProperty('SpecialSort', GUI.TOP)
                self.items_pinned.append(item.get())

    def list(self):
        self.succeeded = True
        pinned = self.get_pinned()
        hidden = self.storage.get('h-{}'.format(self.url))
        self.pinned_custom()
        if self.url == '/':
            info('Mame HP, skontrolujeme pripnute polozky')
            self.pinned_hp()

        for i in self.response.get(SC.ITEM_MENU):
            item = SCItem(i)

            if item.visible:
                # info('pin {} {}'.format(pinned, i.get(SC.ITEM_URL)))
                if pinned is not None and i.get(SC.ITEM_URL) and pinned.get(i.get(SC.ITEM_URL)):
                    item.li().setProperty('SpecialSort', GUI.TOP)
                    info('TOP {}'.format(item.li().getProperty('SpecialSort')))
                    self.items_pinned.append(item.get())
                    item.visible = False

                if hidden is not None and hidden.get(item.li().getLabel()):
                    item.visible = False

            if item.visible:
                self.items.append(item.get())

    def play(self):
        try:
            item = SCItem(self.response)
            url, li, status, selected = item.get()
            if SC.ACTION in self.args and SC.ACTION_DOWNLOAD in self.args[SC.ACTION]:
                filename = selected.get('stream_info', {}).get('filename')
                if filename is None:
                    dok(Strings.txt(Strings.RESOLVE_ERROR_H1), Strings.txt(Strings.RESOLVE_ERROR_L1))
                    return
                from threading import Thread
                worker = Thread(target=download, args=(url, get_setting('download.path'), filename))
                worker.start()
                return
            debug('----------------------------------------------------------------------------------------------------')
            debug('play url: {}'.format(self.url))
            debug('play selected: {}'.format(dumps(selected)))
            # debug('play response: {}'.format(dumps(self.response)))
            # debug('play item: {}'.format(li))
            debug('----------------------------------------------------------------------------------------------------')
            self.response['strms'] = selected
            home_win.setProperty('SC.play_item', dumps(self.response))
            if params.handle == -1:
                debug('HANDLE -1')
                xbmc.Player().play(url, li)
            else:
                debug('HANDLE {}'.format(params.handle))
                self.succeeded = True
                self.cache_to_disc = False
                xbmcplugin.setResolvedUrl(params.handle, True, li)
                self.end_of_directory()
        except:
            # dok('ERROR', 'Chyba pri prehravani')
            info("ERR: {}".format(str(traceback.format_exc())))
            self.end_of_directory()

    def play_url(self, url, li=None):
        info('playUrl: {} / {}'.format(url, li))
        xbmc.Player().play(url, listitem=li)

    def end_of_directory(self):
        if self.send_end:
            return
        self.send_end = True

        info('endOfDirectory s: {} u: {} c: {}'.format(self.succeeded, self.update_listing, self.cache_to_disc))
        xbmcplugin.endOfDirectory(params.handle, succeeded=self.succeeded, updateListing=self.update_listing,
                                  cacheToDisc=self.cache_to_disc)

    def end(self):
        if self.send_end:
            return

        if not self.items:
            self.succeeded = False
            # dok('ERROR', 'Nastala chyba...')

        if len(self.items_pinned) > 0:
            xbmcplugin.addDirectoryItems(params.handle, self.items_pinned)
        if len(self.items) > 0:
            xbmcplugin.addDirectoryItems(params.handle, self.items)
        self.end_of_directory()
        if SC.ITEM_SYSTEM in self.response:
            self.system_after()

    def notify(self, filter):
        return
        try:
            plugin_url = 'plugin://{}/{}'.format(ADDON_ID, params.orig_args if params.orig_args else '')
            kv = KodiViewModeDb()
            sort = kv.get_sort(plugin_url)
            if sort is not None:
                j = dumps({'m': sort[0], 'o': sort[1], 'u': plugin_url, 'f': filter}).encode()
            else:
                j = dumps({'m': 0, 'o': 1, 'u': plugin_url, 'f': filter}).encode()
            from base64 import b64encode
            data = b64encode(j).decode()
            notify(sender=ADDON_ID, message='List.Sort', data=data)
        except:
            debug('notify List.Sort ERR: {}'.format(traceback.format_exc()))
            pass

    def system(self):
        # if 'filter' in self.response:
        #     self.notify(self.response.get('filter', {}))
        # else:
        #     self.notify({})

        data = self.response.get(SC.ITEM_SYSTEM, {})
        if 'setContent' in data:
            xbmcplugin.setContent(params.handle, data['setContent'])

        if 'setPluginCategory' in data:
            xbmcplugin.setPluginCategory(params.handle, data['setPluginCategory'])

        if 'addSortMethod' in data:
            # info('add sort method {}'.format(SORT_METHODS[data['addSortMethod']]))
            xbmcplugin.addSortMethod(params.handle, SORT_METHODS[data['addSortMethod']])

        if 'addSortMethods' in data:
            for method in data['addSortMethods']:
                # info('add sort method {}'.format(SORT_METHODS[method]))
                try:
                    if method in SORT_METHODS:
                        xbmcplugin.addSortMethod(params.handle, SORT_METHODS[method])
                except:
                    pass

        if 'SetSortMethod' in data:
            #method = SORT_METHODS[int(data.get('SetSortMethod'))]
            # info('set sort method {}'.format(method))
            #xbmc.executebuiltin('Container.SetSortMethod(%d)' % method)
            pass

        if 'setPluginFanart' in data:
            tmp = data.get('setPluginFanart')
            image = tmp.get('image', None)
            color1 = tmp.get('color1', None)
            xbmcplugin.setPluginFanart(params.handle, image=image, color1=color1)

        if 'addCustomFilter' in data:
            item = SCItem({
                'type': 'add_custom_filter',
                'title': '[B]+[/B]   ADD',
                SC.ITEM_ACTION: SC.ACTION_ADD_CUSTOM_FILTER
            })
            item.li().setProperty('SpecialSort', GUI.BOTTOM)
            self.items.append(item.get())

        if 'listType' in data:
            params.args.update({'listType': data['listType']})
            self.listType = data['listType']

    def system_after(self):
        data = self.response.get(SC.ITEM_SYSTEM, {})
        if 'setContent' in data:  # and settings.get_setting_bool('gui.views.enabled'):
            xbmcplugin.setContent(params.handle, data['setContent'])
            # view_mode = data["setContent"].lower()
            # view_code = settings.get_setting_int('gui.views.{0}'.format(view_mode))
            # if view_code > 0:
            #     xbmc.executebuiltin("Container.SetViewMode(%d)" % view_code)

        if 'SetSortMethod' in data:
            #method = SORT_METHODS[int(data.get('SetSortMethod'))]
            #xbmc.executebuiltin('Container.SetSortMethod(%d)' % method)
            pass

        if SC.ITEM_FOCUS in data:
            try:
                control = cur_win.getControl(cur_win.getFocusId())
                control.selectItem(int(data[SC.ITEM_FOCUS]))
            except:
                pass

        check_last_key = '{}.last_series'.format(ADDON_ID)
        if 'checkLast' in data and get_setting_as_bool('stream.autoplay.episode'):
            check_last = data['checkLast']
            stop = home_win.getProperty('{}.stop'.format(ADDON_ID))
            debug('Mame check last data: {} / {}'.format(stop, check_last))
            item_id = int(check_last.get('id', 0))
            ki = SCKODIItem(int(item_id))
            last_ep = ki.get_last_ep()
            if item_id > 0 and last_ep:
                win_last_series = home_win.getProperty(check_last_key)
                home_win.setProperty(check_last_key, str(item_id))
                debug('last {} cur {}'.format(win_last_series, item_id))
                if win_last_series == '' or win_last_series != str(item_id):
                    debug('last ep: {}'.format(last_ep))
                    try:
                        data = Sc.up_next(item_id, last_ep[0], last_ep[1])
                        d = SCUpNext(data)
                        debug('NEXT EP: {}'.format(d.get().get('play_info')))
                        cmd = 'PlayMedia({})'.format(create_plugin_url(d.get().get('play_info')))
                        if stop is None or stop == '':
                            debug('play: {}'.format(cmd))
                            exec_build_in(cmd)
                    except:
                        debug('chyba: {}'.format(traceback.format_exc()))
                        pass
        else:
            home_win.clearProperty(check_last_key)
        # upraceme po sebe
        home_win.clearProperty('{}.stop'.format(ADDON_ID))


class Stream:
    def __init__(self, data, parent=None):
        self.data = data
        self.parent = parent

    def select_stream(self):
        strms = self.data.get('strms')
        return strms.get(0)

    def run(self):
        file = self.select_stream()
        info('Vybrany stream: {}'.format(file))
        item = SCItem(self.data)
        # xbmcplugin.setResolvedUrl(params.handle, True, item)
        pass


class Resolve:
    def __init__(self, data):
        self.data = data
