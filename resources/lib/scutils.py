# -*- coding: utf-8 -*-
import base64
import buggalo
import codecs
import copy
import json
import myPlayer
import os
import re
import scinema
import sys
import string
import time
import top
import traceback
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
    mPlayer = None

    def __init__(self, provider, settings, addon):
        xbmcprovider.XBMCMultiResolverContentProvider.__init__(self, provider, settings, addon)
        provider.parent = self
        self.provider = provider
        self.win = xbmcgui.Window(10000)
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

    def add_item_to_library(self, item_path, item_url):
        error = False
        new = False
        item_path = xbmc.validatePath(item_path)
        if item_path:
            item_path = xbmc.translatePath(item_path)
            dir = os.path.dirname(item_path)
            if not xbmcvfs.exists(dir):
                try:
                    xbmcvfs.mkdirs(dir)
                except Exception:
                    error = True
                    util.error('Failed to create directory 1: ' + dir)

            if not xbmcvfs.exists(item_path):
                try:
                    file_desc = xbmcvfs.File(item_path, 'w')
                    file_desc.write(str(item_url))
                    file_desc.close()
                    new = True
                except Exception, e:
                    util.error('Failed to create .strm file: ' + item_path + " | " + str(e))
                    error = True
        else:
            error = True

        return (error, new)
    
    def _link(self, params):
        arg = {"play": "/Play/%d" % int(params['id']), "title": params['title']}
        if 'season' in params:
            arg.update({"play":"/Play/%d/%d/%d" % (int(params['id']), int(params['season']), int(params['episode']))})
        return xbmcutil._create_plugin_url(arg)
    
    def add_multi_item(self, params, addToSubscription=False):
        error = False
        new_items = False
        
        dialog = xbmcgui.DialogProgress()
        dialog.create('Stream Cinema CZ & SK', 'Add all to library')
        
        data = self.provider._json("%s/Lib/%s" % (top.BASE_URL, params['id']))
        page = 1
        while data is not None:
            dialog.update(0)
            total = float(len(data['list']))
            num = 0

            for i in data['list']:
                num += 1
                perc = float(num / total) * 100
                util.info("percento: %d" % int(perc))
                if dialog.iscanceled():
                    return
                
                try:
                    dialog.update(int(perc), "%s / %s - %s" % (str(page), str(data['total']), i['title']))
                except Exception:
                    util.debug('ERR: %s' % str(traceback.format_exc()) )
                    pass

                if 1:
                    param = copy.deepcopy(params)
                    util.debug("I: %s" % str(params))
                    param.update({'id': str(i['id']), 'notify': 1})
                    
                    if params['id'] == 'movie':
                        (err, new) = self.add_item(param, addToSubscription, i)
                    else:
                        (err, new) = self.add_item(param, addToSubscription)
                        
                    error |= err
                    if new is True and not err:
                        new_items = True
            page += 1
            if params['id'] == 'movies':
                data = self.provider._json("%s/Lib/%s/?p=%s" % (top.BASE_URL, params['id'], str(page)))
            else:
                data = None;
                
        if not error and new_items and not ('update' in params) and not ('notify' in params):
            self.showNotification(self.getString(30901), 'New content')
            #xbmc.executebuiltin('UpdateLibrary(video)')
        elif not error and not ('notify' in params):
            self.showNotification(self.getString(30901), 'No new content')
        if error and not ('notify' in params):
            self.showNotification('Failed, Please check kodi logs', 'Linking')
        
    def movienfo(self, data):
        out = "<movie>\n"
        for k,v in data.items():
            out += "\t<%s>%s</%s>\n" % (k, str(v), k) 
        out += "\n</movie>"
        if 'imdb' in data:
            out += "\nhttp://www.imdb.com/title/tt%s/" % data['imdb']
        if 'csfd' in data:
            out += "\nhttp://www.csfd.cz/film/%s-" % data['csfd']
        util.debug("XML: %s" % out)
        return str(out)
        
    def add_item(self, params, addToSubscription=False, data=None):
        error = False
        new_items = False
        if data is None:
            data = self.provider._json("%s/Lib/%s" % (top.BASE_URL, params['id']))
        
        if 'title' not in data:
            return
        
        if not 'refresh' in params:
            params['refresh'] = str(self.getSetting("refresh_time"))
        
        if 'ep' not in data:
            item_dir = self.getSetting('library-movies')
            xml_path = os.path.join(item_dir, self.normalize_filename(data['title']),
                                 self.normalize_filename(data['title'] + '.nfo'))
            self.add_item_to_library(xml_path, self.movienfo(data))
            item_path = os.path.join(item_dir, self.normalize_filename(data['title']),
                                 self.normalize_filename(data['title'] + '.strm'))
            (error, new_items) = self.add_item_to_library(item_path, self._link(data))
        else:
            if not ('notify' in params):
                self.showNotification(data['title'], 'Checking new content')

            subs = self.get_subs()
            item_dir = self.getSetting('library-tvshows')

            if not (data['id'] in subs) and addToSubscription:
                subs.update({data['id']: data['title']})
                self.set_subs(subs)

            if not xbmcvfs.exists(os.path.join(item_dir, 
                            self.normalize_filename(data['title']),
                            'tvshow.nfo')):
                if 'tvdb' in data:
                    tvid = data['tvdb']
                else:
                    tvid = self.getTVDB(data)
                if tvid:
                    self.add_item_to_library(os.path.join(item_dir, self.normalize_filename(
                        data['title']), 'tvshow.nfo'),
                        'http://thetvdb.com/index.php?tab=series&id=%s' % str(tvid))

            for itm in data['ep']:
                item_path = os.path.join(
                    item_dir, self.normalize_filename(data['title']),
                    'Season ' + itm['season'],
                    "S" + itm['season'] +
                    "E" + itm['episode'] + '.strm')
                (err, new) = self.add_item_to_library(item_path, self._link(data))
                error |= err
                if new is True and not err:
                    new_items = True
                    
        if not error and new_items and not ('update' in params) and not ('notify' in params):
            self.showNotification(data['title'], 'New content')
            #xbmc.executebuiltin('UpdateLibrary(video)')
        elif not error and not ('notify' in params):
            self.showNotification(data['title'], 'No new content')
        if error and not ('notify' in params):
            self.showNotification('Failed, Please check kodi logs', 'Linking')
        return (error, new_items)
    
    def getTVDB(self, params):
        if 'imdb' in params:
            data = self.provider.get_data_cached('http://thetvdb.com/api/GetSeriesByRemoteID.php?=' +
                                urllib.urlencode({'imdbid': params['imdb'], 'language': 'en'}))
        else:
            data = self.provider.get_data_cached('http://thetvdb.com/api/GetSeries.php?' +
                                urllib.urlencode({'seriesname': params['name'], 'language': 'en'}))
        try:
            tvid = re.search('<id>(\d+)</id>', data).group(1)
            return tvid
        except:
            pass
        return None

    def normalize_filename(self, name, validChars=None):
        validFilenameChars = "-_.() %s%s" % (string.ascii_letters, string.digits)
        if (validChars is not None):
            validFilenameChars = validChars
        cleanedFilename = self.encode(name)
        return ''.join(c for c in cleanedFilename if c in validFilenameChars)

    def showNotification(self, title, message, time=1000):
        xbmcgui.Dialog().notification(self.encode(title), self.encode(message), time=time,
                                      icon=xbmc.translatePath(self.addon_dir() + "/icon.png"),
                                      sound=False)
    
    def run_custom(self, params):
        util.debug("RUN CUSTOM: %s" % str(params))
        if 'action' in params:
            util.debug("ACTION: %s" % str(params['action']))  
            action = params['action']
            subs = False
            if action == 'remove-from-sub':
                subs = self.get_subs()
                if params['id'] in subs.keys():
                    del subs[params['id']]
                    self.set_subs(subs)
                    self.showNotification(params['title'], 'Removed from subscription')
                    xbmc.executebuiltin('Container.Refresh')
            if action == 'add-to-lib-sub':
                subs = True
                action = 'add-to-lib'
            if action == 'add-to-lib':
                if params['id'] in ['movies', 'series']:
                    self.add_multi_item(params, subs)
                else:
                    self.add_item(params, subs)
                if subs:
                    xbmc.executebuiltin('Container.Refresh')
        elif 'cmd' in params:
            try:
                if '^;^' in params['cmd']:
                    tmp = params['cmd'].split('^;^')
                else:
                    tmp = [params['cmd']]
                for cmd in tmp:
                    util.debug("RUN CMD: %s" % str(cmd))
                    xbmc.executebuiltin(cmd)
            except Exception:
                util.debug("ERROR: %s" % str(traceback.format_exc()))
                pass

    def play(self, item):
        util.debug("PLAY ITEM: %s" % str(item))
        stream = self.resolve(item['url'])
        if stream:
            if 'headers' in stream.keys():
                headerStr = '|' + urllib.urlencode(stream['headers'])
                if len(headerStr) > 1:
                    stream['url'] += headerStr
            util.debug('Sending %s to player' % stream['url'])
            li = xbmcgui.ListItem(path=stream['url'], iconImage='DefaulVideo.png')
            util.debug("PLAY::LI::" + str(stream))
            il = self._extract_infolabels(stream)
            if 'originaltitle' in stream and 'episode' not in stream:
                il['title'] = stream['originaltitle']
            
            uniq = {}
            if 'imdb' in stream:
                uniq.update({'imdb': stream['imdb']})
                li.setProperty('IMDBNumber', stream['imdb']);
            if 'tmdb' in stream:
                uniq.update({'tmdb': stream['tmdb']})
                li.setProperty('TMDBNumber', stream['tmdb']);
            if 'tvdb' in stream:
                uniq.update({'tvdb': stream['tvdb']})
                li.setProperty('TVDBNumber', stream['tvdb']);
            if 'csfd' in stream:
                uniq.update({'csfd': stream['csfd']})
                li.setProperty('CSFDNumber', stream['csfd']);
            
            try:
                li.setUniqueIDs(uniq)
                util.debug("[SC] uniq id: %s" % str(uniq))
            except Exception:
                util.debug("[SC] uniq err: %s" % str(traceback.format_exc()))
                pass
                
            util.debug("INFO: %s" % str(self._extract_infolabels(stream)))
            
            if len(il) > 0:  # only set when something was extracted
                li.setInfo('video', il)
                util.debug("IL: %s" % str(il))
            
            if (stream['subs'] == '' or stream['subs'] is None) and stream['lang'].strip() not in ['CZ', 'SK']:
                #util.debug(stream)
                stream['subs'] = self.findSubtitles(stream)
                
            if stream['subs'] == '' or stream['subs'] == 'internal' or stream['subs'] == 'disabled':
                stream.remove('subs')
                
            if 'subs' in stream and stream['subs'] != '' and stream['subs'] is not None:
                #util.debug("Seturnm titulky: " + str(stream['subs']))
                li.setSubtitles([stream['subs']])
            self.win.setProperty(top.__scriptid__, top.__scriptid__)
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
            'premiered', 'status', 'aired', 'credits', 'lastplayed', 'album', 'artist', 'votes', 'trailer', 'dateadded', 'count', 'date', 'imdbnumber']:
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
        if item['url'].startswith('cmd://'):
            util.debug('command!!!')
            params.update({'cmd':item['url'][6:]})
        else:
            params.update({'list':item['url']})
        title = str(item['title'])
        try:
            title.index('$')
            util.debug("[SC] mame prelozit %s" % title)
            try:
                for i in list(re.finditer('\$([0-9]+)', title, re.IGNORECASE | re.DOTALL)):
                    try:
                        t = self.getString(int(i.group(1)))
                        util.debug('[SC] prelozene: %s' % t)
                        title = title.replace('$%s' % i.group(1), t)
                    except Exception:
                        util.debug('[SC] Neprelozene %s' % title[1:])
                        pass
            except Exception:
                pass
        except Exception:
            pass
        item['title'] = title
            
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
        if item.get('name_seo'):
            downparams.update({'title':"%s%s" % (item['name_seo'], item['extension']), 'down':item['url']})
        else:
            downparams.update({'title':"%s%s" % (item['title'], 'mp4'), 'down':item['url']})
        def_item = self.provider.video_item()
        title = item['title'] #'%s%s' % (item['title'],item['size'])
        menuItems = {}
        if "!download" not in self.provider.capabilities():
            menuItems[xbmc.getLocalizedString(33003)] = downparams
        if 'trailer' in item.keys() and item['trailer'] != '' and item['trailer'] is not None:
            trailerparams = {'action-type': 'trailer', 'url': item['trailer']}
            menuItems['Trailer'] = trailerparams
        if 'menu' in item.keys():
            util.debug("[SC] -=-=-=-=-=---------------------------------")
            for ctxtitle, value in item['menu'].iteritems():
                if ctxtitle.find('$') == 0:
                    try:
                        ctxtitle = self.addon.getLocalizedString(int(ctxtitle[1:]))
                    except:
                        pass
                menuItems[ctxtitle] = value
        util.debug("menuItems: %s" % str(menuItems))
        self.add_video(title,
                params,
                item['img'],
                infoLabels=item,
                menuItems=menuItems
                )
        

    def add_video(self, name, params={}, logo='', infoLabels={}, menuItems={}):
        #util.debug("_add_video")
        #util.debug("[SC] add video info: %s" % str(infoLabels))
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

    def service(self):
        util.info("SC Service Started")
        if top.player is None:
            top.player = myPlayer.MyPlayer()
        try:
            sleep_time = int(self.getSetting("start_sleep_time")) * 1000 * 60
        except:
            sleep_time = self.sleep_time
            pass

        #self.sleep(sleep_time)

        try:
            self.last_run = float(self.cache.get("subscription.last_run"))
        except:
            self.last_run = time.time()
            self.cache.set("subscription.last_run", str(self.last_run))
            pass

        if not xbmc.abortRequested and time.time() > self.last_run:
            self.evalSchedules()

        self.sleep_time = 100
        while not xbmc.abortRequested:
            if(time.time() > self.last_run + 600):
                self.evalSchedules()
                self.last_run = time.time()
                self.cache.set("subscription.last_run", str(self.last_run))
            self.sleep(self.sleep_time)
        util.info("SC Shutdown")
    
    def evalSchedules(self):
        util.debug("evalSchedules")

    def findSubtitles(self, stream):
        try:
            if not self.getSetting('subtitles') == 'true': 
                raise Exception()
            imdb = stream['imdb']
            season = stream['season']
            episode = stream['episode']

            util.debug("[SC] Hladam titulky")
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
            util.debug("[SC] TOKEN: %s" % token)

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

            subtitle = xbmc.validatePath(xbmc.translatePath('special://temp/'))
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
        except Exception:
            util.debug("[SC] Neriesim TITULKY")
            util.debug(traceback.format_exc())
            pass

    def get_subs(self):
        if self.subs is not None:
            return self.subs
        data = self.cache.get("subscription")
        try:
            if data == '':
                return {}
            subs = eval(data)
            for url, name in subs.iteritems():
                if not isinstance(name, dict):
                    subs[url] = {'name': name,
                                 'refresh': '1', 'last_run': -1}
            self.set_subs(subs)
            self.subs = subs
        except Exception, e:
            util.error(e)
            subs = {}
        return subs

    def set_subs(self, subs):
        self.subs = subs
        self.cache.set("subscription", repr(subs))
buggalo.SUBMIT_URL = top.submiturl
