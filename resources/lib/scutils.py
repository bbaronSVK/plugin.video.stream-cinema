# -*- coding: utf-8 -*-
import util
import xbmcprovider
import xbmcplugin
import xbmcutil
import resolver
import xbmcvfs
import xbmcgui
import xbmc
import unicodedata
import os
import re
import time
import string
import datetime
import urllib
import sys
import buggalo
import json
import scinema


class KODISCLib(xbmcprovider.XBMCMultiResolverContentProvider):
    last_run = 0
    sleep_time = 1000 * 1 * 60
    subs = None

    def __init__(self, provider, settings, addon):
        xbmcprovider.XBMCMultiResolverContentProvider.__init__(self, provider, settings, addon)
        provider.parent = self
        self.dialog = xbmcgui.DialogProgress()
        #self._settings()
        try:
            import StorageServer
            self.cache = StorageServer.StorageServer("Downloader")
        except:
            import storageserverdummy as StorageServer
            self.cache = StorageServer.StorageServer("Downloader")

    def _parse_settings(self, itm):
        util.info('--------------------------------------------------------')
        for (a, b) in itm:
            util.info("A: " + a + " " + json.dumps(b))
            if "name" in b:
                self.sett += "<" + b.name
                if "data" in b and "params" in b.data:
                    for (pn, pv) in b.data:
                        self.sett += ' %s="%s"' % (pn, pv)
            if 'items' in b:
                self._parse_settings(b['items'])
        util.info('--------------------------------------------------------')
        
    def _settings(self):
        return
        sp = os.path.join(self.addon_dir(), 'resources', 'settings.xml')
        itm = json.loads(util.request(scinema.BASE_URL + '/json/settings'))
        self.sett = "";
        self._parse_settings(itm['items'])
        util.info('SET: ' + self.sett);

    def _extract_infolabels(self,item):
        infoLabels = {}
        for label in ['genre', 'year', 'episode', 'season', 'top250', 'tracknumber', 'rating', 'watched', 'playcount', 'overlay', 'cast', 'castandrole', 'director', 'mpaa', 'plot', 'plotoutline', 'title', 'originaltitle', 'sorttitle', 'duration', 'studio', 'tagline', 'writer', 'tvshowtitle', 'premiered', 'status', 'code', 'aired', 'credits', 'lastplayed', 'album', 'artist', 'votes', 'trailer', 'dateadded', 'count', 'date']:
            if label in item.keys():
                if label == 'cast':
                    if hasattr(item['cast'], 'lower'):
                        item['cast'] = item['cast'].split(', ')
                    infoLabels[label] = item[label]
                else:
                    infoLabels[label] = util.decode_html(item[label])
        return infoLabels

    def render_dir(self,item):
        params = self.params()
        params.update({'list':item['url']})
        title = item['title']
        img = None
        if 'img' in item.keys():
            img = item['img']
        if title.find('$') == 0:
            try:
                title = self.addon.getLocalizedString(int(title[1:]))
            except:
                pass
        menuItems = {}
        if 'menu' in item.keys():
            for ctxtitle, value in item['menu'].iteritems():
                if ctxtitle.find('$') == 0:
                    try:
                        ctxtitle = self.addon.getLocalizedString(int(ctxtitle[1:]))
                    except:
                        pass
                menuItems[ctxtitle] = value
        self.add_dir(title,params,img,infoLabels=item,menuItems=menuItems)

    def add_dir(self, name, params, logo='', infoLabels={}, menuItems={}):
        name = util.decode_html(name)
        if not 'title' in infoLabels:
            infoLabels['title'] = ''
        if logo == None:
            logo = ''
        liz = xbmcgui.ListItem(name, iconImage='DefaultFolder.png', thumbnailImage=logo)
        
        if 'art' in infoLabels.keys():
            liz.setArt(infoLabels['art'])

        try:
            liz.setInfo(type='Video', infoLabels=self._extract_infolabels(infoLabels))
        except:
            sys.exc_info()
            util.debug("CHYBA")
            util.debug(infoLabels)
        items = []
        for mi in menuItems.keys():
            action = menuItems[mi]
            if not type(action) == type({}):
                items.append((mi, action))
            else:
                if 'action-type' in action:
                    action_type = action['action-type']
                    del action['action-type']
                    if action_type == 'list':
                        items.append((mi, 'Container.Update(%s)' % xbmcutil._create_plugin_url(action)))
                    elif action_type == 'play':
                        items.append((mi, 'PlayMedia(%s)' % xbmcutil._create_plugin_url(action)))
                    else:
                        items.append((mi, 'RunPlugin(%s)' % xbmcutil._create_plugin_url(action)))
                else:
                    items.append((mi, 'RunPlugin(%s)' % xbmcutil._create_plugin_url(action)))
        if len(items) > 0:
            liz.addContextMenuItems(items)
        return xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]), url=xbmcutil._create_plugin_url(params),
                                           listitem=liz, isFolder=True)

    def render_video(self,item):
