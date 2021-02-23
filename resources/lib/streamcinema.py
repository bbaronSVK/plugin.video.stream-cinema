# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals

import traceback

import xbmcplugin
import xbmc
from json import dumps

from resources.lib.kodiutils import params, container_refresh, urlencode, container_update, create_plugin_url, \
    exec_build_in, download, get_setting
from resources.lib.common.logger import info, debug
from resources.lib.common.lists import List
from resources.lib.constants import SORT_METHODS, SC, GUI
from resources.lib.api.sc import Sc
from resources.lib.gui import cur_win, home_win
from resources.lib.gui.dialog import dok, dinput
from resources.lib.gui.item import SCItem, parental_history
from resources.lib.common.storage import Storage
from resources.lib.language import Strings
from resources.lib.params import params
from resources.lib.services.service import check_set_debug
from resources.lib.system import SYSTEM_LANG_CODE


class scinema:
    def __init__(self):
        self.args = params.args
        self.items_pinned = []
        self.items = []
        self.response = []
        self.succeeded = False
        self.update_listing = False
        self.cache_to_disc = False
        self.url = '/'
        self.storage = Storage('scinema')
        self.send_end = False

    def run(self):
        if SC.ITEM_URL in self.args:
            self.url = self.args.get(SC.ITEM_URL)

        if SC.ITEM_URL in self.args and self.args.get(SC.ITEM_URL).startswith('http'):
            self.args.update({SC.ITEM_ACTION: SC.ACTION_PLAY_URL})

        info('Start: {} [{}]'.format(str(self.args), self.url))

        if 'title' in self.args:
            home_win.setProperty('SCTitle', self.args.get('title'))
        else:
            home_win.clearProperty('SCTitle')

        if SC.ACTION in self.args:
            self.action()
        elif 'play' in self.args:
            '''
            stara URL zo SC CS&SK pre play aby fungovala kniznica
            '''
            self.url = self.args.get('play')
            self.call_url()
        else:
            self.call_url()
        self.end()

    def action(self):
        # @todo tu treba spravit "akcie"
        action = self.args.get(SC.ITEM_ACTION)
        if action == SC.ACTION_PLAY_URL:
            self.play_url(self.args.get('url'))
            self.succeeded = True
        elif action == SC.ACTION_CMD:
            self.action_cmd()
        elif action == SC.ACTION_PIN:
            self.action_pin()
        elif action == SC.ACTION_CSEARCH:
            self.action_csearch()
        elif action == SC.ACTION_LAST:
            self.action_last()
        elif action == SC.ACTION_DEBUG:
            check_set_debug(True)
        elif action == 'down':
            debug('download {}'.format(self.args))
            self.url = self.args.get('down')
            self.call_url()
        else:
            info('Neznama akcia: {}'.format(action))
        pass

    def action_last(self):
        lid = 'p-{}'.format(self.args.get(SC.ITEM_ID)) if parental_history() else self.args.get(SC.ITEM_ID)
        st = List(lid)
        if len(st.get()) > 1:
            self.url = '/Last?ids={}'.format(dumps(st.get()))
            self.call_url()
        else:
            dok(Strings.txt(Strings.EMPTY_HISTORY_H1), Strings.txt(Strings.EMPTY_HISTORY_L1))

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
        search = dinput('')
        info('search string: {}'.format(search))
        if search == '':
            self.succeeded = False
            self.end_of_directory()
            return
        _id = self.args.get(SC.ITEM_ID)
        query = {'search': search, SC.ITEM_ID: _id}
        if _id.startswith('search-people'):
            query.update({'ms': '1'})
        url = '/Search/{}?{}'.format(_id, urlencode(query))
        info('search url: {}'.format(url))
        plugin_url = create_plugin_url({'url': url})
        self.succeeded = True
        self.end_of_directory()
        container_update(plugin_url, True)
        return

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

    def call_url(self):
        try:
            self.response = Sc.get(self.url)
        except:
            self.response = {}
        if SC.ITEM_MENU in self.response:
            self.list()
        elif SC.ITEM_STRMS in self.response:
            return self.play()
        else:
            dok(Strings.txt(Strings.SYSTEM_H1), Strings.txt(Strings.SYSTEM_API_ERROR_L1))

    def list(self):
        self.succeeded = True
        pinned = self.get_pinned()
        hidden = self.storage.get('h-{}'.format(self.url))
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
                filename = self.response.get('info', {}).get('stream_info', {}).get('filename')
                if filename is None:
                    dok(Strings.txt(Strings.RESOLVE_ERROR_H1), 'Download error')
                    return
                from threading import Thread
                worker = Thread(target=download, args=(url, get_setting('download.path'), filename))
                worker.start()
                return
            self.response['strms'] = selected
            home_win.setProperty('SC.play_item', dumps(self.response))
            # info('play: {} {} {}'.format(url, li.getPath(), status))
            self.succeeded = True
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

        if SC.ITEM_SYSTEM in self.response:
            self.system()

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

    def system(self):
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
                xbmcplugin.addSortMethod(params.handle, SORT_METHODS[method])

        if 'SetSortMethod' in data:
            method = SORT_METHODS[int(data.get('SetSortMethod'))]
            # info('set sort method {}'.format(method))
            xbmc.executebuiltin('Container.SetSortMethod(%d)' % method)

        if 'setPluginFanart' in data:
            tmp = data.get('setPluginFanart')
            image = tmp.get('image', None)
            color1 = tmp.get('color1', None)
            xbmcplugin.setPluginFanart(params.handle, image=image, color1=color1)

        if 'msgERROR' in data:
            if 'i18n' in data.get('msgERROR'):
                lang = SYSTEM_LANG_CODE
                i18n = data.get('msgERROR', {}).get('i18n', {})
                if lang not in i18n:
                    debug('err pre jazyk {} nemame, tak nastavujem cs'.format(lang))
                    lang = SC.DEFAULT_LANG
                dok(Strings.txt(Strings.SYSTEM_H1), str(data.get('msgERROR', {}).get('i18n', {}).get(lang)))
                pass
            else:
                dok(Strings.txt(Strings.SYSTEM_H1), str(data.get('msgERROR')))

    def system_after(self):
        data = self.response.get(SC.ITEM_SYSTEM, {})
        if 'setContent' in data:  # and settings.get_setting_bool('gui.views.enabled'):
            xbmcplugin.setContent(params.handle, data['setContent'])
            # view_mode = data["setContent"].lower()
            # view_code = settings.get_setting_int('gui.views.{0}'.format(view_mode))
            # if view_code > 0:
            #     xbmc.executebuiltin("Container.SetViewMode(%d)" % view_code)

        if 'SetSortMethod' in data:
            method = SORT_METHODS[int(data.get('SetSortMethod'))]
            xbmc.executebuiltin('Container.SetSortMethod(%d)' % method)

        if SC.ITEM_FOCUS in data:
            try:
                control = cur_win.getControl(cur_win.getFocusId())
                control.selectItem(int(data[SC.ITEM_FOCUS]))
            except:
                pass


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
        xbmcplugin.setResolvedUrl(params.handle, True, item)
        pass


class Resolve:
    def __init__(self, data):
        self.data = data
