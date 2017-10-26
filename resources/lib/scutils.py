# -*- coding: utf-8 -*-
import base64
import bug
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
from dialogselect import DialogSelect
from collections import defaultdict
from provider import ResolveException
from datetime import timedelta

class KODISCLib(xbmcprovider.XBMCMultiResolverContentProvider):
    last_run = 0
    sleep_time = 1000 * 1 * 60
    subs = None
    mPlayer = None
    force = False
    system = None

    def __init__(self, provider, settings, addon):
        xbmcprovider.XBMCMultiResolverContentProvider.__init__(self, provider, settings, addon)
        provider.parent = self
        sctop.uid = provider.uid
        self.provider = provider
        self.win = xbmcgui.Window(10000)
        self.noImage = os.path.join(self.addon_dir(), 'resources', 'img', 'no-image.png')
        #self._settings()
        self.cache = sctop.cache
        self.provider.cache = self.cache
        self.timer = 0

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

    @bug.buggalo_try_except({'method': 'scutils.run'})
    def run(self, params):
        if params == {} or params == self.params():
            return self.root()
        if 'list' in params.keys() and params['list'] != '':
            self.list(self.provider.list(params['list']))
            if self.system is not None:
                self.provider.system(self.system, True)
            return self.endOfDirectory()
        if 'down' in params.keys():
            self.force = True
            return self.download({'url': params['down'], 'title': params['title'], 'force': '1'})
        if 'play' in params.keys():
            return self.play({'url': params['play'], 'info': params})
        if 'search-list' in params.keys():
            return self.search_list()
        if 'search' in params.keys():
            return self.do_search(params['search'])
        if 'search-remove' in params.keys():
            return self.search_remove(params['search-remove'])
        if 'search-edit' in params.keys():
            return self.search_edit(params['search-edit'])
        if self.run_custom:
            return self.run_custom(params)
    
    def endOfDirectory(self, succeeded=True, cacheToDisc=True):
        #util.debug("[SC] endOfDirectory %s %s" % (str(succeeded), str(cacheToDisc)))
        return xbmcplugin.endOfDirectory(int(sys.argv[1]), succeeded=succeeded, cacheToDisc=cacheToDisc)

    @bug.buggalo_try_except({'method': 'scutils.add_item_to_library'})
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
                    util.error('[SC] Failed to create directory 1: ' + dir)

            if not xbmcvfs.exists(item_path):
                try:
                    file_desc = xbmcvfs.File(item_path, 'w')
                    file_desc.write(str(item_url))
                    file_desc.close()
                    new = True
                except Exception, e:
                    util.error('[SC] Failed to create .strm file: ' + item_path + " | " + str(e))
                    error = True
        else:
            error = True
        
        util.debug("[SC] add item: %s" % item_path)
        return (error, new)
    
    @bug.buggalo_try_except({'method': 'scutils._link'})
    def _link(self, params):
        arg = {"play": "/Play/%d" % int(params['id']), "title": params['title']}
        if 'season' in params:
            arg.update({"play":"/Play/%d/%d/%d" % (int(params['id']), int(params['season']), int(params['episode']))})
        return sctop._create_plugin_url(arg, 'plugin://%s/' % sctop.__scriptid__)
    
    @bug.buggalo_try_except({'method': 'scutils.add_multi_item'})
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
                #util.info("percento: %d" % int(perc))
                if dialog.iscanceled():
                    return
                
                try:
                    dialog.update(int(perc), "%s / %s - %s" % (str(page), str(data['total']), i['title']))
                except Exception:
                    util.debug('[SC] ERR: %s' % str(traceback.format_exc()) )
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
        elif error and not ('notify' in params):
            self.showNotification('Failed, Please check kodi logs', 'Linking')
    
    @bug.buggalo_try_except({'method': 'scutils.movieinfo'})
    def movienfo(self, data):
        out = ''
        if 'imdb' in data and data['imdb'] is not None and int(data['imdb']) > 0:
            out += "http://www.imdb.com/title/tt%07d/\n" % int(data['imdb'])
        if 'tmdb' in data and data['tmdb'] is not None and int(data['tmdb']) > 0:
            out += "https://www.themoviedb.org/movie/%d/\n" % int(data['tmdb'])
        if 'csfd' in data and data['csfd'] is not None and int(data['csfd']) > 0:
            out += "http://www.csfd.cz/film/%d-\n" % int(data['csfd'])
        if 'tvdb' in data and data['tvdb'] is not None and int(data['tvdb']) > 0:
            out += "http://thetvdb.com/index.php?tab=series&id=%d\n" % int(data['tvdb'])
            
        util.debug("XML: %s" % out)
        return str(out)
    
    @bug.buggalo_try_except({'method': 'scutils.add_item_trakt'})
    def add_item_trakt(self, params):
        if trakt.getTraktCredentialsInfo() == True:
            util.debug("[SC] add_item_trakt: %s" % str(params))
            ids = trakt.getList(params['tl'])
            data = self.provider._json(self.provider._url("/Search/"), {'ids': json.dumps(ids)})
            if 'menu' in data:
                error = False
                new = False
                e = False
                n = False
                
                dialog = sctop.progressDialog
                dialog.create('Stream Cinema CZ & SK', 'Add all to library')
                total = float(len(data['menu']))
                num = 0
                for i in data['menu']:
                    num += 1
                    perc = float(num / total) * 100
                    #util.info("percento: %d - (%d / %d)" % (int(perc), int(num), int(total)))
                    if dialog.iscanceled():
                        return                    
                    try:
                        dialog.update(int(perc), "%s" % (i['title']))
                    except Exception:
                        util.debug('[SC] ERR: %s' % str(traceback.format_exc()) )
                        pass
                    (e, n) = self.add_item({'notify':False,'id':i['id']}, False)
                        
                    error |= e
                    new |= n
                if not error and new:
                    self.showNotification(self.getString(30901), 'New content')
                    xbmc.executebuiltin('UpdateLibrary(video)')
                elif not error:
                    self.showNotification(self.getString(30901), 'No new content')
                elif error:
                    self.showNotification('Failed, Please check kodi logs', 'Linking')
    
    def add_item_lastrun(self, ids):
        error = False
        new_items = False
        data = self.provider._json("%s/Lib/multi" % sctop.BASE_URL, {"ids": json.dumps(ids)})
        if data:
            for i in data:
                self.add_item({'notifi':1}, data=i)
                    
    @bug.buggalo_try_except({'method': 'scutils.add_item'})
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

    @bug.buggalo_try_except({'method': 'scutils.canCheck'})
    def canCheck(self, last_run):
        next_check = last_run + ((sctop.getSettingAsInt('refresh_time') + 3600) * 3600 * 24)
        return next_check < time.time()
    
    @bug.buggalo_try_except({'method': 'scutils.csearch'})
    def csearch(self, params):
        util.debug("[SC] vyhladavanie: %s " % str(params))
        kb = sctop.keyboard()
        kb.doModal()
        if kb.isConfirmed():
            what = kb.getText()
            self.list(self.provider.search(what, params['id']))
            return self.endOfDirectory()
    
    @bug.buggalo_try_except({'method': 'scutils.evalSchedules'})
    def evalSchedules(self,force=False):
        try:
            if not self.scanRunning() and not self.isPlaying():
                notified = False
                util.info("[SC] Loading subscriptions")
                subs = self.getSubs()
                util.debug("[SC] Subs: %s" % str(subs))
                new_items = False
                ids = {}
                total = len(subs)
                num = 0
                
                if force is True:
                    dialog = sctop.progressDialog
                    dialog.create('Stream Cinema CZ & SK', 'Add all to library')
                    
                for iid, data in subs.iteritems():
                    num += 1
                    if force and dialog:
                        perc = 100 * num / total
                        #util.info("percento: %s %d %d" % (str(perc), int(num), int(total)))
                        if dialog.iscanceled():
                            self.setSubs(subs)
                            return
                        
                        try:
                            dialog.update(int(perc))
                        except Exception:
                            util.debug('[SC] ERR: %s' % str(traceback.format_exc()) )
                            pass
                        
                    util.debug("[SC] sub id: %s" % str(iid))
                    if xbmc.abortRequested:
                        util.info("[SC] Exiting")
                        return
                    
                    if self.scanRunning() or self.isPlaying():
                        self.cache.delete("subscription.last_run")
                        return
                    
                    if iid == 'movie':
                        util.debug("[SC] movie nepokracujem")
                        continue
                        
                    if self.canCheck(data['last_run']):
                        if not notified:
                            self.showNotification('Subscription', 'Chcecking')
                            notified = True
                        util.debug("[SC] Refreshing %s" % str(iid))
                        ids.update({iid:data['last_run']})
                        if len(ids) >= 20:
                            self.add_item_lastrun(ids)
                            ids = {}
                        data['last_run'] = time.time()
                        subs[iid] = data
                        self.setSubs(subs)
                        
                if len(ids) > 0:
                    self.add_item_lastrun(ids)

                if sctop.getSettingAsBool('download-movies'):
                    if 'movie' in subs:
                        data = subs['movie']
                    else:
                        data = {'last_run': time.time()}

                    util.debug("[SC] data: %s" % str(data))

                    if self.canCheck(data['last_run']) or force is True:
                        util.debug("[SC] movie stahujeme")
                        data['last_run'] = time.time()
                        subs['movie'] = data
                        self.setSubs(subs)
                        self.add_multi_item({'id':'movies'}, False)
                    else:
                        util.info("[SC] movie netreba stahovat")
                else:
                    util.info("[SC] movie library disabled")

                if new_items:
                    xbmc.executebuiltin('UpdateLibrary(video)')
                notified = False
            else:
                util.info("[SC] Scan skipped")
        except:
            util.debug('[SC] ERR: %s' % str(traceback.format_exc()) )
            pass

    @bug.buggalo_try_except({'method': 'scutils.getTVDB'})
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

    @bug.buggalo_try_except({'method': 'scutils.normalize_filename'})
    def normalize_filename(self, name, validChars=None):
        validFilenameChars = "-_.() %s%s" % (string.ascii_letters, string.digits)
        if (validChars is not None):
            validFilenameChars = validChars
        cleanedFilename = self.encode(name)
        ret = ''.join(c for c in cleanedFilename if c in validFilenameChars)
        return ret if ret != '' else ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(8))

    @bug.buggalo_try_except({'method': 'scutils.showNotification'})
    def showNotification(self, title, message, time=1000):
        xbmcgui.Dialog().notification(self.encode(title), self.encode(message), time=time,
                                      icon=xbmc.translatePath(self.addon_dir() + "/icon.png"),
                                      sound=False)
    
    @bug.buggalo_try_except({'method': 'scutils.run_custom'})
    def run_custom(self, params):
        util.debug("RUN CUSTOM: %s" % str(params))
        if 'action' in params:
            util.debug("ACTION: %s" % str(params['action']))  
            action = params['action']
            subs = False
            if action == 'remove-from-sub':
                subs = self.getSubs()
                util.debug("[SC] subs: %s" % str(subs))
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
            if action == 'add-to-lib-trakt':
                self.add_item_trakt(params)
                return
            if action == 'subs':
                #xbmc.executebuiltin("ActivateWindow(busydialog)")
                self.evalSchedules(force=True)
                #xbmc.executebuiltin("Dialog.Close(busydialog)")
                sctop.openSettings('5.10')
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
                return self.endOfDirectory()
            if action == 'traktShowList':
                if trakt.getTraktCredentialsInfo() == True:
                    util.debug("[SC] params: %s" % str(params))
                    ids = trakt.getList(params['id'])
                    self.list(self.provider.items(None, self.provider._json("/Search/", {'ids': json.dumps(ids)})))
                return self.endOfDirectory()
            if action == 'authTrakt':
                trakt.authTrakt()
            if action == 'speedtest': #                               1:350    2:500    3:750  4:1000 5:1500   6:2000   7:2500 8:3000  9:3500   10:4000
                g = sctop.getString
                x = [g(30551), g(30552), g(30553), g(30554), g(30555), 
                    g(30556), g(30557), g(30558), g(30559), g(30560)]
                ret = [1500, 2000]
                run = 4
                try:
                    ret =sctop.dialog.multiselect(g(30501), x, preselect=[5,6])
                except:
                    try:
                        xret = sctop.dialog.select(g(30501), x)
                        run = 8
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
                sctop.setSetting('bitrate', int(wsdown))
                sctop.setSetting('bitrateformated', str(pretty_speed(wsdown)))
                sctop.dialog.ok(g(30050), "%s: %s" % (wspeedtest.host, str(pretty_speed(wsdown))), "%s: %s" % (speedtest.host, str(pretty_speed(bedown))))
                sctop.openSettings('1.0')
            if action == 'play-force':
                self.force = True;
                try :
                    self.play({'url': params['play'], 'info': params})
                except:
                    util.debug("[SC] ERROR: %s" % str(traceback.format_exc()))
                    pass
                util.debug("[SC] ----------------------------------------")
            if action == 'trakt':
                movies = self.getTraktLastActivity('series') #trakt.getWatchedActivity()
                util.debug("[SC] movies: %s" % str(movies))
            if action == 'csearch':
                return self.csearch(params)
            if action == 'search-actor':
                self.list(self.provider.items(self.provider._url("/Search/actor?%s" % urllib.urlencode({'id':params['id'], 'type': params['subtype']}))))
                return self.endOfDirectory()
            if action == 'info':
                #metahandler
                #from metahandler import TMDB
                #tmdb = TMDB.TMDB(tmdb_api_key='6889f6089877fd092454d00edb44a84d', omdb_api_key='ea23cea2', lang='cs')
                #cnf = tmdb.call_config()
                #meta = tmdb._get_cast(params['imdb'])
                #from metahandler import metahandlers
                #metaget = metahandlers.MetaData(prepack_images=True, preparezip=False)
                #meta = metaget.get_meta('movie', name='', imdb_id=params['imdb'])
                #util.debug("[SC] conf: %s" % str(cnf))
                #util.debug("[SC] meta: %s" % str(meta))
                xbmc.executebuiltin('Action("Info")')
                return
                dialog = xbmcgui.WindowXMLDialog('DialogSelect.xml', xbmcaddon.Addon().getAddonInfo('path').decode('utf-8'), 'default', '1080p')
                dialog.doModal()
                del dialog
            if action == 'test':
                self.evalSchedules()
                #data = myPlayer.MyPlayer.executeJSON({'jsonrpc': '2.0', 'id': 0, 'method': 'VideoLibrary.GetMovies', 'params': {'properties': ['title', 'imdbnumber', 'year', 'playcount', 'lastplayed', 'file', 'dateadded', 'runtime', 'userrating']}})
                #util.debug("[SC] RPC: %s" % str(json.dumps(data)))
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

    @bug.buggalo_try_except({'method': 'scutils.setUniq'})
    def setUniq(self, li, stream):
        uniq = {}
        if 'imdb' in stream and stream['imdb'] == 0:
            #util.debug("[SC] uniq imdb %s" % stream['imdb'])
            uniq.update({'imdb': stream['imdb']})
            li.setProperty('IMDBNumber', stream['imdb']);
        if 'tmdb' in stream and stream['tmdb'] == 0:
            #util.debug("[SC] uniq tmdb %s" % stream['tmdb'])
            uniq.update({'tmdb': stream['tmdb']})
            li.setProperty('TMDBNumber', stream['tmdb']);
        if 'tvdb' in stream and stream['tvdb'] == 0:
            #util.debug("[SC] uniq tvdb %s" % stream['tvdb'])
            uniq.update({'tvdb': stream['tvdb']})
            li.setProperty('TVDBNumber', stream['tvdb']);
        if 'csfd' in stream:
            #util.debug("[SC] uniq csfd %s" % stream['csfd'])
            uniq.update({'csfd': stream['csfd']})
            li.setProperty('CSFDNumber', stream['csfd']);
        if 'trakt' in stream and stream['trakt'] == 0:
            #util.debug("[SC] uniq trakt %s" % stream['trakt'])
            uniq.update({'trakt': stream['trakt']})
            li.setProperty('TRAKTNumber', stream['trakt']);

        try:
            li.setUniqueIDs(uniq)
            #util.debug("[SC] uniq id: %s" % str(uniq))
        except Exception:
            util.debug("[SC] uniq err: %s" % str(traceback.format_exc()))
            pass

    @bug.buggalo_try_except({'method': 'scutils.list'})
    def list(self, items):
        params = self.params()
        for item in items:
            if item['type'] == 'dir':
                self.render_dir(item)
            elif item['type'] == 'next':
                params.update({'list': item['url']})
                xbmcutil.add_dir(xbmcutil.__lang__(30007), params, xbmcutil.icon('next.png'))
            elif item['type'] == 'prev':
                params.update({'list': item['url']})
                xbmcutil.add_dir(xbmcutil.__lang__(30008), params, xbmcutil.icon('prev.png'))
            elif item['type'] == 'new':
                params.update({'list': item['url']})
                xbmcutil.add_dir(xbmcutil.__lang__(30012), params, xbmcutil.icon('new.png'))
            elif item['type'] == 'top':
                params.update({'list': item['url']})
                xbmcutil.add_dir(xbmcutil.__lang__(30013), params, xbmcutil.icon('top.png'))
            elif item['type'] == 'video':
                self.render_video(item)
            else:
                self.render_default(item)
    
    @bug.buggalo_try_except({'method': 'scutils.play'})
    def play(self, item):
        util.debug("PLAY ITEM: %s" % str(item))
        if 'info' in item and 'force' in item['info'] or 'force' in item:
            self.force = True
        stream = self.resolve(item['url'])
        
        if stream and 'id' in stream:
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
                #util.debug("IL: %s" % str(il))
            
            if (stream['subs'] == '' or stream['subs'] is None) and stream['lang'].strip()[:2] not in ['CZ', 'SK']:
                #util.debug(stream)
                stream['subs'] = self.findSubtitles(stream)
                
            if stream['subs'] == '' or stream['subs'] == 'internal' or stream['subs'] == 'disabled':
                stream.remove('subs')
            
            try:
                if 'subs' in stream and stream['subs'] != '' and stream['subs'] is not None:
                    #util.debug("Seturnm titulky: " + str(stream['subs']))
                    li.setSubtitles([stream['subs']])
            except:
                pass
            self.win.setProperty(sctop.__scriptid__, sctop.__scriptid__)
            util.debug("[SC] mozem zacat prehravat %s" % str(stream))
            if self.force == True:
                return xbmc.Player().play(stream['url'], li, False, -1)
            util.debug("[SC] setResolvedUrl")
            xbmcplugin.setResolvedUrl(int(sys.argv[1]), True, li)
        else:
            li = xbmcgui.ListItem(path=item['url'])
            xbmcplugin.setResolvedUrl(int(sys.argv[1]), False, li)
            util.debug('[SC] ERR play strem %s' % str(stream))
            pass
        
    def _settings(self):
        return
        sp = os.path.join(self.addon_dir(), 'resources', 'settings.xml')
        itm = json.loads(util.request(scinema.BASE_URL + '/json/settings'))
        self.sett = "";
        self._parse_settings(itm['items'])
        util.info('SET: ' + self.sett);

    @bug.buggalo_try_except({'method': 'scutils._extract_infolabels'})
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
                    #util.debug("[SC] oznacujem za videne z trakt.tv %s" % str(item))
                    infoLabels['playcount'] = 1
                #util.debug("[SC] item ma imdb %s" % str(item.get('imdb')))
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

    @bug.buggalo_try_except({'method': 'scutils.render_dir'})
    def render_dir(self,item):
        params = self.params()
        params.update(item)
        if 'url' in item:
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

    @bug.buggalo_try_except({'method': 'scutils.add_dir'})
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
            #wnd = xbmcgui.Window(xbmcgui.getCurrentWindowId())
            #util.debug("[SC] wnd: %s [%d]" % (str(wnd), xbmcgui.getCurrentWindowId()))
            pass
            
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

    @bug.buggalo_try_except({'method': 'scutils.render_video'})
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
        
    @bug.buggalo_try_except({'method': 'scutils.getTaraktLastActitivy'})
    def getTraktLastActivity(self, typ='movie'):
        res = []
        try:
            if trakt.getTraktCredentialsInfo() == True:
                if sctop.traktlistlast is None:
                    loc = self.cache.get('lastActivity')
                    rem = str(trakt.getWatchedActivity())
                    #util.debug("[SC] loc: [%s] rem: [%s]" % (loc, rem))
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
        #util.debug('[SC] getTraktLastActivity ret: %s' % str(res) )
        return res
    
    @bug.buggalo_try_except({'method': 'scutils.add_video'})
    def add_video(self, name, params={}, logo='', infoLabels={}, menuItems={}):
        #util.debug("_add_video")
        #util.debug("[SC] add video info: %s" % str(infoLabels))
        _infoLabels=self._extract_infolabels(infoLabels)
        name = util.decode_html(name)
        if 'Title' not in _infoLabels:
            _infoLabels['Title'] = name
        #util.debug("[SC] params: %s" % str(params))
        url = sctop._create_plugin_url(params)
        if logo == '' or logo is None:
            logo = self.noImage
        li = xbmcgui.ListItem(name, path=url, iconImage='DefaultVideo.png', thumbnailImage=logo)
        li.setInfo(type='Video', infoLabels=_infoLabels)
        mt = sctop.getMediaType()
        #util.debug("[SC] item media type: %s" % mt)

        if 'selected' in infoLabels.keys():
            wnd = xbmcgui.Window(xbmcgui.getCurrentWindowId())
            #util.debug("[SC] wnd: %s [%d]" % (str(wnd), xbmcgui.getCurrentWindowId()))
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

    @bug.buggalo_try_except({'method': 'scutils.service'})
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
        start = 0
        while not xbmc.abortRequested and start < sleep_time:
            self._player()
            start += 1000
            sctop.sleep(1000)
        del start

        util.debug("[SC] start sleep end")

        try:
            self.last_run = float(self.cache.get("subscription.last_run"))
        except:
            self.last_run = time.time()
            self.cache.set("subscription.last_run", str(self.last_run))
            pass
        
        util.debug("[SC] last_rum: %s" % str(self.last_run))

        if not xbmc.abortRequested and time.time() > self.last_run:
            self.evalSchedules()

        self.sleep_time = 1000
        while not xbmc.abortRequested:
            self._player()
            self._sheduler()
            sctop.sleep(self.sleep_time)
        del sctop.player
        util.info("[SC] Shutdown")
        
    def _player(self):
        try:
            if not xbmc.abortRequested and sctop.player.isPlayingVideo() and sctop.player.scid > 0:
                notificationtime = 30
                playTime = sctop.player.getTime()
                totalTime = sctop.player.getTotalTime()
                sctop.player.watchedTime = playTime
                self.timer += 1
                if self.timer >= 600:
                    sctop.player.waitForChange()
                    self.timer = 0
                    data = {'scid': sctop.player.scid, 'action': 'ping', 'prog': sctop.player.timeRatio()}
                    sctop.player.action(data)
                
                util.debug("[SC] upNext [%s] " % str((totalTime - playTime) <= int(notificationtime)))
                showupnext = sctop.getSettingAsBool("show_up_next")
                if showupnext and (totalTime - playTime) <= int(notificationtime):
                    sctop.player.upNext()
        except Exception, e:
            bug.onExceptionRaised(e)
            util.debug("[SC] _player e: %s" % str(e))
            pass
        
    def _sheduler(self):
        try:
            if time.time() > self.last_run + 600:
                self.evalSchedules()
                self.last_run = time.time()
                self.cache.set("subscription.last_run", str(self.last_run))
        except:
            pass

    @bug.buggalo_try_except({'method': 'scutils.findSubtitles'})
    def findSubtitles(self, stream):
        try:
            if not self.getSetting('subtitles') == 'true' or stream['sinfo'] == True: 
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

            util.debug("[SC] subtitles: %s" % str(filter[0]))
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

    @bug.buggalo_try_except({'method': 'scutils.getSubs'})
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
    
    @bug.buggalo_try_except({'method': 'scutils.setSubs'})
    def setSubs(self, subs):
        self.subs = subs
        util.debug("[SC] set subs %s" % str(subs))
        self.cache.set("subscription", repr(subs), expiration=timedelta(days=365))

    @bug.buggalo_try_except({'method': 'scutils.getResumePoint'})
    def getResumePoint(self):
        data = self.cache.get("resume_point2")
        try:
            if data == '' or data is None:
                last = {}
            else:
                last = eval(data)
        except:
            last = {}
        util.debug("[SC] getResumePoints %s" % str(last))
        return last
    
    @bug.buggalo_try_except({'method': 'scutils.setResumePoint'})
    def setResumePoint(self, data):
        util.debug("[SC] setResumePoint %s" % str(data))
        self.cache.set("resume_point2", repr(data))
    
    def cacheMigrate(self):
        util.debug("[SC] cacheMigrate start")
        sctop.setSetting("cachemigrate", "true")
        try:
            import StorageServer
            cache = StorageServer.StorageServer(sctop.__scriptname__, 24)
            data = cache.get("last")
            util.debug("[SC] cacheMigrate data")
            if not (data == '' or data is None):
                util.debug("[SC] cacheMigrate eval")
                last = eval(data)
                self.setLast(last)
        except Exception, e:
            util.debug("[SC] migrate err: %s" % str(traceback.format_exc()))
            pass
    
    @bug.buggalo_try_except({'method': 'scutils.getLast'})
    def getLast(self):
        data = self.cache.get("last")
        try:
            if data == '' or data is None:
                last = []
            else:
                last = eval(data)
        except:
            last = []
        util.debug("[SC] getLast %s" % str(last))
        return last
    
    @bug.buggalo_try_except({'method': 'scutils.setLast'})
    def setLast(self, last):
        util.debug("[SC] setLast %s" % str(last))
        self.cache.set("last", repr(last), expiration=timedelta(days=365))

    @bug.buggalo_try_except({'method': 'scutils.addLast'})
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

    @bug.buggalo_try_except({'method': 'scutils.filter_bitrate'})
    def filter_bitrate(self, resolved):
        bt = sctop.getSettingAsInt('bitrate')
        if bt > 0 and sctop.getSettingAsBool('bitratefilter'):
            tmp = []
            for s in resolved:
                util.debug("[SC] bitrate video %s vs %s" % (str(s.get('bitrate', 0)), str(bt)))
                if int(s.get('bitrate', 0)) <= bt:
                    util.debug("[SC] pridavam BT %s" % str(s.get('bitrate', 0)))
                    tmp.append(s)
                else:
                    util.debug("[SC] pomaly net pre BT %s" % str(s.get('bitrate', 0)))
            if len(tmp) > 1:
                resolved = tmp
            
        return resolved
    
    @bug.buggalo_try_except({'method': 'scutils._filter_lang'})
    def _filter_lang(self, resolved, lang, prio):
        import re

        tmp = []
        util.debug("[SC] filter lang %s" % str(lang))
        for s in resolved:
            if s['quality'] == '3D-SBS':
                continue
            if 'lang' in s and s['lang'] != '' and s['lang'] == lang:
                util.debug("[SC] pridavam stream s jazykom %s" % str(lang))
                tmp.append(s)
        
        if prio == True and len(tmp) > 1:
            tmpq = self.filter_quality(tmp, False)
            if len(tmpq) >= 1:
                util.debug("[SC] vyberame najlepsi stream z %s" % str(tmpq))
                return [tmpq[0]]
        elif len(tmp) == 1:
            return tmp
        
        return [] if prio == True else resolved
    
    @bug.buggalo_try_except({'method': 'scutils.filter_lang'})
    def filter_lang(self, resolved, prio = False):
        if sctop.getSettingAsBool('filter_audio') == False:
            util.debug("[SC] nemame zapnute filtrovanie podla audia")
            return resolved
        
        util.debug("[SC] lang.1 %s" % sctop.getSetting('filter_lang.1'))
        tmp = self._filter_lang(resolved, sctop.getSetting('filter_lang.1'), prio)
        if len(tmp) == 0:
            util.debug("[SC] lang.2 %s" % sctop.getSetting('filter_lang.2'))
            tmp = self._filter_lang(resolved, sctop.getSetting('filter_lang.2'), prio)
            
        if len(tmp) == 1:
            util.debug("[SC] mame vybrany len jeden stream %s" % str(tmp))
            return tmp
        
        if len(tmp) >= 1 and prio == False:
            util.debug("[SC] prioprita podla videa, vyberame prvy stream s audiom")
            resolved = [tmp[0]]

        return resolved
    
    @bug.buggalo_try_except({'method': 'scutils.filter_quality'})
    def filter_quality(self, resolved, prio = False):
        if sctop.getSettingAsBool('filter_video') == False:
            util.debug("[SC] nemame zapnute filtrovanie podla kvality videa")
            return resolved
        
        res = sctop.getSetting('filter_quality')
        util.debug("[SC] filter kvality nastaveny na %s" % str(res))
        sources = {}
        for item in resolved:
            if item['quality'] == '3D-SBS':
                continue
                
            if item['quality'] in sources.keys():
                sources[item['quality']].append(item)
            else:
                sources[item['quality']] = [item]
  
        if prio == True and res in sources:
            return self.filter_lang(sources[res])
  
        if prio == False and res in sources:
            util.debug('[SC] mame prioritu vyberame prvy stream s videom pre rozlisenie %s' % str(res))
            return [sources[res][0]]
        
        return resolved
    
    @bug.buggalo_try_except({'method': 'scutils.filter_hevc'})
    def filter_hevc(self, resolved):
        tmp = []
        for i in resolved:
            if not ('vinfo' in i and re.search('HEVC', i['vinfo'])):
                tmp.append(i)
        return tmp
    
    @bug.buggalo_try_except({'method': 'scutils.filter_priority'})
    def filter_priority(self, resolved):
        if sctop.getSettingAsBool('filter_enable') == False:
            util.debug("[SC] nemame zapnuty filter streamov, tak nic nefiltrujeme")
            return resolved
        
        if sctop.getSettingAsBool('filter_hevc'):
            resolved = self.filter_hevc(resolved)
        
        if sctop.getSettingAsBool('filter_audio') and not sctop.getSettingAsBool('filter_video'):
            return self.filter_lang(resolved, False)

        if not sctop.getSettingAsBool('filter_audio') and sctop.getSettingAsBool('filter_video'):
            return self.filter_quality(resolved, False)
        
        util.debug("[SC] pokusame sa filtrovat stream podla audia a kvality")
        if sctop.getSetting('filter_prio') == 'Audio':
            util.debug("[SC] priorita na audio stopu")
            resolved = self.filter_lang(resolved, True)
        else:
            util.debug("[SC] priorita na video stopu")
            resolved = self.filter_quality(resolved, True)
        
        return resolved

    @bug.buggalo_try_except({'method': 'scutils.filter_resolved'})
    def filter_resolved(self, resolved):
        resolved = self.filter_bitrate(resolved)
        resolved = self.filter_priority(resolved)    
        return resolved

    @bug.buggalo_try_except({'method': 'scutils.resolve'})
    def resolve(self, url):
        item = self.provider.video_item()
        item.update({'url': url})

        def select_cb(resolved):
            if len(resolved) > 1 and self.force == False:
                resolved = self.filter_resolved(resolved)
                
            if len(resolved) > 1 or self.force == True:
                if not sctop.getSettingAsBool('dialog_details'):
                    dialog = xbmcgui.Dialog()
                    opts = []
                    for r in resolved:
                        d = defaultdict(lambda: '', r)
                        if d['sinfo'] == True:
                            d['lang'] = '%s+tit' % d['lang']
                        opts.append('[B][%s] %s%s[/B] - %s%s' % (d['olang'], d['quality'], d['vinfo'], d['size'], d['ainfo']))
                    ret = dialog.select(resolved[0]['title'], opts)
                    ret = ret if ret != -1 else False
                    del dialog
                else:
                    listing = []
                    art = resolved[0]['art'] if 'art' in resolved[0] else None
                    img = art['poster'] if art is not None and 'poster' in art else None
                    for (p,r) in enumerate(resolved):
                        d = defaultdict(lambda: '', r)

                        listitem = xbmcgui.ListItem(
                            label='[B][%s] %s%s %s[/B] - %s%s' % (d['olang'], d['quality'], d['vinfo'], '', d['size'], d['ainfo']), 
                            label2=d['fname'], iconImage=img, thumbnailImage=img)
                        listitem.setProperty("pos", str(p))
                        listing.append(listitem)

                    dialog = DialogSelect("DialogSelect.xml", "", listing=listing, windowtitle=resolved[0]['title'], multiselect=False, getmorebutton=False, richlayout=True)
                    dialog.doModal()
                    item = dialog.result
                    del dialog
                    ret = int(item.getProperty('pos')) if item is not False else False
                util.debug("[SC] dialog ret: %s" % str(ret))
                if ret is not False:
                    util.debug("[SC] dialog resolved url: %s" % str(resolved[ret]['params']))
                    return resolved[ret]
                else:
                    util.debug('[SC] None.........')
                    return None
            return resolved[0]
        try:
            return self.provider.resolve(item, select_cb=select_cb)
        except ResolveException, e:
            self._handle_exc(e)

bug.SUBMIT_URL = sctop.submiturl