#        util.debug("_render_video")
        
        params = self.params()
        params.update({'play':item['url']})
        downparams = self.params()
        downparams.update({'title':item['title'],'down':item['url']})
        def_item = self.provider.video_item()
        title = item['title'] #'%s%s' % (item['title'],item['size'])
        menuItems = {}
        if "!download" not in self.provider.capabilities():
            menuItems[xbmc.getLocalizedString(33003)] = downparams
        if 'trailer' in item.keys() and item['trailer'] != '' and item['trailer'] is not None:
            trailerparams = {'action-type': 'trailer', 'url': item['trailer']}
            menuItems['Trailer'] = trailerparams
        if 'menu' in item.keys():
            for ctxtitle, value in item['menu'].iteritems():
                if ctxtitle.find('$') == 0:
                    try:
                        ctxtitle = self.addon.getLocalizedString(int(ctxtitle[1:]))
                    except:
                        pass
                menuItems[ctxtitle] = value
        self.add_video(title,
                params,
                item['img'],
                infoLabels=item,
                menuItems=menuItems
                )
        

    def add_video(self, name, params={}, logo='', infoLabels={}, menuItems={}):
#        util.debug("_add_video")
#        util.debug(infoLabels)
        _infoLabels=self._extract_infolabels(infoLabels)
        name = util.decode_html(name)
        if not 'Title' in _infoLabels:
            _infoLabels['Title'] = name
        url = xbmcutil._create_plugin_url(params)
        li = xbmcgui.ListItem(name, path=url, iconImage='DefaultVideo.png', thumbnailImage=logo)
        li.setInfo(type='Video', infoLabels=_infoLabels)
        if 'art' in infoLabels.keys():
            li.setArt(infoLabels['art'])
        li.setProperty('IsPlayable', 'true')
        if 'runtime' in infoLabels.keys() and infoLabels['runtime'] > 0:
            duration = int(infoLabels['runtime']) * 60
            li.addStreamInfo('video', {'duration': duration})
        items = [(xbmc.getLocalizedString(13347), 'Action(Queue)')]
        for mi in menuItems.keys():
            action = menuItems[mi]
            if not type(action) == type({}):
                items.append((mi, action))
            else:
                if 'action-type' in action:
                    action_type = action['action-type']
                    del action['action-type']
                    if action_type == 'list':
                        items.append((mi, 'Container.Update(%s)' % xbmcutil._create_plugin_url(action)))
                    elif action_type == 'play':
                        items.append((mi, 'PlayMedia(%s)' % xbmcutil._create_plugin_url(action)))
                    elif action_type == 'trailer':
                        items.append((mi, 'PlayMedia(%s)' % action['url']))
                    else:
                        items.append((mi, 'RunPlugin(%s)' % xbmcutil._create_plugin_url(action)))
                else:
                    items.append((mi, 'RunPlugin(%s)' % xbmcutil._create_plugin_url(action)))

        if len(items) > 0:
            li.addContextMenuItems(items)
        #xbmc.executebuiltin("Container.SetViewMode(515)")
        return xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]), url=url, listitem=li,
                                           isFolder=False)

    @staticmethod
    def encode(string):
        return unicodedata.normalize('NFKD', string.decode('utf-8')).encode('ascii', 'ignore')

    def addon_dir(self):
        return self.addon.getAddonInfo('path')

    def data_dir(self):
        return self.addon.getAddonInfo('profile')

    def getSetting(self, name):
        return self.addon.getSetting(name)

    def getString(self, string_id):
        return self.addon.getLocalizedString(string_id)

    @staticmethod
    def sleep(sleep_time):
        while not xbmc.abortRequested and sleep_time > 0:
            sleep_time -= 1
            xbmc.sleep(1)

buggalo.SUBMIT_URL = scinema.submiturl
