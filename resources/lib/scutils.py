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
import xbmcutil
import xbmcplugin
import xbmcprovider
import xbmcvfs
import xmlrpclib
import zlib
import random
from datetime import datetime, timedelta
from dialogselect import DialogSelect
from collections import defaultdict
from provider import ResolveException
from urlparse import urlparse, parse_qs, urlunsplit


class KODISCLib(xbmcprovider.XBMCMultiResolverContentProvider):
    last_run = 0
    sleep_time = 1 * 60
    subs = None
    mPlayer = None
    force = False
    system = None

    def __init__(self, provider, settings, addon):
        xbmcprovider.XBMCMultiResolverContentProvider.__init__(
            self, provider, settings, addon)
        provider.parent = self
        sctop.uid = provider.uid
        self.provider = provider
        self.win = xbmcgui.Window(10000)
        self.noImage = os.path.join(self.addon_dir(), 'resources', 'img',
                                    'no-image.png')
        self.monitor = xbmc.Monitor()
        #self._settings()
        self.cache = sctop.cache
        self.provider.cache = self.cache
        self.timer = 0
        self._checkHTTPS()
        if sctop.player is None:
            sctop.player = myPlayer.MyPlayer(parent=self)

    def _checkHTTPS(self):
        '''
        skontroluje pri prvom spusteni, ci je zariadnie schopne nacitat stream-cinema cez https
        '''
        if sctop.getSettingAsBool('check_ssl1') is False:
            sctop.setSetting('check_ssl1', 'true')
            url = str(self.provider._url('/')).replace('http://', 'https://')
            util.debug('[SC] testujem HTTPS na SC %s' % url)
            s = sctop.checkSupportHTTPS(url)
            sctop.setSetting('UseSSL', 'true' if s is True else 'false')
            sctop.BASE_URL = "http%s://stream-cinema.online/kodi" % (
                's' if s is True else '')
            pass

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

    def root(self):
        if not '!download' in self.provider.capabilities():
            xbmcutil.add_local_dir(self.getString(30006),
                                   self.settings['downloads'],
                                   xbmcutil.icon('download.png'))
        self.list(self.provider.categories())
        return xbmcplugin.endOfDirectory(int(sys.argv[1]))

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
            return self.download({
                'url': params['down'],
                'title': params['title'],
                'force': '1'
            })
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
        return xbmcplugin.endOfDirectory(int(sys.argv[1]),
                                         succeeded=succeeded,
                                         cacheToDisc=cacheToDisc)

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
                except Exception as e:
                    error = True
                    util.error('[SC] Failed to create directory 1: ' + dir)

            if not xbmcvfs.exists(item_path):
                try:
                    file_desc = xbmcvfs.File(item_path, 'w')
                    file_desc.write(str(item_url))
                    file_desc.close()
                    new = True
                except Exception as e:
                    util.error('[SC] Failed to create .strm file: ' +
                               item_path + " | " + str(e))
                    error = True
        else:
            error = True

        util.debug("[SC] add item: %s" % item_path)
        return (error, new)

    @bug.buggalo_try_except({'method': 'scutils._link'})
    def _link(self, params):
        arg = {
            "play": "/Play/%d" % int(params['id']),
            "title": params['title']
        }
        if 'season' in params:
            arg.update({
                "play":
                "/Play/%d/%d/%d" % (int(params['id']), int(
                    params['season']), int(params['episode']))
            })
        return sctop._create_plugin_url(arg,
                                        'plugin://%s/' % sctop.__scriptid__)

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

        data = self.provider._json("%s/Lib/%s" %
                                   (sctop.BASE_URL, params['id']))
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
                    dialog.close()
                    return

                try:
                    dialog.update(
                        int(perc), "%s / %s - %s" %
                        (str(page), str(data['total']), i['title']))
                except Exception:
                    util.debug('[SC] ERR: %s' % str(traceback.format_exc()))
                    pass

                param = copy.deepcopy(params)
                util.debug("I: %s" % str(params))
                param.update({'id': str(i['id']), 'notify': 1})

                if params['id'] == 'movies':
                    (e, n) = self.add_item(param, addToSubscription, i)
                else:
                    if addToSubscription is False or (i['id'] not in subs) \
                       or (i['id'] in subs and self.canCheck(subs[i['id']]['last_run'])):
                        try:
                            (e, n) = self.add_item(param, addToSubscription)
                        except:
                            e |= True
                            sctop.sleep(6000)
                            pass

                error |= e
                new |= n
                new_in_page |= n
                if new is True and not error:
                    new_items = True
            page += 1
            if params['id'] == 'movies':
                if 'force' not in params and page > 2 and new_in_page is False:
                    util.debug(
                        "[SC] Dalej nepridavam, nemame nic dalsie na pridanie ..."
                    )
                    data = None
                else:
                    data = self.provider._json(
                        "%s/Lib/%s/?p=%s" %
                        (sctop.BASE_URL, params['id'], str(page)))
            else:
                data = None

        dialog.close()
        if not error and new_items and not ('update' in params) and not (
                'notify' in params):
            self.showNotification(self.getString(30901), 'New content')
            xbmc.executebuiltin('UpdateLibrary(video)')
        elif not error and not ('notify' in params):
            self.showNotification(self.getString(30901), 'No new content')
        elif error and not ('notify' in params):
            self.showNotification('Failed, Please check kodi logs', 'Linking')

    @bug.buggalo_try_except({'method': 'scutils.movieinfo'})
    def movienfo(self, data):
        out = ''
        if 'imdb' in data and data['imdb'] is not None and int(
                data['imdb']) > 0:
            out += "http://www.imdb.com/title/tt%07d/\n" % int(data['imdb'])
        if 'tmdb' in data and data['tmdb'] is not None and int(
                data['tmdb']) > 0:
            out += "https://www.themoviedb.org/movie/%d/\n" % int(data['tmdb'])
        if 'csfd' in data and data['csfd'] is not None and int(
                data['csfd']) > 0 and int(data['csfd']) < 999999:
            out += "http://www.csfd.cz/film/%d-\n" % int(data['csfd'])
        if 'tvdb' in data and data['tvdb'] is not None and int(
                data['tvdb']) > 0:
            out += "http://thetvdb.com/index.php?tab=series&id=%d\n" % int(
                data['tvdb'])

        util.debug("XML: %s" % out)
        return str(out)

    @bug.buggalo_try_except({'method': 'scutils.add_item_trakt'})
    def add_item_trakt(self, params):
        if trakt.getTraktCredentialsInfo() is True:
            util.debug("[SC] add_item_trakt: %s" % str(params))
            user = params['tu'] if 'tu' in params else 'me'
            __, ids, __ = trakt.getList(params['tl'], user=user)
            data = self.provider._json(self.provider._url("/Search/getTrakt"),
                                       {'ids': json.dumps(ids)})
            if 'menu' in data:
                error = False
                new = False
                e = False
                n = False

                dialog = sctop.progressDialogBG
                dialog.create('Stream Cinema CZ & SK',
                              'Adding Trakt watchlist to library')
                total = float(len(data['menu']))
                num = 0
                for i in data['menu']:
                    num += 1
                    perc = float(num / total) * 100
                    #util.info("percento: %d - (%d / %d)" % (int(perc), int(num), int(total)))
                    # background dialog cannot be canceled
                    # if dialog.iscanceled():
                    #     dialog.close()
                    #     return
                    try:
                        dialog.update(int(perc),
                                      "Adding Trakt watchlist to library",
                                      "%s" % (i['title']))
                    except Exception:
                        util.debug('[SC] ERR: %s' %
                                   str(traceback.format_exc()))
                        pass
                    (e, n) = self.add_item({
                        'notify': False,
                        'id': i['id']
                    }, False)

                    error |= e
                    new |= n

                dialog.close()
                if not error and new:
                    self.showNotification(self.getString(30901), 'New content')
                    xbmc.executebuiltin('UpdateLibrary(video)')
                elif not error:
                    self.showNotification(self.getString(30901),
                                          'No new content')
                elif error:
                    self.showNotification('Failed, Please check kodi logs',
                                          'Linking')

    def add_item_lastrun(self, ids):
        error = False
        new_items = False
        data = self.provider._json("%s/Lib/multi" % sctop.BASE_URL,
                                   {"ids": json.dumps(ids)})
        if data:
            for i in data:
                (e, n) = self.add_item({'notifi': 1, 'update': True}, data=i)
                error |= e
                new_items |= n
        else:
            error = True
        return (error, new_items)

    @bug.buggalo_try_except({'method': 'scutils.add_item'})
    def add_item(self, params, addToSubscription=False, data=None):
        error = False
        new_items = False
        if data is None:
            data = self.provider._json("%s/Lib/%s" %
                                       (sctop.BASE_URL, params['id']))

        if data is None or 'title' not in data:
            return (True, False)

        if 'ep' not in data:
            item_dir = self.getSetting('library-movies')
            xml_path = os.path.join(
                item_dir, self.normalize_filename(data['title']),
                self.normalize_filename(data['title'] + '.nfo'))
            self.add_item_to_library(xml_path, self.movienfo(data))
            item_path = os.path.join(
                item_dir, self.normalize_filename(data['title']),
                self.normalize_filename(data['title'] + '.strm'))
            (error,
             new_items) = self.add_item_to_library(item_path, self._link(data))
        else:
            if not ('notify' in params):
                self.showNotification(data['title'], 'Checking new content')

            subs = self.getSubs()
            item_dir = self.getSetting('library-tvshows')

            if not (data['id'] in subs) and addToSubscription:
                subs.update({
                    data['id']: {
                        'title': data['title'],
                        'last_run': time.time()
                    }
                })
                self.setSubs(subs)

            if not xbmcvfs.exists(
                    os.path.join(item_dir,
                                 self.normalize_filename(data['title']),
                                 'tvshow.nfo')):
                if 'tvdb' not in data:
                    data['tvdb'] = self.getTVDB(data)
                self.add_item_to_library(
                    os.path.join(item_dir,
                                 self.normalize_filename(data['title']),
                                 'tvshow.nfo'), self.movienfo(data))

            for itm in data['ep']:
                item_path = os.path.join(
                    item_dir, self.normalize_filename(data['title']),
                    'Season ' + itm['season'],
                    "S" + itm['season'] + "E" + itm['episode'] + '.strm')
                (err, new) = self.add_item_to_library(item_path,
                                                      self._link(itm))
                error |= err
                if new is True and not err:
                    new_items = True

        if not error and new_items and not ('update' in params) and not (
                'notify' in params):
            self.showNotification(data['title'], 'New content')
            xbmc.executebuiltin('UpdateLibrary(video)')
        elif not error and not ('notify' in params):
            if new_items is True:
                self.showNotification(data['title'], 'New content')
            else:
                self.showNotification(data['title'], 'No new content')
        if error and not ('notify' in params):
            self.showNotification('Failed, Please check kodi logs', 'Linking')
        return (error, new_items)

    @bug.buggalo_try_except({'method': 'scutils.canCheck'})
    def canCheck(self, last_run):
        next_check = last_run + (
            (sctop.getSettingAsInt('refresh_time')) * 3600 * 24) + 3600
        util.debug("[SC] can check: %d %d" %
                   (int(next_check), int(time.time())))
        return next_check < time.time()

    def sinput(self, edit):
        edit = '' if edit == '#' or '$' in edit else edit
        kb = sctop.keyboard(edit)
        kb.doModal()
        what = None
        if kb.isConfirmed():
            what = kb.getText()
            return what
            #self.list(self.provider.search(what, params['id']))
        self.endOfDirectory(succeeded=False)
        exit()

    @bug.buggalo_try_except({'method': 'scutils.csearch'})
    def csearch(self, params):
        util.debug("[SC] vyhladavanie: %s " % str(params))
        edit = False
        if 'action' in params and 'title' in params and params['title'] != '' and \
                params['action'] in [
                'csearch-remove', 'csearch-edit'
        ]:
            self.addList(params['id'],
                         params['title'],
                         max=sctop.getSettingAsInt("searchHistoryNum"),
                         removeonly=True)
            if params['action'] == 'csearch-remove':
                xbmc.executebuiltin('Container.Refresh')
                return
            edit = True
        if 'csearch' in params:
            self.list(self.provider.search(params['csearch'], params['id']))
            return self.endOfDirectory(cacheToDisc=False)
        li = self.getList(params['id'])
        if len(li) == 0 or (
                'title' in params and params['title'] == '#'
        ) or sctop.getSettingAsBool("searchHistory") is False or edit is True:
            what = self.sinput(params['title'])
            self.addList(params['id'],
                         what,
                         max=sctop.getSettingAsInt("searchHistoryNum"))
            params['action'] = 'csearch'
            params['csearch'] = what
            params['title'] = what
            url = sctop._create_plugin_url(params,
                                           'plugin://%s/' % sctop.__scriptid__)
            #self.endOfDirectory(succeeded=False, cacheToDisc=False)
            xbmc.executebuiltin('Container.Update(%s,true)' % url)
            #self.list(self.provider.search(what, params['id']))
        else:
            out = [{
                'title': '#',
                'action': 'csearch',
                'id': params['id'],
                'new': 1,
                'type': 'dir'
            }]
            for i in li:
                item = {
                    'title': str(i),
                    'action': 'csearch',
                    'csearch': str(i),
                    'id': str(params['id']),
                    'type': 'dir'
                }
                out.append(item)
            self.list(self.provider.items(data={'menu': out})
                      )  #self.provider.search(what, params['id']))
            pass
        return self.endOfDirectory(cacheToDisc=False)

    @bug.buggalo_try_except({'method': 'scutils.evalSchedules'})
    def evalSchedules(self, force=False):
        try:
            if not self.scanRunning() and not self.isPlaying():
                notified = False
                util.info("[SC] Loading subscriptions")
                subs = self.getSubs()
                util.debug("[SC] Subs: %s" % str(subs))
                new_items = False
                error = False
                ids = {}
                total = len(subs)
                num = 0

                if total > 0:
                    if force is True:
                        dialog = sctop.progressDialog
                        dialog.create('Stream Cinema CZ & SK',
                                      'Add all to library')
                    else:
                        dialog = None

                    mtime = 99999999999
                    for iid, data in subs.iteritems():
                        if iid != 'movie' and int(data['last_run']) < mtime:
                            mtime = int(data['last_run'])
                    sdata = self.provider._json(
                        self.provider._url('/Lib/getLast/%s' % str(mtime)))

                    if sdata is not None and 'data' in sdata and len(
                            sdata['data']) > 0:
                        for iid, data in subs.iteritems():
                            num += 1
                            if force is True and dialog is not None:
                                perc = 100 * num / total
                                util.info("percento: %s %d %d" %
                                          (str(perc), int(num), int(total)))
                                if dialog.iscanceled():
                                    dialog.close()
                                    self.setSubs(subs)
                                    return

                                try:
                                    dialog.update(int(perc))
                                except Exception:
                                    util.debug('[SC] ERR: %s' %
                                               str(traceback.format_exc()))
                                    pass

                            util.debug("[SC] sub id: %s" % str(iid))
                            if self.monitor.abortRequested():
                                util.info("[SC] Exiting")
                                return

                            if self.scanRunning() or self.isPlaying():
                                self.cache.delete("subscription.last_run")
                                return

                            if (iid == 'movie') or (iid == 'traktwatchlist'):
                                util.debug(
                                    "[SC] movie alebo traktwatchlist nepokracujem"
                                )
                                continue

                            if iid in sdata['data']:
                                if not notified:
                                    self.showNotification(
                                        'Subscription', 'Checking')
                                    notified = True
                                util.debug("[SC] Refreshing %s" % str(iid))
                                ids.update({iid: mtime})
                                if len(ids) >= 20:
                                    (e, n) = self.add_item_lastrun(ids)
                                    error |= e
                                    new_items |= n
                                    ids = {}
                            data['last_run'] = sdata['time']
                            subs[iid] = data

                        if len(ids) > 0:
                            (e, n) = self.add_item_lastrun(ids)
                            error |= e
                            new_items |= n

                        if error is False:
                            self.setSubs(subs)
                        util.debug("[SC] subscription done")

                    if dialog is not None:
                        dialog.close()

                if sctop.getSettingAsBool('download-movies'):
                    if 'movie' in subs:
                        data = subs['movie']
                    else:
                        data = {'last_run': 0}

                    util.debug("[SC] data: %s" % str(data))

                    if self.canCheck(data['last_run']) or force is True:
                        util.debug("[SC] movie stahujeme")
                        data['last_run'] = time.time()
                        subs['movie'] = data
                        self.setSubs(subs)
                        self.add_multi_item({'id': 'movies'}, False)
                    else:
                        util.info("[SC] movie netreba stahovat")
                else:
                    util.info("[SC] movie library disabled")

                if sctop.getSettingAsBool('download-trakt-watchlist'):
                    util.info("[SC] trakt watchlist enabled")

                    if 'traktwatchlist' in subs:
                        data = subs['traktwatchlist']
                    else:
                        data = {'last_run': 0}

                    util.debug("[SC] data: %s" % str(data))
                    if self.canCheck(data['last_run']) or force is True:
                        util.debug("[SC] download trakt watchlist")
                        data['last_run'] = time.time()
                        subs['traktwatchlist'] = data
                        self.setSubs(subs)
                        # self.run({'action': 'add-to-lib-trakt', 'tl': 'watchlist', 'tu': 'me', 'title': '[B]$30944[/B]'})
                        self.add_item_trakt({'tl': 'watchlist'})
                    else:
                        util.info(
                            "[SC] download trakt watchlist netreba stahovat")

                else:
                    util.info("[SC] trakt watchlist disabled")

                if new_items:
                    util.debug("[SC] UpdateLibrary")
                    xbmc.executebuiltin('UpdateLibrary(video)')
                else:
                    util.debug("[SC] no UpdateLibrary")
                notified = False
            else:
                util.info("[SC] Scan skipped")
        except:
            util.debug('[SC] ERR: %s' % str(traceback.format_exc()))
            pass

    @bug.buggalo_try_except({'method': 'scutils.getTVDB'})
    def getTVDB(self, params):
        if 'imdb' in params:
            data = self.provider.get_data_cached(
                'http://thetvdb.com/api/GetSeriesByRemoteID.php?=' +
                urllib.urlencode({
                    'imdbid': params['imdb'],
                    'language': 'en'
                }))
        else:
            data = self.provider.get_data_cached(
                'http://thetvdb.com/api/GetSeries.php?' +
                urllib.urlencode({
                    'seriesname': params['name'],
                    'language': 'en'
                }))
        try:
            tvid = re.search('<id>(\d+)</id>', data).group(1)
            return tvid
        except:
            pass
        return None

    @bug.buggalo_try_except({'method': 'scutils.normalize_filename'})
    def normalize_filename(self, name, validChars=None):
        validFilenameChars = "-_.() %s%s" % (string.ascii_letters,
                                             string.digits)
        if (validChars is not None):
            validFilenameChars = validChars
        cleanedFilename = self.encode(name)
        ret = ''.join(c for c in cleanedFilename if c in validFilenameChars)
        return ret if ret != '' else ''.join(
            random.choice(string.ascii_uppercase + string.digits)
            for _ in range(8))

    @bug.buggalo_try_except({'method': 'scutils.showNotification'})
    def showNotification(self, title, message, time=1000):
        xbmcgui.Dialog().notification(
            self.encode(title),
            self.encode(message),
            time=time,
            icon=xbmc.translatePath(self.addon_dir() + "/icon.png"),
            sound=False)

    def download(self, item):
        downloads = sctop.getSetting('downloads')
        if '' == downloads:
            sctop.dialog.ok(self.provider.name, self.getString(30009))
            return
        stream = self.resolve(item['url'])
        if stream is not None and stream is not False:
            if not 'headers' in stream.keys(): stream['headers'] = {}
            name = stream['fname']
            if (stream['subs'] == '' or stream['subs'] is None)\
                    and stream['lang'].strip()[:2] not in ['CZ', 'SK']:
                stream['subs'] = self.findSubtitles(stream)
            if stream['subs'] == '' or stream['subs'] == 'internal' or stream[
                    'subs'] == 'disabled':
                stream.remove('subs')
            if not stream['subs'] == '' and stream['subs'] is not None:
                sctop.download(stream['subs'], downloads, name + '.srt',
                               stream['headers'])
            from threading import Thread
            util.debug("[SC] mame co stahovat: %s" % str(stream))
            worker = Thread(target=sctop.download,
                            args=(stream['url'], downloads, name,
                                  stream['headers']))
            worker.start()

    @bug.buggalo_try_except({'method': 'scutils.run_custom'})
    def run_custom(self, params):
        util.debug("RUN CUSTOM: %s" % str(params))
        trakt_user = params['tu'] if 'tu' in params else 'me'
        if 'action' in params:
            util.debug("ACTION: %s" % str(params['action']))
            action = params['action']
            subs = False
            if action == 'ws-logout':
                try:
                    from myprovider.webshare import Webshare
                    ws = Webshare('', '', self.cache)
                    ws.logout()
                    sctop.notification('Webshare.cz',
                                       sctop.__language__(30112))
                except:
                    util.debug('[SC] ERR ws logout: %s' %
                               str(traceback.format_exc()))
                    pass
            if action == 'remove-from-sub':
                subs = self.getSubs()
                util.debug("[SC] subs: %s" % str(subs))
                if params['id'] in subs.keys():
                    del subs[params['id']]
                    self.setSubs(subs)
                    self.showNotification(params['title'],
                                          'Removed from subscription')
                    xbmc.executebuiltin('Container.Refresh')
            if action == 'add-to-lib-sub':
                subs = True
                action = 'add-to-lib'
            if action == 'add-to-lib':
                if params['id'] in ['movies', 'series'
                                    ] or 'movies' in params['id']:
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
                self.list(
                    self.provider.items(
                        self.provider._url("/Last/?%s" % urllib.urlencode(
                            {'ids': json.dumps(self.getList(params['id']))}))))
                return self.endOfDirectory()

            if action[0:5] == 'trakt':
                if trakt.getTraktCredentialsInfo() is False:
                    return

                if action == "traktManager":
                    trakt.manager(params['name'], params['trakt'],
                                  params['content'])
                    return

                if action == 'traktWatchlist':
                    self.list(
                        self.provider.items(
                            data={'menu': trakt.getLists(trakt_user)}))
                    return self.endOfDirectory()

                if action == 'traktHistory':
                    self.list(
                        self.provider.items(
                            data={'menu': trakt.getHistory(trakt_user)}))
                    return self.endOfDirectory()

                if action == 'traktFollowing':
                    self.list(
                        self.provider.items(
                            data={'menu': trakt.getFollowing()}))
                    return self.endOfDirectory()

                if action == 'traktShowList':
                    util.debug("[SC] params: %s" % str(params))
                    content = None if 'content' not in params else params[
                        'content']
                    content_type, ids, ratings = trakt.getList(params['id'],
                                                               content,
                                                               user=trakt_user)
                    if len(ids) > 0:
                        data = self.provider._json("/Search/getTrakt",
                                                   {'ids': json.dumps(ids)})
                        try:
                            data['system']['setContent'] = content_type
                        except:
                            pass
                        if ratings != False:
                            for i, item in enumerate(data['menu']):
                                data['menu'][i]['rating'] = ratings[int(
                                    item['trakt'])]

                        self.list(self.provider.items(data=data))
                    else:
                        self.list([])
                    return self.endOfDirectory()

                if action == 'traktSpecialLists':
                    page = int(params['page']) if 'page' in params else 1
                    self.list(
                        self.provider.items(data={
                            'menu':
                            trakt.getSpecialLists(params['id'], page)
                        }))
                    return self.endOfDirectory()

                if action == 'traktListAppendToCustom':
                    trakt.listAppendToCustom(params['tu'], params['id'])
                    return

                if action == 'traktListClone':
                    trakt.listClone(params['tu'], params['id'])
                    return

                if action == 'traktListCustomRemove':
                    trakt.listCustomRemove(params['title'], params['id'])
                    xbmc.executebuiltin('Container.Refresh')
                    return

                if action == 'traktListLike':
                    trakt.listLike(params['title'], params['tu'], params['id'])
                    return

                if action == 'traktListUnlike':
                    trakt.listUnlike(params['title'], params['tu'],
                                     params['id'])
                    xbmc.executebuiltin('Container.Refresh')
                    return

            if action == 'authTrakt':
                trakt.authTrakt()
            if action == 'speedtest':  #                               1:350    2:500    3:750  4:1000 5:1500   6:2000   7:2500 8:3000  9:3500   10:4000
                g = sctop.getString
                x = [
                    g(30551),
                    g(30552),
                    g(30553),
                    g(30554),
                    g(30555),
                    g(30556),
                    g(30557),
                    g(30558),
                    g(30559),
                    g(30560)
                ]
                run = 8

                try:
                    ret = sctop.dialog.select(g(30501), x)
                except:
                    ret = 2000
                    pass

                _files = [
                    0, 350, 500, 750, 1000, 1500, 2000, 2500, 3000, 3500, 4000
                ]
                # https://webshare.cz/#/group/4le11t36i5/
                _idents = [
                    '', '5ac4wB1iU7', '73d43j1aDy', '12r20P3ir2', '14b1Bc3lg2',
                    '4P448o4pr5', 'Ik6qg55c6h', '6j22Kr6L7h', '1gr7fX6oE7',
                    '4Xs60K66ei', '6g03G1Dl1p'
                ]
                out = [_files[ret]]
                from speedtest import speedTest, pretty_speed
                pg = sctop.progressDialog
                pg.create(g(30050))
                pg.update(0)

                # https://vip.3.dl.webshare.cz
                try:
                    from myprovider.webshare import Webshare as ws
                    w = ws(sctop.getSetting('wsuser'),
                           sctop.getSetting('wspass'))
                    r = w.resolve(_idents[ret])
                    o = urlparse(r)
                    pg.update(10)
                    wspeedtest = speedTest(
                        None, run, out,
                        'http' if 'http://' in o[0] else 'https')
                    pg.update(10, 'webshare.cz')
                    urls = [{'host': o[1], 'url': o[2]} for i in range(run)]
                    wsdown = wspeedtest.download(urls=urls)
                    pg.update(50)
                except Exception as e:
                    wsdown = 0
                    util.debug("[SC] ERROR: %s" % str(traceback.format_exc()))

                speedtest = speedTest(None, run, out)
                pg.update(60, speedtest.host)
                bedown = speedtest.download()
                pg.update(100)
                pg.close()
                if wsdown > 100:
                    sctop.setSetting('bitrate', int(wsdown))
                    sctop.setSetting('bitrateformated',
                                     str(pretty_speed(wsdown)))
                if str(params.get('wizard', '')) == '1':
                    sctop.win.setProperty(
                        'scwizard',
                        json.dumps({
                            'ws': {
                                'host': speedtest.host,
                                'speed': pretty_speed(bedown)
                            },
                            'oth': {
                                'host': speedtest.host,
                                'speed': pretty_speed(bedown)
                            }
                        }))
                    return
                sctop.dialog.ok(
                    g(30050),
                    "%s: %s" % ('webshare.cz', str(pretty_speed(wsdown))),
                    "%s: %s" % (speedtest.host, str(pretty_speed(bedown))))
                sctop.openSettings('1.0')
            if action == 'play-force':
                self.force = True
                try:
                    self.play({'url': params['play'], 'info': params})
                except:
                    util.debug("[SC] ERROR: %s" % str(traceback.format_exc()))
                    pass
                util.debug("[SC] ----------------------------------------")
            if action == 'trakt':
                movies = self.getTraktLastActivity(
                    'series')  #trakt.getWatchedActivity()
                util.debug("[SC] movies: %s" % str(movies))
            if action in ['csearch', 'csearch-edit', 'csearch-remove']:
                return self.csearch(params)
            if action == 'search-actor':
                self.list(
                    self.provider.items(
                        None,
                        self.provider._json(
                            "/Search/actor/%s/%s" %
                            (params['id'], params['subtype']), {
                                'id': params['id'],
                                'type': params['subtype']
                            })))
                return self.endOfDirectory()
            if action == 'info':
                xbmc.executebuiltin('Action("Info")')
                return
            if action == 'refreshrepo':
                xbmc.executebuiltin("UpdateAddonRepos()")
                xbmc.executebuiltin("UpdateLocalAddons()")
                xbmc.executebuiltin("ReloadSkin()")
            if action == 'json_settings':
                sctop.json_settings()
                return self.endOfDirectory(succeeded=False, cacheToDisc=False)
            if action == 'filter':
                self.list(
                    self.provider.items(
                        None, self.provider._json('/Filter/', params)))
                return self.endOfDirectory(cacheToDisc=False)
            if action == 'test':
                self.evalSchedules()
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
        return sctop.isPlaying()

    def scanRunning(self):
        return (xbmc.getCondVisibility('Library.IsScanningVideo')
                or xbmc.getCondVisibility('Library.IsScanningMusic'))

    @bug.buggalo_try_except({'method': 'scutils.setUniq'})
    def setUniq(self, li, stream):
        uniq = {}
        if 'imdb' in stream and int(stream['imdb']) != 0:
            # util.debug("[SC] uniq imdb %s" % stream['imdb'])
            imdb = "tt%07d" % int(stream['imdb'])
            uniq.update({'imdb': imdb})
            li.setProperty('IMDBNumber', stream['imdb'])
        if 'tmdb' in stream and int(stream['tmdb']) != 0:
            # util.debug("[SC] uniq tmdb %s" % stream['tmdb'])
            uniq.update({'tmdb': stream['tmdb']})
            li.setProperty('TMDBNumber', stream['tmdb'])
        if 'tvdb' in stream and int(stream['tvdb']) != 0:
            # util.debug("[SC] uniq tvdb %s" % stream['tvdb'])
            uniq.update({'tvdb': stream['tvdb']})
            li.setProperty('TVDBNumber', stream['tvdb'])
        if 'csfd' in stream and int(stream['csfd']) < 1000000:
            # util.debug("[SC] uniq csfd %s" % stream['csfd'])
            uniq.update({'csfd': stream['csfd']})
            li.setProperty('CSFDNumber', stream['csfd'])
        if 'trakt' in stream and int(stream['trakt']) != 0:
            # util.debug("[SC] uniq trakt %s" % stream['trakt'])
            uniq.update({'trakt': stream['trakt']})
            li.setProperty('TRAKTNumber', stream['trakt'])

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
                # util.debug('[SC] render item dir')
                self.render_dir(item)
            elif item['type'] == 'next':
                # util.debug('[SC] render item next')
                params.update({'list': item['url']})
                xbmcutil.add_dir(self.getString(30007), params,
                                 xbmcutil.icon('next.png'))
            elif item['type'] == 'prev':
                # util.debug('[SC] render item prev')
                params.update({'list': item['url']})
                xbmcutil.add_dir(self.getString(30008), params,
                                 xbmcutil.icon('prev.png'))
            elif item['type'] == 'new':
                # util.debug('[SC] render item new')
                params.update({'list': item['url']})
                xbmcutil.add_dir(self.getString(30012), params,
                                 xbmcutil.icon('new.png'))
            elif item['type'] == 'top':
                # util.debug('[SC] render item top')
                params.update({'list': item['url']})
                xbmcutil.add_dir(self.getString(30013), params,
                                 xbmcutil.icon('top.png'))
            elif item['type'] == 'video':
                # util.debug('[SC] render item video')
                try:
                    self.render_video(item)
                except Exception as e:
                    util.debug('[SC] item error: %s' % str(traceback.format_exc()))
            else:
                # util.debug('[SC] render item default')
                self.render_default(item)

    @bug.buggalo_try_except({'method': 'scutils.play'})
    def play(self, item):
        util.debug("[SC] PLAY ITEM: %s" % str(item))
        if 'info' in item and 'force' in item['info'] or 'force' in item:
            self.force = True
        stream = self.resolve(item['url'])

        if stream and 'id' in stream:
            imdb = stream['imdb'] if 'imdb' in stream else 0
            tvdb = stream['tvdb'] if 'tvdb' in stream else 0
            trakt = stream['trakt'] if 'trakt' in stream else 0
            ids = {'imdb': imdb, 'tvdb': tvdb, 'trakt': trakt}
            ids = dict((k, v) for k, v in ids.iteritems() if not v == '0')

            xbmcgui.Window(10000).setProperty('script.trakt.ids',
                                              json.dumps(ids))
            xbmcgui.Window(10000).setProperty('%s.ids' % sctop.__scriptid__,
                                              json.dumps(ids))
            xbmcgui.Window(10000).setProperty('%s.stream' % sctop.__scriptid__,
                                              json.dumps(stream))
            self.win.setProperty('scid', str(stream['id']))

            if 'headers' in stream.keys():
                headerStr = '|' + urllib.urlencode(stream['headers'])
                if len(headerStr) > 1:
                    stream['url'] += headerStr
            util.debug('Sending %s to player' % stream['url'])
            li = xbmcgui.ListItem(path=stream['url'],
                                  iconImage='DefaulVideo.png')
            util.debug("PLAY::LI::" + str(stream))
            il = self._extract_infolabels(stream)
            if 'dtitle' in item['info']:
                il['title'] = item['info']['dtitle']

            if 'art' in stream:
                util.debug("[SC] Play MAME ART")
                if 'poster' in stream['art'] and 'thumb' not in stream['art']:
                    stream['art'].update({'thumb': stream['art']['poster']})
                li.setArt(stream['art'])
            else:
                util.debug("[SC] Play nemame ART")

            self.setUniq(li, stream)

            util.debug("[SC] INFO: %s" % str(self._extract_infolabels(stream)))

            if len(il) > 0:  # only set when something was extracted
                li.setInfo('video', il)
                #util.debug("IL: %s" % str(il))

            if (stream['subs'] == '' or stream['subs'] is None
                ) and stream['lang'].strip()[:2] not in ['CZ', 'SK']:
                #util.debug(stream)
                stream['subs'] = self.findSubtitles(stream)

            if stream['subs'] == '' or stream['subs'] == 'internal' or stream[
                    'subs'] == 'disabled':
                stream.remove('subs')

            try:
                if 'subs' in stream and stream['subs'] != '' and stream[
                        'subs'] is not None:
                    #util.debug("Seturnm titulky: " + str(stream['subs']))
                    li.setSubtitles([stream['subs']])
            except:
                pass

            try:
                li.setMimeType('application/octet-stream')
                li.setContentLookup(False)
            except Exception as e:
                util.debug("[SC] err content lookup %s" %
                           str(traceback.format_exc()))

            self.win.setProperty(sctop.__scriptid__, sctop.__scriptid__)
            util.debug("[SC] mozem zacat prehravat %s" % str(stream))

            if self.force is True:
                return xbmc.Player().play(stream['url'], li, False, -1)
            util.debug("[SC] setResolvedUrl")
            xbmcplugin.setResolvedUrl(int(sys.argv[1]), True, li)
        else:
            li = xbmcgui.ListItem(path=item['url'])
            xbmcplugin.setResolvedUrl(int(sys.argv[1]), True, li)
            util.debug('[SC] play external stream %s' % str(stream))
            pass

    def _settings(self):
        return
        sp = os.path.join(self.addon_dir(), 'resources', 'settings.xml')
        itm = json.loads(util.request(scinema.BASE_URL + '/json/settings'))
        self.sett = ""
        self._parse_settings(itm['items'])
        util.info('SET: ' + self.sett)

    @bug.buggalo_try_except({'method': 'scutils._extract_infolabels'})
    def _extract_infolabels(self, item):
        infoLabels = {}
        for label in [
                'genre', 'year', 'episode', 'season', 'top250', 'tracknumber',
                'rating', 'watched', 'playcount', 'overlay', 'cast',
                'castandrole', 'director', 'mpaa', 'plot', 'plotoutline',
                'title', 'originaltitle', 'sorttitle', 'duration', 'studio',
                'tagline', 'writer', 'tvshowtitle', 'premiered', 'status',
                'aired', 'credits', 'lastplayed', 'album', 'artist', 'votes',
                'trailer', 'dateadded', 'count', 'date', 'imdbnumber',
                'mediatype'
        ]:
            if label in item.keys():
                if label == 'cast':
                    if hasattr(item['cast'], 'lower'):
                        item['cast'] = item['cast'].split(', ')
                    infoLabels[label] = item[label]
                else:
                    infoLabels[label] = util.decode_html(item[label])
        if trakt.getTraktCredentialsInfo() != True:
            return infoLabels

        try:
            if item.get('trakt') and int(
                    item.get('trakt')) > 0 and item.get('season') is None:
                if item.get('trakt') in self.getTraktLastActivity():
                    # util.debug("[SC] oznacujem za videne z trakt.tv %s" % str(item))
                    infoLabels['playcount'] = 1
                # util.debug("[SC] item ma trakt %s" % str(item.get('trakt')))
        except:
            pass

        try:
            if item.get('trakt') and int(item.get('trakt')) > 0 and item.get(
                    'season') is not None and item.get('episode') is not None:
                playcount = [
                    i[2] for i in self.getTraktLastActivity('series')
                    if i[0] == item.get('trakt')
                ]
                playcount = playcount[0] if len(playcount) > 0 else []
                playcount = [
                    i for i in playcount
                    if int(item.get('season')) == int(i[0])
                    and int(item.get('episode')) == int(i[1])
                ]
                util.debug("[SC] item ma tvdb %s %sx%s %s" %
                           (str(item.get('trakt')), str(item.get('season')),
                            str(item.get('episode')), str(playcount)))
                playcount = 1 if len(playcount) > 0 else 0
                infoLabels['playcount'] = playcount
        except:
            pass

        #infoLabels['overlay'] = 7
        return infoLabels

    @bug.buggalo_try_except({'method': 'scutils.render_dir'})
    def render_dir(self, item):
        params = self.params()
        params.update(item)
        if 'url' in item:
            if item['url'].startswith('cmd://'):
                #util.debug('command!!!')
                params.update({'cmd': item['url'][6:]})
            else:
                params.update({'list': item['url']})
        title = str(item['title'])
        try:
            title.index('$')
            #util.debug("[SC] mame prelozit %s" % title)
            try:
                for i in list(
                        re.finditer('\$([0-9]+)', title,
                                    re.IGNORECASE | re.DOTALL)):
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
                        ctxtitle = self.addon.getLocalizedString(
                            int(ctxtitle[1:]))
                    except:
                        pass
                menuItems[ctxtitle] = value
        self.add_dir(title, params, img, infoLabels=item, menuItems=menuItems)

    @bug.buggalo_try_except({'method': 'scutils.add_dir'})
    def add_dir(self, name, params, logo='', infoLabels={}, menuItems={}):
        name = util.decode_html(name)
        if 'title' not in infoLabels:
            infoLabels['title'] = ''
        if logo is None:
            logo = ''
        liz = xbmcgui.ListItem(name,
                               iconImage='DefaultFolder.png',
                               thumbnailImage=logo)

        if 'art' in infoLabels.keys():
            liz.setArt(infoLabels['art'])

        if 'selected' in infoLabels.keys():
            #wnd = xbmcgui.Window(xbmcgui.getCurrentWindowId())
            #util.debug("[SC] wnd: %s [%d]" % (str(wnd), xbmcgui.getCurrentWindowId()))
            pass

        try:
            liz.setInfo(type='Video',
                        infoLabels=self._extract_infolabels(infoLabels))
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
                        items.append((mi, 'Container.Update(%s)' %
                                      sctop._create_plugin_url(action)))
                    elif action_type == 'play':
                        items.append((mi, 'PlayMedia(%s)' %
                                      sctop._create_plugin_url(action)))
                    else:
                        items.append((mi, 'RunPlugin(%s)' %
                                      sctop._create_plugin_url(action)))
                else:
                    items.append(
                        (mi,
                         'RunPlugin(%s)' % sctop._create_plugin_url(action)))
        if len(items) > 0:
            liz.addContextMenuItems(items)
        return xbmcplugin.addDirectoryItem(
            handle=int(sys.argv[1]),
            url=sctop._create_plugin_url(params),
            listitem=liz,
            isFolder=True)

    @bug.buggalo_try_except({'method': 'scutils.render_video'})
    def render_video(self, item):
        #util.debug("_render_video")

        params = self.params()
        params.update({'play': item['url'], 'dtitle': item['title']})
        #for k,v in item.iteritems():
        #    params.update({k: str(v)})
        downparams = self.params()
        if item.get('originaltitle_seo'):
            downparams.update({
                'title':
                "%s%s" % (item['originaltitle_seo'], item['extension']),
                'down':
                item['url']
            })
        else:
            downparams.update({
                'title': "%s.%s" % (item['title'], 'mp4'),
                'down': item['url']
            })
        title = item['title']  #'%s%s' % (item['title'],item['size'])
        menuItems = {}
        if "!download" not in self.provider.capabilities():
            menuItems[xbmc.getLocalizedString(33003)] = downparams
        if 'trailer' in item.keys(
        ) and item['trailer'] != '' and item['trailer'] is not None:
            trailerparams = {'action-type': 'trailer', 'url': item['trailer']}
            menuItems['Trailer'] = trailerparams
        if 'menu' in item.keys():
            for ctxtitle, value in item['menu'].iteritems():
                if ctxtitle.find('$') == 0:
                    try:
                        ctxtitle = self.addon.getLocalizedString(
                            int(ctxtitle[1:]))
                    except:
                        pass
                menuItems[ctxtitle] = value
        # util.debug("[SC] menuItems: %s" % str(menuItems))
        self.add_video(title,
                       params,
                       item['img'],
                       infoLabels=item,
                       menuItems=menuItems)

    @bug.buggalo_try_except({'method': 'scutils.getTaraktLastActitivy'})
    def getTraktLastActivity(self, typ='movie'):
        if sctop.traktlistlast is not None:
            return sctop.traktlistlast.get(typ)
        res = []
        try:
            if trakt.getTraktCredentialsInfo():
                if sctop.traktlistlast is None:
                    loc = self.cache.get('lastActivity')
                    rem = str(trakt.getWatchedActivity())
                    util.debug("[SC] loc: [%s] rem: [%s]" % (loc, rem))
                    if loc is None or rem != loc:
                        util.debug('[SC] trakt natahujem z webu')
                        self.cache.set('lastActivity', str(rem))
                        alres = {
                            'movie': trakt.syncMovies(),
                            'series': trakt.syncTVShows()
                        }
                        self.cache.set('LastActivityList', repr(alres))
                    else:
                        util.debug('[SC] trakt natahujem z cache')
                        try:
                            alres = eval(self.cache.get('LastActivityList'))
                        except:
                            util.debug('[SC] LastActivityList problem')
                            alres = {
                                'moveies': [],
                                'series': []
                            }
                            self.cache.set('lastActivity', repr(None))
                else:
                    alres = sctop.traktlistlast
                if alres is not None:
                    util.debug('[SC] mame data pre lastActivity')
                    sctop.traktlistlast = alres
                    res = alres.get(typ)
        except:
            util.debug('[SC] getTraktLastActivity ERR: %s' %
                       str(traceback.format_exc()))
            pass
        util.debug('[SC] getTraktLastActivity ret: %s' % str(res) )
        return res

    @bug.buggalo_try_except({'method': 'scutils.add_video'})
    def add_video(self, name, params={}, logo='', infoLabels={}, menuItems={}):
        #util.debug("_add_video")
        #util.debug("[SC] add video info: %s" % str(infoLabels))
        _infoLabels = self._extract_infolabels(infoLabels)
        name = util.decode_html(name)
        if 'Title' not in _infoLabels:
            _infoLabels['Title'] = name
        #util.debug("[SC] params: %s" % str(params))
        url = sctop._create_plugin_url(params)
        if logo == '' or logo is None:
            logo = self.noImage
        li = xbmcgui.ListItem(name,
                              path=url,
                              iconImage='DefaultVideo.png',
                              thumbnailImage=logo)
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
                        items.append((mi, 'Container.Update(%s)' %
                                      sctop._create_plugin_url(action)))
                    elif action_type == 'play':
                        items.append((mi, 'PlayMedia(%s)' %
                                      sctop._create_plugin_url(action)))
                    elif action_type == 'trailer':
                        items.append((mi, 'PlayMedia(%s)' % action['url']))
                    else:
                        items.append((mi, 'RunPlugin(%s)' %
                                      sctop._create_plugin_url(action)))
                else:
                    items.append(
                        (mi,
                         'RunPlugin(%s)' % sctop._create_plugin_url(action)))

        # util.debug('[SC] av 20')
        if len(items) > 0:
            li.addContextMenuItems(items)
        # util.debug('[SC] pridavam idem do adresara: %s' % str(li))
        # xbmc.executebuiltin("Container.SetViewMode(515)")
        return xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]),
                                           url=url,
                                           listitem=li,
                                           isFolder=False)

    @staticmethod
    def encode(string):
        return unicodedata.normalize('NFKD', string.decode('utf-8')).encode(
            'ascii', 'ignore')

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
        if sctop.player is None:
            sctop.player = myPlayer.MyPlayer(parent=self)
        try:
            sleep_time = int(self.getSetting("start_sleep_time")) * 60
        except:
            sleep_time = self.sleep_time
            pass

        util.debug("[SC] start delay: %s" % str(sleep_time))
        start = time.time() + sleep_time
        while not self.monitor.abortRequested() and time.time() < start:
            self._player()
            if self.monitor.waitForAbort(1):
                break
        del start

        util.debug("[SC] start sleep end")

        try:
            self.last_run = float(self.cache.get("subscription.last_run"))
        except:
            self.last_run = time.time()
            self.cache.set("subscription.last_run", str(self.last_run))
            pass

        util.debug("[SC] last_rum: %s" % str(self.last_run))

        if not self.monitor.abortRequested() and time.time() > self.last_run:
            self.evalSchedules()

        self.sleep_time = 1
        while not self.monitor.abortRequested():
            self._player()
            self._scheduler()
            if self.monitor.waitForAbort(self.sleep_time):
                break
        del sctop.player
        util.info("[SC] Shutdown")

    def _player(self):
        try:
            if not self.monitor.abortRequested(
            ) and sctop.player.isPlayingVideo() and sctop.player.scid > 0:
                notificationtime = 30
                playTime = sctop.player.getTime()
                totalTime = sctop.player.getTotalTime()
                sctop.player.watchedTime = playTime
                self.timer += 1
                if self.timer >= 600:
                    sctop.player.waitForChange()
                    self.timer = 0
                    data = {
                        'scid': sctop.player.scid,
                        'action': 'ping',
                        'prog': sctop.player.timeRatio()
                    }
                    if bool(xbmc.getCondVisibility("!Player.Paused")) is True:
                        sctop.player.action(data)

                showupnext = sctop.getSettingAsBool("show_up_next")
                util.debug('[SC] [%s] [%s]' % (str(sctop.player.started + 10), str(time.time())))
                util.debug("[SC] upNext [%s] [%s] " % (str(
                    (totalTime - playTime) <= int(notificationtime)), (int(time.time()) - sctop.player.started) > 10))
                if showupnext and (int(time.time()) - sctop.player.started) > 10 and (
                        totalTime - playTime) <= int(notificationtime):
                    sctop.player.upNext()
        except Exception as e:
            bug.onExceptionRaised(e)
            util.debug("[SC] _player e: %s" % str(e))
            pass

    def _scheduler(self):
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
            if not self.getSetting(
                    'subtitles') == 'true' or stream['sinfo'] is True:
                raise Exception()
            imdb = stream['imdb']
            season = None
            episode = None
            if 'season' in stream:
                season = stream['season']
            if 'episode' in stream:
                episode = stream['episode']

            util.debug("[SC] Hladam titulky")
            langDict = {
                'Afrikaans': 'afr',
                'Albanian': 'alb',
                'Arabic': 'ara',
                'Armenian': 'arm',
                'Basque': 'baq',
                'Bengali': 'ben',
                'Bosnian': 'bos',
                'Breton': 'bre',
                'Bulgarian': 'bul',
                'Burmese': 'bur',
                'Catalan': 'cat',
                'Chinese': 'chi',
                'Croatian': 'hrv',
                'Czech': 'cze',
                'Danish': 'dan',
                'Dutch': 'dut',
                'English': 'eng',
                'Esperanto': 'epo',
                'Estonian': 'est',
                'Finnish': 'fin',
                'French': 'fre',
                'Galician': 'glg',
                'Georgian': 'geo',
                'German': 'ger',
                'Greek': 'ell',
                'Hebrew': 'heb',
                'Hindi': 'hin',
                'Hungarian': 'hun',
                'Icelandic': 'ice',
                'Indonesian': 'ind',
                'Italian': 'ita',
                'Japanese': 'jpn',
                'Kazakh': 'kaz',
                'Khmer': 'khm',
                'Korean': 'kor',
                'Latvian': 'lav',
                'Lithuanian': 'lit',
                'Luxembourgish': 'ltz',
                'Macedonian': 'mac',
                'Malay': 'may',
                'Malayalam': 'mal',
                'Manipuri': 'mni',
                'Mongolian': 'mon',
                'Montenegrin': 'mne',
                'Norwegian': 'nor',
                'Occitan': 'oci',
                'Persian': 'per',
                'Polish': 'pol',
                'Portuguese': 'por,pob',
                'Portuguese(Brazil)': 'pob,por',
                'Romanian': 'rum',
                'Russian': 'rus',
                'Serbian': 'scc',
                'Sinhalese': 'sin',
                'Slovak': 'slo',
                'Slovenian': 'slv',
                'Spanish': 'spa',
                'Swahili': 'swa',
                'Swedish': 'swe',
                'Syriac': 'syr',
                'Tagalog': 'tgl',
                'Tamil': 'tam',
                'Telugu': 'tel',
                'Thai': 'tha',
                'Turkish': 'tur',
                'Ukrainian': 'ukr',
                'Urdu': 'urd'
            }

            quality = [
                'bluray', 'hdrip', 'brrip', 'bdrip', 'dvdrip', 'webrip', 'mhd',
                'hdtv', 'web', 'www'
            ]

            langs = []
            try:
                try:
                    langs = langDict[self.getSetting(
                        'subtitles.lang.1')].split(',')
                except:
                    langs.append(langDict[self.getSetting('subtitles.lang.1')])
            except:
                pass

            try:
                try:
                    langs = langs + langDict[self.getSetting(
                        'subtitles.lang.2')].split(',')
                except:
                    langs.append(langDict[self.getSetting('subtitles.lang.2')])
            except:
                pass

            server = xmlrpclib.Server('http://api.opensubtitles.org/xml-rpc',
                                      verbose=0)
            token = server.LogIn('', '', 'en', 'XBMC_Subtitles_v1')['token']
            util.debug("[SC] TOKEN: %s" % token)

            sublanguageid = ','.join(langs)
            imdbid = re.sub('[^0-9]', '', imdb)

            if season is not None and episode is not None:
                result = server.SearchSubtitles(token, [{
                    'sublanguageid': sublanguageid,
                    'imdbid': imdbid,
                    'season': season,
                    'episode': episode
                }])['data']
            else:
                result = server.SearchSubtitles(token, [{
                    'sublanguageid': sublanguageid,
                    'imdbid': imdbid
                }])['data']

            try:
                vidPath = stream['fname'] if 'fname' in stream else stream[
                    'url']
            except:
                vidPath = ''
            fmt = re.split('\.|\(|\)|\[|\]|\s|\-', vidPath)
            fmt = [i.lower() for i in fmt]
            fmt = [i for i in fmt if i in quality]

            filter = []
            result = [i for i in result if i['SubSumCD'] == '1']

            for lang in langs:
                if 'src' in stream and 'grp' in stream:
                    util.debug("[SC] skusam vybrat podla SRC %s a GRP %s" %
                               (stream['src'].lower(), stream['grp'].lower()))
                    filter += [
                        i for i in result
                        if i['SubLanguageID'] == lang and stream['src'].lower(
                        ) in i['MovieReleaseName'].lower() and
                        stream['grp'].lower() in i['MovieReleaseName'].lower()
                    ]
                if 'grp' in stream:
                    util.debug("[SC] skusam vybrat podla GRP %s" %
                               stream['grp'].lower())
                    filter += [
                        i for i in result if i['SubLanguageID'] == lang and
                        stream['grp'].lower() in i['MovieReleaseName'].lower()
                    ]
                if 'src' in stream:
                    util.debug("[SC] skusam vybrat podla SRC %s" %
                               stream['src'].lower())
                    filter += [
                        i for i in result if i['SubLanguageID'] == lang and
                        stream['src'].lower() in i['MovieReleaseName'].lower()
                    ]

                filter += [
                    i for i in result if i['SubLanguageID'] == lang and any(
                        x in i['MovieReleaseName'].lower() for x in fmt)
                ]
                filter += [
                    i for i in result if i['SubLanguageID'] == lang and any(
                        x in i['MovieReleaseName'].lower() for x in quality)
                ]
                filter += [i for i in result if i['SubLanguageID'] == lang]

            try:
                lang = xbmc.convertLanguage(filter[0]['SubLanguageID'],
                                            xbmc.ISO_639_1)
            except:
                lang = filter[0]['SubLanguageID']

            util.debug("[SC] subtitles: %s" % str(filter[0]))
            content = [
                filter[0]['IDSubtitleFile'],
            ]
            content = server.DownloadSubtitles(token, content)
            content = base64.b64decode(content['data'][0]['data'])
            content = str(
                zlib.decompressobj(16 + zlib.MAX_WBITS).decompress(content))

            return self.saveSubtitle(content, lang)
        except Exception:
            util.debug("[SC] Neriesim TITULKY")
            util.debug(traceback.format_exc())
            pass

    def saveSubtitle(self, content, lang, convert=True):
        codePageDict = {
            'ara': 'cp1256',
            'ar': 'cp1256',
            'cs': 'cp1250',
            'ell': 'cp1253',
            'el': 'cp1253',
            'heb': 'cp1255',
            'he': 'cp1255',
            'sk': 'cp1250',
            'tur': 'cp1254',
            'tr': 'cp1254',
            'rus': 'cp1251',
            'ru': 'cp1251'
        }

        subtitle = xbmc.validatePath(xbmc.translatePath('special://temp/'))
        subtitle = os.path.join(subtitle, 'AutomatickeTitulky.%s.srt' % lang)

        codepage = codePageDict.get(lang, '')
        if codepage and self.getSetting('subtitles.utf') == 'true':
            try:
                content_encoded = codecs.decode(content, codepage)
                content = codecs.encode(content_encoded, 'utf-8')
            except Exception as e:
                util.debug("[SC] chyba ukladania titulkov....")
                pass

        file = xbmcvfs.File(subtitle, 'w')
        file.write(str(content))
        file.close()
        return subtitle

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
        except Exception as e:
            util.error(e)
            subs = {}
        return subs

    @bug.buggalo_try_except({'method': 'scutils.setSubs'})
    def setSubs(self, subs):
        self.subs = subs
        #util.debug("[SC] set subs %s" % str(subs))
        self.cache.set("subscription",
                       repr(subs),
                       expiration=timedelta(days=365))

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
        except Exception as e:
            util.debug("[SC] migrate err: %s" % str(traceback.format_exc()))
            pass

    @bug.buggalo_try_except({'method': 'scutils.getLast'})
    def getLast(self):
        return self.getList('last')

    @bug.buggalo_try_except({'method': 'scutils.setLast'})
    def setLast(self, last):
        self.setList('last', last)

    @bug.buggalo_try_except({'method': 'scutils.addLast'})
    def addLast(self, scid):
        return self.addList('last', scid)

    @bug.buggalo_try_except({'method': 'scutils.getList'})
    def getList(self, name):
        data = self.cache.get(name)
        try:
            if data == '' or data is None:
                last = []
            else:
                last = eval(data)
        except:
            last = []
        util.debug("[SC] getList %s %s" % (name, str(last)))
        return last

    @bug.buggalo_try_except({'method': 'scutils.setList'})
    def setList(self, name, last):
        util.debug("[SC] setList %s %s" % (name, str(last)))
        self.cache.set(name, repr(last), expiration=timedelta(days=365))

    @bug.buggalo_try_except({'method': 'scutils.addList'})
    def addList(self, name, scid, max=20, removeonly=False):
        last = self.getList(name)
        util.debug("[SC] addList [%s] %s -> %s" % (name, str(scid), str(last)))
        if scid in last:
            last.remove(scid)

        if removeonly is False:
            last.insert(0, scid)
        remove = len(last) - max
        if remove > 0:
            for i in range(remove):
                last.pop()
        self.setList(name, last)

    @bug.buggalo_try_except({'method': 'scutils.filter_bitrate'})
    def filter_bitrate(self, resolved):
        bt = sctop.getSettingAsInt('bitrate')
        if bt > 0 and sctop.getSettingAsBool('bitratefilter'):
            tmp = []
            for s in resolved:
                util.debug("[SC] bitrate video %s vs %s" %
                           (str(s.get('bitrate', 0)), str(bt)))
                if int(s.get('bitrate', 0)) <= bt:
                    util.debug("[SC] pridavam BT %s" %
                               str(s.get('bitrate', 0)))
                    tmp.append(s)
                else:
                    util.debug("[SC] pomaly net pre BT %s" %
                               str(s.get('bitrate', 0)))
            if len(tmp) >= 1:
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
            if 'linfo' in s:
                if lang == 'SK':
                    alist = ['slo', 'sk', 'slk']
                elif lang == 'CZ':
                    alist = ['cze', 'cz', 'ces']
                elif lang == 'EN':
                    alist = ['eng', 'en']
                else:
                    break
                for a in alist:
                    if a in s['linfo']:
                        util.debug(
                            "[SC] pridavam stream s audio jazykom %s %s" %
                            (str(lang), s['lang']))
                        tmp.append(s)
            elif 'lang' in s and s['lang'] != '' and s['lang'] == lang:
                util.debug("[SC] pridavam stream s jazykom %s" % str(lang))
                tmp.append(s)

        if prio is True and len(tmp) > 1:
            tmpq = self.filter_quality(tmp, False)
            if len(tmpq) >= 1:
                util.debug("[SC] vyberame najlepsi stream z %s" % str(tmpq))
                return [tmpq[0]]
        elif len(tmp) == 1:
            return tmp

        return [] if prio is True else resolved

    @bug.buggalo_try_except({'method': 'scutils.filter_lang'})
    def filter_lang(self, resolved, prio=False):
        if sctop.getSettingAsBool('filter_audio') is False:
            util.debug("[SC] nemame zapnute filtrovanie podla audia")
            return resolved

        sctop.win.setProperty('lang.1', sctop.getSetting('filter_lang.1'))
        sctop.win.setProperty('lang.2', sctop.getSetting('filter_lang.2'))

        util.debug("[SC] lang.1 %s" % sctop.getSetting('filter_lang.1'))
        tmp = self._filter_lang(resolved, sctop.getSetting('filter_lang.1'),
                                prio)
        if len(tmp) == 0:
            util.debug("[SC] lang.2 %s" % sctop.getSetting('filter_lang.2'))
            tmp = self._filter_lang(resolved,
                                    sctop.getSetting('filter_lang.2'), prio)

        if len(tmp) == 1:
            util.debug("[SC] mame vybrany len jeden stream %s" % str(tmp))
            return tmp

        if len(tmp) >= 1 and prio is False:
            util.debug(
                "[SC] prioprita podla videa, vyberame prvy stream s audiom")
            resolved = [tmp[0]]

        return resolved

    @bug.buggalo_try_except({'method': 'scutils.filter_quality'})
    def filter_quality(self, resolved, prio=False):
        if sctop.getSettingAsBool('filter_video') is False:
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

        if prio is True and res in sources:
            return self.filter_lang(sources[res])

        if prio is False and res in sources:
            util.debug(
                '[SC] mame prioritu vyberame prvy stream s videom pre rozlisenie %s'
                % str(res))
            return [sources[res][0]]

        return resolved

    @bug.buggalo_try_except({'method': 'scutils.filter_hevc'})
    def filter_hevc(self, resolved):
        tmp = []
        for i in resolved:
            if not ('vinfo' in i and re.search('HEVC', i['vinfo'])):
                tmp.append(i)
            else:
                util.debug("[SC] vyhadzujem HEVC stream")
                pass
        return tmp

    @bug.buggalo_try_except({'method': 'scutils.filter_3d'})
    def filter_3d(self, resolved):
        tmp = []
        for i in resolved:
            if '3D-SBS' not in i['quality']:
                tmp.append(i)
            else:
                util.debug("[SC] vyhadzujem 3D stream")
                pass
        return tmp

    @bug.buggalo_try_except({'method': 'scutils.filter_priority'})
    def filter_priority(self, resolved):
        if sctop.getSettingAsBool('filter_enable') is False:
            util.debug(
                "[SC] nemame zapnuty filter streamov, tak nic nefiltrujeme")
            return resolved

        if sctop.getSettingAsBool('filter_hevc'):
            resolved = self.filter_hevc(resolved)

        if sctop.getSettingAsBool('filter_3d'):
            resolved = self.filter_3d(resolved)

        if sctop.getSettingAsBool(
                'filter_audio') and not sctop.getSettingAsBool('filter_video'):
            return self.filter_lang(resolved, False)

        if not sctop.getSettingAsBool(
                'filter_audio') and sctop.getSettingAsBool('filter_video'):
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
        util.debug("[SC] filter po bitrate: %s" % str(resolved))
        resolved = self.filter_priority(resolved)
        return resolved

    @bug.buggalo_try_except({'method': 'scutils.resolve'})
    def resolve(self, url):
        item = self.provider.video_item()
        item.update({'url': url})

        def select_cb(resolved):
            if len(resolved) > 1 and self.force is False:
                resolved = self.filter_resolved(resolved)

            if len(resolved) > 1 or self.force is True:
                if not sctop.getSettingAsBool('dialog_details'):
                    dialog = xbmcgui.Dialog()
                    opts = []
                    for r in resolved:
                        util.debug('[SC] select_cb r: %s' % str(r))
                        d = defaultdict(lambda: '', r)
                        if d['sinfo'] is True:
                            d['lang'] = '%s+tit' % d['lang']
                        opts.append('%s[B][%s] %s%s[/B] - %s%s' %
                                    (d['provider'][0], d['olang'], d['quality'], d['vinfo'],
                                     d['size'], d['ainfo']))
                    ret = dialog.select(resolved[0]['title'], opts)
                    ret = ret if ret != -1 else False
                    del dialog
                else:
                    listing = []
                    art = resolved[0]['art'] if 'art' in resolved[0] else None
                    img = art[
                        'poster'] if art is not None and 'poster' in art else None
                    for (p, r) in enumerate(resolved):
                        d = defaultdict(lambda: '', r)

                        listitem = xbmcgui.ListItem(
                            label='%s[B][%s] %s%s %s[/B] - %s%s' %
                            (d['provider'][0], d['olang'], d['quality'], d['vinfo'], '',
                             d['size'], d['ainfo']),
                            label2=d['fname'],
                            iconImage=img,
                            thumbnailImage=img)
                        listitem.setProperty("pos", str(p))
                        listing.append(listitem)

                    dialog = DialogSelect("DialogSelect.xml",
                                          "",
                                          listing=listing,
                                          windowtitle=resolved[0]['title'],
                                          multiselect=False,
                                          getmorebutton=False,
                                          richlayout=True)
                    dialog.doModal()
                    item = dialog.result
                    del dialog
                    ret = int(item.getProperty(
                        'pos')) if item is not False else False
                util.debug("[SC] dialog ret: %s" % str(ret))
                if ret is not False:
                    util.debug("[SC] dialog resolved url: %s" %
                               str(resolved[ret]['url']))
                    sctop.win.setProperty('linfo',
                                          json.dumps(resolved[ret]['linfo']))
                    return resolved[ret]
                else:
                    util.debug('[SC] None.........')
                    return None
            sctop.win.setProperty('linfo', json.dumps(resolved[0]['linfo']))
            return resolved[0]

        try:
            return self.provider.resolve(item, select_cb=select_cb)
        except ResolveException as e:
            self._handle_exc(e)


bug.SUBMIT_URL = sctop.submiturl
