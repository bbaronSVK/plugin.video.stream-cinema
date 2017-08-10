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
import trakt
import sctop
import traceback
import unicodedata
import urllib
import util
import xbmc
import xbmcgui
import xbmcplugin
import xbmcprovider
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
        sctop.uid = provider.uid
        self.provider = provider
        self.win = xbmcgui.Window(10000)
        self.noImage = os.path.join(self.addon_dir(), 'resources', 'img', 'no-image.png')
        #self._settings()
        self.cache = sctop.cache

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
        
        util.debug("[SC] add item: %s" % item_path)
        return (error, new)
    
    def _link(self, params):
        arg = {"play": "/Play/%d" % int(params['id']), "title": params['title']}
        if 'season' in params:
            arg.update({"play":"/Play/%d/%d/%d" % (int(params['id']), int(params['season']), int(params['episode']))})
        return sctop._create_plugin_url(arg, 'plugin://%s/' % sctop.__scriptid__)
    
    def add_multi_item(self, params, addToSubscription=False):
        error = False
        new = False
        new_items = False
        e = False
        n = False
        subs = self.getSubs()
        
        dialog = xbmcgui.DialogProgress()
        dialog.create('Stream Cinema CZ & SK', 'Add all to library')
        
        data = self.provider._json("%s/Lib/%s" % (sctop.BASE_URL, params['id']))
        page = 1
        while data is not None:
            dialog.update(0)
            total = float(len(data['list']))
            num = 0
            new_in_page = False

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
                    
                    if params['id'] == 'movies':
                        (e, n) = self.add_item(param, addToSubscription, i)
                    else:
                        if addToSubscription == False or (i['id'] not in subs) \
                           or (i['id'] in subs and self.canCheck(subs[i['id']]['last_run'])):
                            (e, n) = self.add_item(param, addToSubscription)
                        
                    error |= e
                    new |= n
                    new_in_page |= n
                    if new is True and not error:
                        new_items = True
            page += 1
            if params['id'] == 'movies':
                if 'force' not in params and page > 2 and new_in_page == False:
                    util.debug("[SC] Dalej nepridavam, nemame nic dalsie na pridanie ...")
                    data = None
                else:
                    data = self.provider._json("%s/Lib/%s/?p=%s" % (sctop.BASE_URL, params['id'], str(page)))
            else:
                data = None;
                
        if not error and new_items and not ('update' in params) and not ('notify' in params):
            self.showNotification(self.getString(30901), 'New content')
            xbmc.executebuiltin('UpdateLibrary(video)')
        elif not error and not ('notify' in params):
            self.showNotification(self.getString(30901), 'No new content')
        if error and not ('notify' in params):
            self.showNotification('Failed, Please check kodi logs', 'Linking')
        
    def movienfo(self, data):
        out = ''
        if 'imdb' in data and int(data['imdb']) > 0:
            out += "http://www.imdb.com/title/tt%08d/\n" % int(data['imdb'])
        if 'tmdb' in data and int(data['tmdb']) > 0:
            out += "https://www.themoviedb.org/movie/%d/\n" % int(data['tmdb'])
        if 'csfd' in data and int(data['csfd']) > 0:
            out += "http://www.csfd.cz/film/%d-\n" % int(data['csfd'])
        if 'tvdb' in data and int(data['tvdb']) > 0:
            out += "http://thetvdb.com/index.php?tab=series&id=%d\n" % int(data['tvdb'])
            
        util.debug("XML: %s" % out)
        return str(out)
        
    def add_item(self, params, addToSubscription=False, data=None):
        error = False
        new_items = False
        if data is None:
            data = self.provider._json("%s/Lib/%s" % (sctop.BASE_URL, params['id']))
        
        if 'title' not in data:
            return
        
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

            subs = self.getSubs()
            item_dir = self.getSetting('library-tvshows')

            if not (data['id'] in subs) and addToSubscription:
                subs.update({data['id']: {'title': data['title'], 'last_run':time.time()}})
                self.setSubs(subs)

            if not xbmcvfs.exists(os.path.join(item_dir, 
                            self.normalize_filename(data['title']),
                            'tvshow.nfo')):
                if 'tvdb' not in data:
                    data['tvdb'] = self.getTVDB(data)
                self.add_item_to_library(os.path.join(item_dir, self.normalize_filename(
                        data['title']), 'tvshow.nfo'), self.movienfo(data))

            for itm in data['ep']:
                item_path = os.path.join(
                    item_dir, self.normalize_filename(data['title']),
                    'Season ' + itm['season'],
                    "S" + itm['season'] +
                    "E" + itm['episode'] + '.strm')
                (err, new) = self.add_item_to_library(item_path, self._link(itm))
                error |= err
                if new is True and not err:
                    new_items = True
                    
        if not error and new_items and not ('update' in params) and not ('notify' in params):
            self.showNotification(data['title'], 'New content')
            xbmc.executebuiltin('UpdateLibrary(video)')
        elif not error and not ('notify' in params):
            self.showNotification(data['title'], 'No new content')
        if error and not ('notify' in params):
            self.showNotification('Failed, Please check kodi logs', 'Linking')
        return (error, new_items)

    def canCheck(self, last_run):
        next_check = last_run + (int(self.getSetting('refresh_time')) * 3600 * 24)
        return next_check < time.time()
    
    def evalSchedules(self):
        if not self.scanRunning() and not self.isPlaying():
            notified = False
            util.info("[SC] Loading subscriptions")
            subs = self.getSubs()
            util.debug("[SC] Subs: %s" % str(subs))
            new_items = False
            for iid, data in subs.iteritems():
                if xbmc.abortRequested:
                    util.info("[SC] Exiting")
                    return
                if self.scanRunning() or self.isPlaying():
                    self.cache.delete("subscription.last_run")
                    return
                if self.canCheck(data['last_run']):
                    if not notified:
                        self.showNotification('Subscription', 'Chcecking')
                        notified = True
                    util.debug("[SC] Refreshing %s" % str(iid))
                    (e, n) = self.add_item({'id': str(iid)})
                    new_items |= n
                    data['last_run'] = time.time()
                    subs[iid] = data
                    self.setSubs(subs)
            if new_items:
                xbmc.executebuiltin('UpdateLibrary(video)')
            notified = False
        else:
            util.info("SOSAC Scan skipped")

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
                subs = self.getSubs()
                if params['id'] in subs.keys():
                    del subs[params['id']]
                    self.setSubs(subs)
                    self.showNotification(params['title'], 'Removed from subscription')
                    xbmc.executebuiltin('Container.Refresh')
            if action == 'add-to-lib-sub':
                subs = True
                action = 'add-to-lib'
            if action == 'add-to-lib':
                if params['id'] in ['movies', 'series'] or 'movies' in params['id']:
                    self.add_multi_item(params, subs)
                else:
                    self.add_item(params, subs)
                if subs:
                    xbmc.executebuiltin('Container.Refresh')
            if action == 'subs':
                self.evalSchedules()
            if action == 'rsubs':
                self.setSubs({})
            if action == 'last':
                self.list(self.provider.items(self.provider._url("/Last/?%s" % urllib.urlencode({'ids': json.dumps(self.getLast())}))))
                return xbmcplugin.endOfDirectory(int(sys.argv[1]))
            if action == 'traktManager':
                if trakt.getTraktCredentialsInfo() == True:
                    trakt.manager(params['name'], params['imdb'], params['tvdb'], params['content'])
                return
            if action == 'traktWatchlist':
                if trakt.getTraktCredentialsInfo() == True:
                    self.list(self.provider.items(data={'menu':trakt.getLists()}))
                else:
                    self.list([])
                return xbmcplugin.endOfDirectory(int(sys.argv[1]))
            if action == 'traktShowList':
                if trakt.getTraktCredentialsInfo() == True:
                    util.debug("[SC] params: %s" % str(params))
                    ids = trakt.getList(params['id'])
                    self.list(self.provider.items(self.provider._url("/Search/?%s" % urllib.urlencode({'ids': json.dumps(ids)}))))
                return xbmcplugin.endOfDirectory(int(sys.argv[1]))
            if action == 'authTrakt':
                trakt.authTrakt()
            if action == 'speedtest': #                               1:350    2:500    3:750  4:1000 5:1500   6:2000   7:2500 8:3000  9:3500   10:4000
                g = sctop.getString
                x = [g(30551), g(30552), g(30553), g(30554), g(30555), 
                    g(30556), g(30557), g(30558), g(30559), g(30560)]
                ret = [1500, 2000]
                run = 2
                try:
                    ret =sctop.dialog.multiselect(g(30501), x, preselect=[5,6])
                except:
                    try:
                        xret = sctop.dialog.select(g(30501), x)
                        run = 5
                        ret = [xret]
                    except:
                        pass
                _files = [0, 350, 500, 750, 1000, 1500, 2000, 2500, 3000, 3500, 4000]
                out = []
                for i in ret:
                    out.append(_files[i])
                if len(out) < 1:
                    out = [1500, 2000]
                from speedtest import speedTest, pretty_speed
                pg = sctop.progressDialog
                pg.create(g(30050))
                pg.update(0)
                wspeedtest = speedTest('speedtest.webshare.cz', run, out)
                pg.update(10, wspeedtest.host)
                wsdown = wspeedtest.download()
                pg.update(50)
                speedtest = speedTest(None, run, out)
                pg.update(60, speedtest.host)
                bedown = speedtest.download()
                pg.update(100)
                pg.close()
                sctop.dialog.ok(g(30050), "%s: %s" % (wspeedtest.host, str(pretty_speed(wsdown))), "%s: %s" % (speedtest.host, str(pretty_speed(bedown))))
                sctop.openSettings('1.0')
                
            if action == 'trakt':
                movies = self.getTraktLastActivity('series') #trakt.getWatchedActivity()
                util.debug("[SC] movies: %s" % str(movies))
            if action == 'test':
                data = myPlayer.MyPlayer.executeJSON({'jsonrpc': '2.0', 'id': 0, 'method': 'VideoLibrary.GetMovies', 'params': {'properties': ['title', 'imdbnumber', 'year', 'playcount', 'lastplayed', 'file', 'dateadded', 'runtime', 'userrating']}})
                util.debug("[SC] RPC: %s" % str(json.dumps(data)))
        elif 'cmd' in params:
            try:
                if '^;^' in params['cmd']:
                    tmp = params['cmd'].split('^;^')
                else:
                    tmp = [params['cmd']]
                for cmd in tmp:
                    util.debug("[SC] RUN CMD: %s" % str(cmd))
                    xbmc.executebuiltin(cmd)
            except Exception:
                util.debug("[SC] ERROR: %s" % str(traceback.format_exc()))
                pass
    
    def isPlaying(self):
        return xbmc.Player().isPlaying()

    def scanRunning(self):
        return (xbmc.getCondVisibility('Library.IsScanningVideo') or
                xbmc.getCondVisibility('Library.IsScanningMusic'))

    def setUniq(self, li, stream):
        uniq = {}
        if 'imdb' in stream:
            util.debug("[SC] uniq imdb %s" % stream['imdb'])
            uniq.update({'imdb': stream['imdb']})
            li.setProperty('IMDBNumber', stream['imdb']);
        if 'tmdb' in stream:
            util.debug("[SC] uniq tmdb %s" % stream['tmdb'])
            uniq.update({'tmdb': stream['tmdb']})
            li.setProperty('TMDBNumber', stream['tmdb']);
        if 'tvdb' in stream:
            util.debug("[SC] uniq tvdb %s" % stream['tvdb'])
            uniq.update({'tvdb': stream['tvdb']})
            li.setProperty('TVDBNumber', stream['tvdb']);
        if 'csfd' in stream:
            util.debug("[SC] uniq csfd %s" % stream['csfd'])
            uniq.update({'csfd': stream['csfd']})
            li.setProperty('CSFDNumber', stream['csfd']);
        if 'trakt' in stream:
            util.debug("[SC] uniq trakt %s" % stream['trakt'])
            uniq.update({'trakt': stream['trakt']})
            li.setProperty('TRAKTNumber', stream['trakt']);

        try:
            li.setUniqueIDs(uniq)
            util.debug("[SC] uniq id: %s" % str(uniq))
        except Exception:
            util.debug("[SC] uniq err: %s" % str(traceback.format_exc()))
            pass

    def play(self, item):
        util.debug("PLAY ITEM: %s" % str(item))
        stream = self.resolve(item['url'])
        
        if stream:
            imdb = stream['imdb'] if 'imdb' in stream else 0
            tvdb = stream['tvdb'] if 'tvdb' in stream else 0
            trakt = stream['trakt'] if 'trakt' in stream else 0
            ids = {'imdb': imdb, 'tvdb': tvdb, 'trakt': trakt}
            ids = dict((k,v) for k, v in ids.iteritems() if not v == '0')

            xbmcgui.Window(10000).setProperty('script.trakt.ids', json.dumps(ids))
            xbmcgui.Window(10000).setProperty('%s.ids' % sctop.__scriptid__, json.dumps(ids))
            xbmcgui.Window(10000).setProperty('%s.stream' % sctop.__scriptid__, json.dumps(stream))
            self.win.setProperty('scid', stream['id'])
            
            if 'headers' in stream.keys():
                headerStr = '|' + urllib.urlencode(stream['headers'])
                if len(headerStr) > 1:
                    stream['url'] += headerStr
            util.debug('Sending %s to player' % stream['url'])
            li = xbmcgui.ListItem(path=stream['url'], iconImage='DefaulVideo.png')
            util.debug("PLAY::LI::" + str(stream))
            il = self._extract_infolabels(stream)
            if 'dtitle' in item['info']:
                il['title'] = item['info']['dtitle']
                
            if 'art' in stream:
                util.debug("[SC] Play MAME ART")
                if 'poster' in stream['art'] and 'thumb' not in stream['art']:
                    stream['art'].update({'thumb':stream['art']['poster']})
                li.setArt(stream['art']);
            else:
                util.debug("[SC] Play nemame ART")
            
            self.setUniq(li, stream)
            
            util.debug("INFO: %s" % str(self._extract_infolabels(stream)))
            
            if len(il) > 0:  # only set when something was extracted
                li.setInfo('video', il)
                util.debug("IL: %s" % str(il))
            
            if (stream['subs'] == '' or stream['subs'] is None) and stream['lang'].strip()[:2] not in ['CZ', 'SK']:
                #util.debug(stream)
                stream['subs'] = self.findSubtitles(stream)
                
            if stream['subs'] == '' or stream['subs'] == 'internal' or stream['subs'] == 'disabled':
                stream.remove('subs')
                
            if 'subs' in stream and stream['subs'] != '' and stream['subs'] is not None:
                #util.debug("Seturnm titulky: " + str(stream['subs']))
                li.setSubtitles([stream['subs']])
            self.win.setProperty(sctop.__scriptid__, sctop.__scriptid__)
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
            'premiered', 'status', 'aired', 'credits', 'lastplayed', 'album', 'artist', 'votes', 'trailer', 'dateadded', 'count', 'date', 'imdbnumber',
            'mediatype']:
            if label in item.keys():
                if label == 'cast':
                    if hasattr(item['cast'], 'lower'):
                        item['cast'] = item['cast'].split(', ')
                    infoLabels[label] = item[label]
                else:
                    infoLabels[label] = util.decode_html(item[label])
        try:
            if item.get('imdb') and int(item.get('imdb')) > 0 and item.get('season') is None:
                if 'tt%07d' % int(item.get('imdb')) in self.getTraktLastActivity():
                    util.debug("[SC] oznacujem za videne z trakt.tv %s" % str(item))
                    infoLabels['playcount'] = 1
                util.debug("[SC] item ma imdb %s" % str(item.get('imdb')))
        except:
            pass
        
        try:
            if item.get('tvdb') and int(item.get('tvdb')) > 0 and item.get('season') is not None and item.get('episode') is not None:
                playcount = [i[2] for i in self.getTraktLastActivity('series') if i[0] == item.get('tvdb')]
                playcount = playcount[0] if len(playcount) > 0 else []
                playcount = [i for i in playcount if int(item.get('season')) == int(i[0]) and int(item.get('episode')) == int(i[1])]
                playcount = 1 if len(playcount) > 0 else 0
                infoLabels['playcount'] = playcount
                util.debug("[SC] item ma tvdb %s %sx%s %s" % (str(item.get('tvdb')), str(item.get('season')), str(item.get('episode')), str(playcount)))
        except:
            pass
        
        #infoLabels['overlay'] = 7
        return infoLabels

    def render_dir(self,item):
        params = self.params()
        if item['url'].startswith('cmd://'):
            #util.debug('command!!!')
            params.update({'cmd':item['url'][6:]})
        else:
            params.update({'list':item['url']})
        title = str(item['title'])
        try:
            title.index('$')
            #util.debug("[SC] mame prelozit %s" % title)
            try:
                for i in list(re.finditer('\$([0-9]+)', title, re.IGNORECASE | re.DOTALL)):
                    try:
                        t = self.getString(int(i.group(1)))
                        #util.debug('[SC] prelozene: %s' % t)
                        title = title.replace('$%s' % i.group(1), t)
                    except Exception:
                        #util.debug('[SC] Neprelozene %s' % title[1:])
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

        if 'selected' in infoLabels.keys():
            wnd = xbmcgui.Window(xbmcgui.getCurrentWindowId())
            util.debug("[SC] wnd: %s [%d]" % (str(wnd), xbmcgui.getCurrentWindowId()))
            
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
                        items.append((mi, 'Container.Update(%s)' % sctop._create_plugin_url(action)))
                    elif action_type == 'play':
                        items.append((mi, 'PlayMedia(%s)' % sctop._create_plugin_url(action)))
                    else:
                        items.append((mi, 'RunPlugin(%s)' % sctop._create_plugin_url(action)))
                else:
                    items.append((mi, 'RunPlugin(%s)' % sctop._create_plugin_url(action)))
        if len(items) > 0:
            liz.addContextMenuItems(items)
        return xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]), url=sctop._create_plugin_url(params),
                                           listitem=liz, isFolder=True)

    def render_video(self,item):
        #util.debug("_render_video")
        
        params = self.params()
        params.update({'play':item['url'],'dtitle':item['title']})
        #for k,v in item.iteritems():
        #    params.update({k: str(v)})
        downparams = self.params()
        if item.get('originaltitle_seo'):
            downparams.update({'title':"%s%s" % (item['originaltitle_seo'], item['extension']), 'down':item['url']})
        else:
            downparams.update({'title':"%s.%s" % (item['title'], 'mp4'), 'down':item['url']})
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
        #util.debug("menuItems: %s" % str(menuItems))
        self.add_video(title,
                params,
                item['img'],
                infoLabels=item,
                menuItems=menuItems
                )
        

    def getTraktLastActivity(self, typ='movie'):
        res = []
        try:
            if trakt.getTraktCredentialsInfo() == True:
                if sctop.traktlistlast is None:
                    loc = self.cache.get('lastActivity')
                    rem = str(trakt.getWatchedActivity())
                    util.debug("[SC] loc: [%s] rem: [%s]" % (loc, rem))
                    if loc is None or rem != loc:
                        self.cache.set('lastActivity', str(rem))
                        alres = {'movie': trakt.syncMovies(), 'series': trakt.syncTVShows()}
                        self.cache.set('LastActivityList', repr(alres))
                    else:
                        alres = eval(self.cache.get('LastActivityList'))
                else:
                    alres = sctop.traktlistlast
                sctop.traktlistlast = alres
                res = alres.get(typ)
        except:
            util.debug('[SC] getTraktLastActivity ERR: %s' % str(traceback.format_exc()) )
            pass
        util.debug('[SC] getTraktLastActivity ret: %s' % str(res) )
        return res

    def add_video(self, name, params={}, logo='', infoLabels={}, menuItems={}):
        util.debug("_add_video")
        #util.debug("[SC] add video info: %s" % str(infoLabels))
        _infoLabels=self._extract_infolabels(infoLabels)
        name = util.decode_html(name)
        if 'Title' not in _infoLabels:
            _infoLabels['Title'] = name
        util.debug("[SC] params: %s" % str(params))
        url = sctop._create_plugin_url(params)
        if logo == '' or logo is None:
            logo = self.noImage
        li = xbmcgui.ListItem(name, path=url, iconImage='DefaultVideo.png', thumbnailImage=logo)
        li.setInfo(type='Video', infoLabels=_infoLabels)
        mt = sctop.getMediaType()
        util.debug("[SC] item media type: %s" % mt)

        if 'selected' in infoLabels.keys():
            wnd = xbmcgui.Window(xbmcgui.getCurrentWindowId())
            util.debug("[SC] wnd: %s [%d]" % (str(wnd), xbmcgui.getCurrentWindowId()))
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
        
        self.setUniq(li, infoLabels)
        
        for mi in menuItems.keys():
            action = menuItems[mi]
            if not type(action) == type({}):
                items.append((mi, action))
            else:
                if 'action-type' in action:
                    action_type = action['action-type']
                    del action['action-type']
                    if action_type == 'list':
                        items.append((mi, 'Container.Update(%s)' % sctop._create_plugin_url(action)))
                    elif action_type == 'play':
                        items.append((mi, 'PlayMedia(%s)' % sctop._create_plugin_url(action)))
                    elif action_type == 'trailer':
                        items.append((mi, 'PlayMedia(%s)' % action['url']))
                    else:
                        items.append((mi, 'RunPlugin(%s)' % sctop._create_plugin_url(action)))
                else:
                    items.append((mi, 'RunPlugin(%s)' % sctop._create_plugin_url(action)))

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
        sctop.sleep(sleep_time)

    def service(self):
        util.info("SC Service Started")
        #dialog = sctop.dialog.textviewer('heading', 'Prosim podporte vyvoj pluginu na adrese: http://stream-cinema.online/')
        if sctop.player is None:
            sctop.player = myPlayer.MyPlayer(parent=self)
        try:
            sleep_time = int(self.getSetting("start_sleep_time")) * 1000 * 60
        except:
            sleep_time = self.sleep_time
            pass

        util.debug("[SC] start delay: %s" % str(sleep_time))
        self.sleep(sleep_time)
        util.debug("[SC] sleep end")

        try:
            self.last_run = float(self.cache.get("subscription.last_run"))
        except:
            self.last_run = time.time()
            self.cache.set("subscription.last_run", str(self.last_run))
            pass
        
        util.debug("[SC] last_rum: %s" % str(self.last_run))

        if not xbmc.abortRequested and time.time() > self.last_run:
            self.evalSchedules()

        self.sleep_time = 100
        while not xbmc.abortRequested:
            if(time.time() > self.last_run + 600):
                self.evalSchedules()
                self.last_run = time.time()
                self.cache.set("subscription.last_run", str(self.last_run))
            self.sleep(self.sleep_time)
        util.info("[SC] Shutdown")
    
    def findSubtitles(self, stream):
        try:
            if not self.getSetting('subtitles') == 'true': 
                raise Exception()
            imdb = stream['imdb']
            season = None
            episode = None
            if 'season' in stream:
                season = stream['season']
            if 'episode' in stream:
                episode = stream['episode']

            util.debug("[SC] Hladam titulky")
            langDict = {'Afrikaans': 'afr', 'Albanian': 'alb', 'Arabic': 'ara', 'Armenian': 'arm', 
                'Basque': 'baq', 'Bengali': 'ben', 'Bosnian': 'bos', 'Breton': 'bre', 
                'Bulgarian': 'bul', 'Burmese': 'bur', 'Catalan': 'cat', 'Chinese': 'chi', 
                'Croatian': 'hrv', 'Czech': 'cze', 'Danish': 'dan', 'Dutch': 'dut', 'English': 'eng', 
                'Esperanto': 'epo', 'Estonian': 'est', 'Finnish': 'fin', 'French': 'fre', 
                'Galician': 'glg', 'Georgian': 'geo', 'German': 'ger', 'Greek': 'ell', 
                'Hebrew': 'heb', 'Hindi': 'hin', 'Hungarian': 'hun', 'Icelandic': 'ice', 
                'Indonesian': 'ind', 'Italian': 'ita', 'Japanese': 'jpn', 'Kazakh': 'kaz', 
                'Khmer': 'khm', 'Korean': 'kor', 'Latvian': 'lav', 'Lithuanian': 'lit', 
                'Luxembourgish': 'ltz', 'Macedonian': 'mac', 'Malay': 'may', 'Malayalam': 'mal', 
                'Manipuri': 'mni', 'Mongolian': 'mon', 'Montenegrin': 'mne', 'Norwegian': 'nor', 
                'Occitan': 'oci', 'Persian': 'per', 'Polish': 'pol', 'Portuguese': 'por,pob', 
                'Portuguese(Brazil)': 'pob,por', 'Romanian': 'rum', 'Russian': 'rus', 'Serbian': 'scc', 
                'Sinhalese': 'sin', 'Slovak': 'slo', 'Slovenian': 'slv', 'Spanish': 'spa', 
                'Swahili': 'swa', 'Swedish': 'swe', 'Syriac': 'syr', 'Tagalog': 'tgl', 'Tamil': 'tam', 
                'Telugu': 'tel', 'Thai': 'tha', 'Turkish': 'tur', 'Ukrainian': 'ukr', 'Urdu': 'urd'}

            codePageDict = {'ara': 'cp1256', 'ar': 'cp1256', 'cs': 'cp1250', 'ell': 'cp1253', 
                'el': 'cp1253', 'heb': 'cp1255', 'he': 'cp1255', 'sk': 'cp1250', 'tur': 'cp1254', 
                'tr': 'cp1254', 'rus': 'cp1251', 'ru': 'cp1251'}

            quality = ['bluray', 'hdrip', 'brrip', 'bdrip', 'dvdrip', 'webrip', 'mhd', 'hdtv']

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

    def getSubs(self):
        if self.subs is not None:
            return self.subs
        data = self.cache.get("subscription")
        try:
            if data == '':
                subs = {}
            else:
                subs = eval(data)
            self.subs = subs
        except Exception, e:
            util.error(e)
            subs = {}
        return subs

    def setSubs(self, subs):
        self.subs = subs
        self.cache.set("subscription", repr(subs))

    def getResumePoint(self):
        data = self.cache.get("resume_point")
        try:
            if data == '' or data is None:
                last = []
            else:
                last = eval(data)
        except Exception, e:
            last = []
        util.debug("[SC] getResumePoints %s" % str(last))
        return last
        
    def setResumePoint(self, data):
        util.debug("[SC] setResumePoint %s" % str(data))
        self.cache.set("resume_point", repr(data))
        
    def getLast(self):
        data = self.cache.get("last")
        try:
            if data == '' or data is None:
                last = []
            else:
                last = eval(data)
        except Exception, e:
            last = []
        util.debug("[SC] getLast %s" % str(last))
        return last
        
    def setLast(self, last):
        util.debug("[SC] setLast %s" % str(last))
        self.cache.set("last", repr(last))

    def addLast(self, scid):
        last = self.getLast()
        util.debug("[SC] addLast %s -> %s" % (str(scid), str(last)))
        if scid in last:
            last.remove(scid)
        last.insert(0, scid)
        remove = len(last) - 20
        if remove > 0:
            for i in range(remove):
                last.pop()
        self.setLast(last)

buggalo.SUBMIT_URL = sctop.submiturl
