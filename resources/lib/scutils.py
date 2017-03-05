# -*- coding: utf-8 -*-
import base64
import buggalo
import codecs
import json
import os
import re
import scinema
import sys
import unicodedata
import urllib
import util
import xbmc
import xbmcgui
import xbmcplugin
import xbmcprovider
import xbmcutil
import xbmcvfs
import xmlrpclib
import zlib

class KODISCLib(xbmcprovider.XBMCMultiResolverContentProvider):
    last_run = 0
    sleep_time = 1000 * 1 * 60
    subs = None

    def __init__(self, provider, settings, addon):
        xbmcprovider.XBMCMultiResolverContentProvider.__init__(self, provider, settings, addon)
        provider.parent = self
        self.noImage = os.path.join(self.addon_dir(), 'resources', 'img', 'no-image.png')
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

    def play(self, item):
        stream = self.resolve(item['url'])
        if stream:
            if 'headers' in stream.keys():
                headerStr = '|' + urllib.urlencode(stream['headers'])
                if len(headerStr) > 1:
                    stream['url'] += headerStr
            util.debug('Sending %s to player' % stream['url'])
            li = xbmcgui.ListItem(path=stream['url'], iconImage='DefaulVideo.png')
            util.debug("PLAY::LI::" + str(li))
            il = self._extract_infolabels(item['info'])
            
            if len(il) > 0:  # only set when something was extracted
                li.setInfo('video', il)
            
            if (stream['subs'] == '' or stream['subs'] is None) and stream['lang'].strip() not in ['CZ', 'SK']:
                util.debug(stream)
                stream['subs'] = self.findSubtitles(stream)
                
            if stream['subs'] == '' or stream['subs'] == 'internal' or stream['subs'] == 'disabled':
                stream.remove('subs')
                
            if 'subs' in stream and stream['subs'] != '' and stream['subs'] is not None:
                util.debug("Seturnm titulky: " + str(stream['subs']))
                li.setSubtitles([stream['subs']])
            xbmcplugin.setResolvedUrl(int(sys.argv[1]), True, li)
        
    def _settings(self):
        return
        sp = os.path.join(self.addon_dir(), 'resources', 'settings.xml')
        itm = json.loads(util.request(scinema.BASE_URL + '/json/settings'))
        self.sett = "";
        self._parse_settings(itm['items'])
        util.info('SET: ' + self.sett);

    def _extract_infolabels(self,item):
        infoLabels = {}
        for label in ['genre', 'year', 'episode', 'season', 'top250', 'tracknumber', 'rating', 'watched', 'playcount', 'overlay', 'cast', 'castandrole', 
            'director', 'mpaa', 'plot', 'plotoutline', 'title', 'originaltitle', 'sorttitle', 'duration', 'studio', 'tagline', 'writer', 'tvshowtitle', 
            'premiered', 'status', 'code', 'aired', 'credits', 'lastplayed', 'album', 'artist', 'votes', 'trailer', 'dateadded', 'count', 'date']:
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
        if 'title' not in infoLabels:
            infoLabels['title'] = ''
        if logo is None:
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
        #util.debug("_render_video")
        
        params = self.params()
        params.update({'play':item['url']})
        #for k,v in item.iteritems():
        #    params.update({k: str(v)})
        downparams = self.params()
        downparams.update({'title':"%s%s" % (item['name_seo'], item['extension']), 'down':item['url']})
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
        #util.debug("_add_video")
        #util.debug(infoLabels)
        _infoLabels=self._extract_infolabels(infoLabels)
        name = util.decode_html(name)
        if 'Title' not in _infoLabels:
            _infoLabels['Title'] = name
        url = xbmcutil._create_plugin_url(params)
        if logo == '' or logo is None:
            logo = self.noImage
        li = xbmcgui.ListItem(name, path=url, iconImage='DefaultVideo.png', thumbnailImage=logo)
        li.setInfo(type='Video', infoLabels=_infoLabels)
        if 'mvideo' in infoLabels.keys():
            li.addStreamInfo('video', infoLabels['mvideo'])
        if 'maudio' in infoLabels.keys():
            li.addStreamInfo('audio', infoLabels['maudio'])
        if 'msubtitle' in infoLabels.keys():
            li.addStreamInfo('subtitle', infoLabels['msubtitle'])
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

    def findSubtitles(self, stream):
        try:
            if not self.getSetting('subtitles') == 'true': 
                raise Exception()
            imdb = stream['imdb']
            season = stream['season']
            episode = stream['episode']

            util.debug("Hladam titulky")
            langDict = {'Afrikaans': 'afr', 'Albanian': 'alb', 'Arabic': 'ara', 'Armenian': 'arm', 'Basque': 'baq', 'Bengali': 'ben', 'Bosnian': 'bos', 'Breton': 'bre', 'Bulgarian': 'bul', 'Burmese': 'bur', 'Catalan': 'cat', 'Chinese': 'chi', 'Croatian': 'hrv', 'Czech': 'cze', 'Danish': 'dan', 'Dutch': 'dut', 'English': 'eng', 'Esperanto': 'epo', 'Estonian': 'est', 'Finnish': 'fin', 'French': 'fre', 'Galician': 'glg', 'Georgian': 'geo', 'German': 'ger', 'Greek': 'ell', 'Hebrew': 'heb', 'Hindi': 'hin', 'Hungarian': 'hun', 'Icelandic': 'ice', 'Indonesian': 'ind', 'Italian': 'ita', 'Japanese': 'jpn', 'Kazakh': 'kaz', 'Khmer': 'khm', 'Korean': 'kor', 'Latvian': 'lav', 'Lithuanian': 'lit', 'Luxembourgish': 'ltz', 'Macedonian': 'mac', 'Malay': 'may', 'Malayalam': 'mal', 'Manipuri': 'mni', 'Mongolian': 'mon', 'Montenegrin': 'mne', 'Norwegian': 'nor', 'Occitan': 'oci', 'Persian': 'per', 'Polish': 'pol', 'Portuguese': 'por,pob', 'Portuguese(Brazil)': 'pob,por', 'Romanian': 'rum', 'Russian': 'rus', 'Serbian': 'scc', 'Sinhalese': 'sin', 'Slovak': 'slo', 'Slovenian': 'slv', 'Spanish': 'spa', 'Swahili': 'swa', 'Swedish': 'swe', 'Syriac': 'syr', 'Tagalog': 'tgl', 'Tamil': 'tam', 'Telugu': 'tel', 'Thai': 'tha', 'Turkish': 'tur', 'Ukrainian': 'ukr', 'Urdu': 'urd'}

            codePageDict = {'ara': 'cp1256', 'ar': 'cp1256', 'ell': 'cp1253', 'el': 'cp1253', 'heb': 'cp1255', 'he': 'cp1255', 'tur': 'cp1254', 'tr': 'cp1254', 'rus': 'cp1251', 'ru': 'cp1251'}

            quality = ['bluray', 'hdrip', 'brrip', 'bdrip', 'dvdrip', 'webrip', 'hdtv']

            langs = []
            try:
                try: langs = langDict[self.getSetting('subtitles.lang.1')].split(',')
                except: langs.append(langDict[self.getSetting('subtitles.lang.1')])
            except: 
                pass
            
            try:
                try: langs = langs + langDict[self.getSetting('subtitles.lang.2')].split(',')
                except: langs.append(langDict[self.getSetting('subtitles.lang.2')])
            except: 
                pass

            server = xmlrpclib.Server('http://api.opensubtitles.org/xml-rpc', verbose=0)
            token = server.LogIn('', '', 'en', 'XBMC_Subtitles_v1')['token']
            util.debug("TOKEN: %s" % token)

            sublanguageid = ','.join(langs) ; imdbid = re.sub('[^0-9]', '', imdb)

            if season is not None and episode is not None:
                result = server.SearchSubtitles(token, [{'sublanguageid': sublanguageid, 'imdbid': imdbid, 'season': season, 'episode': episode}])['data']
                fmt = ['hdtv']
            else:
                result = server.SearchSubtitles(token, [{'sublanguageid': sublanguageid, 'imdbid': imdbid}])['data']
                try: vidPath = stream['url']
                except: vidPath = ''
                fmt = re.split('\.|\(|\)|\[|\]|\s|\-', vidPath)
                fmt = [i.lower() for i in fmt]
                fmt = [i for i in fmt if i in quality]

            filter = []
            result = [i for i in result if i['SubSumCD'] == '1']

            for lang in langs:
                filter += [i for i in result if i['SubLanguageID'] == lang and any(x in i['MovieReleaseName'].lower() for x in fmt)]
                filter += [i for i in result if i['SubLanguageID'] == lang and any(x in i['MovieReleaseName'].lower() for x in quality)]
                filter += [i for i in result if i['SubLanguageID'] == lang]

            try: 
                lang = xbmc.convertLanguage(filter[0]['SubLanguageID'], xbmc.ISO_639_1)
            except: 
                lang = filter[0]['SubLanguageID']

            content = [filter[0]['IDSubtitleFile'],]
            content = server.DownloadSubtitles(token, content)
            content = base64.b64decode(content['data'][0]['data'])
            content = str(zlib.decompressobj(16+zlib.MAX_WBITS).decompress(content))

            subtitle = xbmc.translatePath('special://temp/')
            subtitle = os.path.join(subtitle, 'AutomatickeTitulky.%s.srt' % lang)

            codepage = codePageDict.get(lang, '')
            if codepage and self.getSetting('subtitles.utf') == 'true':
                try:
                    content_encoded = codecs.decode(content, codepage)
                    content = codecs.encode(content_encoded, 'utf-8')
                except:
                    pass

            file = xbmcvfs.File(subtitle, 'w')
            file.write(str(content))
            file.close()
            return subtitle
        except:
            pass
buggalo.SUBMIT_URL = scinema.submiturl
