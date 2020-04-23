# -*- coding: UTF-8 -*-
# /*
# *      Copyright (C) 2017 bbaron
# *
# *
# *  This Program is free software; you can redistribute it and/or modify
# *  it under the terms of the GNU General Public License as published by
# *  the Free Software Foundation; either version 2, or (at your option)
# *  any later version.
# *
# *  This Program is distributed in the hope that it will be useful,
# *  but WITHOUT ANY WARRANTY; without even the implied warranty of
# *  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# *  GNU General Public License for more details.
# *
# *  You should have received a copy of the GNU General Public License
# *  along with this program; see the file COPYING.  If not, write to
# *  the Free Software Foundation, 675 Mass Ave, Cambridge, MA 02139, USA.
# *  http://www.gnu.org/copyleft/gpl.html
# *
# */

import sys

import os
import resolver

sys.path.append(os.path.join(os.path.dirname(resolver.__file__), 'usage'))
sys.path.append(
    os.path.join(os.path.dirname(resolver.__file__), 'contentprovider'))
import bug
import json
from provider import ContentProvider
from provider import ResolveException
from urlparse import urlparse, parse_qs, urlunsplit
from myprovider.webshare import Webshare as wx
from myprovider.kraska import Kraska
import urllib
import util
import xbmcgui
import xbmcplugin
import xbmc
import sctop
import trakt
import tracker
import traceback
import datetime

reload(sys)
sys.setrecursionlimit(10000)
sys.setdefaultencoding('utf-8')


class StreamCinemaContentProvider(ContentProvider):
    par = None
    subs = None

    def __init__(self, username=None, password=None, filter=None, uid=None):
        ContentProvider.__init__(self,
                                 name='czsklib',
                                 base_url=sctop.BASE_URL,
                                 username=username,
                                 password=password,
                                 filter=filter)

        self.tr = tracker.TrackerInfo().getSystemInfo()
        self.uid = uid
        util.UA = self.tr['useragent'] + ' ver' + str(
            sctop.addonInfo('version'))
        #util.debug("[SC] tr: %s" % str(self.tr))
        self.cache = sctop.cache
        self.ws = wx(sctop.getSetting('wsuser'), sctop.getSetting('wspass'),
                     self.cache)
        util.debug("[SC] init cache %s" % self.cache.__class__.__name__)
        util.init_urllib(self.cache)
        cookies = self.cache.get('cookies')
        hasTrakt = str(sctop.getSetting('trakt.token') != '')
        util.debug('[SC] has trakt: %s' % hasTrakt)
        sctop.win.setProperty('sc.trakt', hasTrakt)

    def capabilities(self):
        return ['resolve', 'categories']  # , 'search']

    def getSubs(self):
        return self.parent.getSubs()

    @bug.buggalo_try_except({'method': 'scinema._url'})
    def _url(self, url):
        if url.startswith('plugin://'):
            return url

        if url.startswith('cmd://'):
            if '__self__' in url:
                url.replace('__self__', sctop.__scriptid__)
            return url

        if url.startswith('/'):
            url = sctop.BASE_URL + url

        if not url.startswith('http'):
            util.debug('[SC] nemame http v URL %s' % url)
            o = urlparse(self.base_url)
        else:
            o = urlparse(url)
        q = parse_qs(o.query)
        q.update({
            'uid': self.uid,
            'ver': sctop.API_VERSION,
            'lang': sctop.KODI_LANG,
            'v': sctop.addonInfo('version')
        })

        util.debug('[SC] providers [%s] [%s]' % (str(sctop.getSetting('kruser')), str(sctop.getSetting('wsuser'))))
        if sctop.getSetting('kruser') != '' and sctop.getSetting('wsuser') != '':
            q.update({'pro': 'kraska,webshare'})
        elif sctop.getSetting('kruser') != '':
            q.update({'pro': 'kraska'})
        elif sctop.getSetting('wsuser') != '':
            q.update({'pro': 'webshare'})

        if sctop.getSettingAsBool('filter_audio'):
            q.update({'l': sctop.getSetting('filter_lang.1')})
        if not url.startswith('http'):
            n = [
                str(o[0]),
                str(o[1]),
                str(o[2]).rstrip('./') + '/' + url.lstrip('./'),
                str(o[3]), ''
            ]
        else:
            n = [str(o[0]), str(o[1]), str(o[2]), str(o[3]), '']
        n[3] = urllib.urlencode(q, True)
        nurl = urlunsplit(n)
        return nurl

    @bug.buggalo_try_except({'method': 'scinema._json'})
    def _json(self, url, post=False):
        try:
            return json.loads(self.get_data_cached(url, post))
        except Exception as e:
            util.debug("[SC] chybna URL %s" % str(url))
            util.error(e)
        return None

    @bug.buggalo_try_except({'method': 'scinema.items'})
    def items(self, url=None, data=None):
        self.subs = self.getSubs()
        if data is None and url is not None:
            data = self._json(url)
        result = []
        if data is not None and data.get("menu"):
            for m in data["menu"]:
                try:
                    if 'visible' in m and not sctop.getCondVisibility(
                            m['visible']):
                        # util.debug('[SC] item invisible %s' % m.title)
                        continue
                    if m['type'] == 'dir':
                        # util.debug('[SC] dir item')
                        item = self._dir_item(m)
                    elif m['type'] == 'video':
                        # util.debug('[SC] video item')
                        item = self._video_item(m)
                    else:
                        # util.debug('[SC] default video item')
                        item = self._video_item(m)
                    # util.debug('[SC] pridavam polozku do vysledku')
                    result.append(item)
                except Exception:
                    util.debug('[SC] item error: %s' %
                               str(traceback.format_exc()))
                    pass
            try:
                skeys = sctop.win.getProperty('sc.filter._keys')
                if skeys != '':
                    fremove = json.loads(skeys)
                    if fremove is not None:
                        for i in fremove:
                            util.debug('[SC] remove filter %s' % str(i))
                            sctop.win.clearProperty('sc.filter.%s' % str(i))
                sctop.win.clearProperty('sc.filter._keys')
            except:
                sctop.win.clearProperty('sc.filter._keys')
                pass
            if 'system' in data:
                self.system(data["system"])
            if 'filter' in data:
                try:
                    fkeys = []
                    for k, v in data['filter'].items():
                        if k != 'meta':
                            fkeys.append(k)
                            util.debug('[SC] filter %s: %s' % (str(k), str(v)))
                            sctop.win.setProperty('sc.filter.%s' % str(k),
                                                  str(v))
                    sctop.win.setProperty('sc.filter._keys', json.dumps(fkeys))
                except:
                    sctop.win.clearProperty('sc.filter._keys')
                    util.debug('[SC] filter err %s' %
                               str(traceback.format_exc()))
        else:
            result = [{'title': 'i failed', 'url': 'failed', 'type': 'dir'}]
            self.parent.endOfDirectory(succeeded=False)
        # util.debug('[SC] vraciam result: %s' % str(result))
        return result

    @bug.buggalo_try_except({'method': 'scinema.system'})
    def system(self, data, cl=False):
        util.debug("[SC] SYSYEM CL: %s" % str(cl))
        if cl is False and "setContent" in data:
            xbmcplugin.setContent(int(sys.argv[1]), data["setContent"])
            '''
            view_mode=data["setContent"].lower()
            skin_name=xbmc.getSkinDir() # nacitame meno skinu
            util.debug("[SC] skin_name='"+skin_name+"'")
            try:
                util.debug("[SC] view mode is "+view_mode)
                view_codes=sctop.ALL_VIEW_CODES.get(view_mode)
                view_code=view_codes.get(skin_name)
                util.debug("[SC] view code for "+view_mode+" in "+skin_name+" is "+str(view_code))
                xbmc.executebuiltin("Container.SetViewMode("+str(view_code)+")")
                #xbmc.executebuiltin("Container.Refresh")
            except:
                util.debug("[SC] Unable to find view code for view mode "+str(view_mode)+" and skin "+skin_name)
            '''

        if cl is False and "setPluginCategory" in data:
            xbmcplugin.setPluginCategory(int(sys.argv[1]),
                                         data["setPluginCategory"])

        if cl is False and "addSortMethod" in data:
            xbmcplugin.addSortMethod(
                int(sys.argv[1]), sctop.sortmethod[int(data["addSortMethod"])])

        if cl is False and data.get('addSortMethods'):
            for m in data.get("addSortMethods"):
                xbmcplugin.addSortMethod(int(sys.argv[1]),
                                         sctop.sortmethod[int(m)])

        if cl is False and "setPluginFanart" in data:
            xbmcplugin.setPluginFanart(int(sys.argv[1]),
                                       data["setPluginFanart"])

        if cl is False and "version" in data:
            util.info("[SC] kontrola verzie: %s %s" %
                      (str(sctop.addonInfo('version')), data["version"]))
            if sctop.addonInfo('version') != data[
                "version"] and sctop.getSetting('ver') != data['version']:
                try:
                    sctop.dialog.ok(
                        sctop.getString(30954),
                        sctop.getString(30955) % str(data['version']))
                except:
                    pass
                xbmc.executebuiltin('UpdateAddonRepos')
                sctop.setSetting('ver', data['version'])
                sctop.setSetting('ws_checkssl', 'false')
                sctop.setSetting('check_ssl1', 'false')
                sctop.setSetting('usecache', 'true')
            if sctop.getSettingAsBool(
                    'cachemigrate'
            ) == '' or sctop.getSettingAsBool('cachemigrate') is False:
                self.parent.cacheMigrate()
                pass
            pass

        if cl is False and "focus" in data:
            self.parent.system = {"focus": data['focus']}

        if cl is True and "focus" in data:
            try:
                self.parent.endOfDirectory()
                util.debug("[SC] nastavujem focus na: %d" % int(data['focus']))
                xel = xbmcgui.Window(xbmcgui.getCurrentWindowId())
                ctr = xel.getControl(xel.getFocusId())
                ctr.selectItem(int(data['focus']))
            except Exception as e:
                util.debug("[SC] error focus :-( %s" %
                           str(traceback.format_exc()))
                pass

    @bug.buggalo_try_except({'method': 'scinema.categories'})
    def categories(self):
        return self.list(self._url(''))

    @bug.buggalo_try_except({'method': 'scinema.list'})
    def list(self, url):
        self.base_url = self._url(url)
        return self.items(url)

    def _oldapi(self):
        xbmc.executebuiltin("Container.Update(plugin://%s)" %
                            (sctop.__scriptid__))

    @bug.buggalo_try_except({'method': 'scinema.get_data_cached'})
    def get_data_cached(self, url, post=False):
        try:
            url.index('/json/')
            self._oldapi()
        except Exception:
            pass
        headers = {
            'X-UID':
                self.uid,
            'X-LANG':
                self.tr['language'],
            'X-VER':
                sctop.API_VERSION,
            'Accept':
                'application/vnd.bbaron.kodi-plugin-v%s+json' %
                (sctop.API_VERSION),
        }
        url = self._url(url)
        code = None
        try:
            if post != False:
                util.debug("POST URL: %s %s" % (url, str(post)))
                (ret, code) = sctop.post(url, post, headers, "extend")
                self.handleHttpError(code)
                return ret
            util.info("GET x URL: %s" % url)
            ret = False
            if sctop.getSettingAsBool('usecache') is not False:
                util.debug("[SC] skusam cache")
                ret = self.cache.get(str(url))
            if not ret:
                util.debug("[SC] url BEZ cache %s" % str(url))
                (ret, code, info) = sctop.request(url, headers, "info")
                util.debug("[SC] code: %s %s" % (str(code), str(info)))
                self.handleHttpError(code, data=ret, i=info)
                if code == 200:
                    ttl = datetime.timedelta(hours=2)
                    try:
                        util.debug("[SC] info: %s " % str(info))
                        if 'x-ttl' in info:
                            ttl = datetime.timedelta(
                                seconds=int(info.get('x-ttl')))
                            util.debug("[SC] mame TTL: %s" % str(ttl))
                    except:
                        pass
                    try:
                        self.cache.cache.set(str(url), ret, expiration=ttl)
                    except:
                        self.cache.set(str(url), ret)
            else:
                util.debug("[SC] url z cache %s" % str(url))
            util.debug("[SC] return data")
            return ret
        except Exception as e:
            inet = sctop.getCondVisibility('System.InternetState')
            util.debug("[SC] inet scinema status: %s | %s" %
                       (str(inet), str(e)))
            if inet is False or inet == 0:
                HANDLE = int(sys.argv[1])
                xbmcplugin.endOfDirectory(HANDLE, succeeded=False)
                sctop.dialog.ok("internet",
                                'Skontrolujte pripojenie na internet')
                return False
            util.error('[SC] ERROR URL: --------- %s --------' %
                       str(traceback.format_exc()))
            if code is None:
                sctop.dialog.ok("error", url)
            return False

    def handleHttpError(self, code, data=None, i=None):
        if int(code) == 200:
            return
        if int(code) == 429:
            util.debug("[SC] 429: %s " % str(i))
            sctop.dialog.ok('error', sctop.getString(30957))
            self.bSleep(50)
            raise Exception('API call')
        if int(code) == 503:
            util.debug("[SC] cloudflare?")
            pass
        else:
            util.debug("[SC] data: %s" % str(data))
            sctop.dialog.ok('error', 'server error')
            self.bSleep(30)
            raise Exception('server error: %s' % str(code))

    def bSleep(self, time):
        xbmc.executebuiltin("ActivateWindow(busydialog)")
        sctop.sleep(time * 1000)
        xbmc.executebuiltin("Dialog.Close(busydialog)")

    @bug.buggalo_try_except({'method': 'scinema._dir_item'})
    def _dir_item(self, m):
        if 'url' in m:
            item = self.dir_item(title=m['title'], url=m['url'])
        else:
            item = self.dir_item(title=m['title'])
        for k in m.keys():
            if k != 'url':
                item[k] = m[k]
        item = self.ctx(item, m)
        return item

    @bug.buggalo_try_except({'method': 'scinema._video_item'})
    def _video_item(self, m):
        item = self.video_item(m['url'], img=m['poster'])
        for k in m.keys():
            if k != 'url':
                item[k] = m[k]
        item = self.ctx(item, m)
        return item

    @bug.buggalo_try_except({'method': 'scinema.ctx'})
    def ctx(self, item, data):
        try:
            from collections import OrderedDict
            menu = OrderedDict()
        except ImportError as e:
            menu = {}
        # util.debug("CTX ITM: %s" % str(item))
        # util.debug("CTX DAT: %s" % str(data))
        # if 'dir' in data and data['dir'] == 'tvshows':

        if 'csearch' in item:
            menu.update({
                "Edit": {
                    "action": "csearch-edit",
                    "id": item['id'],
                    "title": item['csearch']
                }
            })
            menu.update({
                "Remove": {
                    "action": "csearch-remove",
                    "id": item['id'],
                    "title": item['csearch']
                }
            })

        if 'tl' in item:
            menu.update({
                "$30918": {
                    "action": "add-to-lib-trakt",
                    "tl": item['tl'],
                    "title": data['title'],
                    'tu': item['tu'] if 'tu' in item else 'me'
                }
            })

        if 'list' in item and item['list'] == 'liked':
            menu.update({
                "$30977": {
                    "action": "traktListUnlike",
                    "title": item['title'],
                    "tu": item['tu'],
                    "id": item['id']
                }
            })
        elif 'list' in item and item['tu'] != 'me':
            menu.update({
                "$30978": {
                    "action": "traktListLike",
                    "title": data['title'],
                    "tu": item['tu'],
                    "id": item['id']
                }
            })

        if 'list' in item and item['list'] == 'user' and item['tu'] == 'me':
            menu.update({
                "$30979": {
                    'action': 'traktListCustomRemove',
                    'title': data['title'],
                    'id': item['id'],
                }
            })
        elif 'list' in item:
            menu.update({
                "$30980": {
                    'action': 'traktListClone',
                    'title': data['title'],
                    'id': item['id'],
                    'tu': item['tu']
                }
            })
            menu.update({
                "$30981": {
                    'action': 'traktListAppendToCustom',
                    'id': item['id'],
                    'tu': item['tu']
                }
            })

        if 'id' in data and data['id'].isdigit():
            if 'imdb' in data and data['imdb'] > 0:
                menu.update({
                    "$30942": {
                        "action": "info",
                        'imdb': "tt%07d" % int(data['imdb'])
                    }
                })  # {"cmd":'Action("Info")'}})
            else:
                menu.update({"$30942": {"cmd": 'Action("Info")'}})
            params = self.parent.params()
            params.update({
                'action': 'play-force',
                'url': item['url'],
                'play': item['url'],
                'dtitle': item['title'],
                'force': 'true'
            })
            menu.update({"$30949": params})
            try:
                id = int(data['id'])
                # menu.update({"report stream": {"action": "report", "id": data['id'], "title": data['title']}})
            except Exception:
                pass

        if 'trakt' in data and data['trakt'].isdigit(
        ) and trakt.getTraktCredentialsInfo() is True:
            # name, imdb, tvdb, content
            content = 'series' if 'season' in data and data['season'].isdigit(
            ) else 'movie'
            menu.update({
                "Trakt menu": {
                    "action": "traktManager",
                    'name': data['title'],
                    'trakt': data['trakt'],
                    'content': content
                }
            })

        if 'id' in data and data['id'].isdigit() and 'season' not in data:
            menu.update({
                "$30918": {
                    "action": "add-to-lib",
                    "id": 'movies/%d' % int(data['id']),
                    "title": data['title']
                }
            })

        if 'id' in data and data['id'] == 'series':
            menu.update({
                "$30923": {
                    "action": "add-to-lib-sub",
                    "id": data['id'],
                    "title": data['title']
                }
            })

        if 'id' in data and data['id'] == 'movies':
            menu.update({
                "$30918": {
                    "action": "add-to-lib",
                    "id": data['id'],
                    "title": data['title']
                }
            })
            menu.update({
                "$30926": {
                    "action": "add-to-lib",
                    "id": data['id'],
                    "title": data['title'],
                    "force": "1"
                }
            })
            # util.debug("[SC] MAME menu!")

        # util.debug("[SC] data %s" % str(data))
        if 'season' in data or data.get('id') == 'series':
            if data['id'] in self.subs.keys() and data['id'] != 'series':
                item['title'] = "[COLOR red]*[/COLOR] %s" % item['title']
                # util.debug("[SC] Serial je v odoberani: %s" % data['title'])
                menu.update({
                    "$30924": {
                        "action": "remove-from-sub",
                        "id": data['id'],
                        "title": data['title']
                    }
                })
            else:
                # util.debug("[SC] Serial neodoberam: %s" % data['title'])
                menu.update({
                    "$30918": {
                        "action": "add-to-lib",
                        "id": data['id'],
                        "title": data['title']
                    }
                })
                menu.update({
                    "$30923": {
                        "action": "add-to-lib-sub",
                        "id": data['id'],
                        "title": data['title']
                    }
                })
        # menu.update({"$30922": {"cmd":'Addon.OpenSettings("%s")' % sctop.__scriptid__}})
        # menu.update({"run Schedule": {"action": "subs"}})
        # menu.update({"test": {"action": "test"}})
        # menu.update({"last": {'cp': 'czsklib', 'list': 'http://stream-cinema.online/json/movies-a-z'}})

        item['menu'] = menu
        return item

    @bug.buggalo_try_except({'method': 'scinema.search'})
    def search(self, keyword, id=None):
        sq = {'search': keyword, 'id': id}
        if str(id).startswith('search-people'):
            sq.update({'ms': '1'})
        util.debug("[SC] search %s" % str(sq))
        return self.items(data=self._json(self._url('/Search/%s' % id), sq))

    @bug.buggalo_try_except({'method': 'scinema._resolve'})
    def _resolve(self, itm):
        util.debug("[SC] _resolve")
        if itm is None:
            return None
        if itm.get('provider') == 'plugin.video.online-files' or itm.get('provider') == 'webshare':
            if sctop.getSetting('wsuser') == "":
                sctop.infoDialog(sctop.getString(30945),
                                 sctop.getString(30946))
                return None
            try:
                if not self.ws.login():
                    sctop.infoDialog(sctop.getString(30945),
                                    sctop.getString(30946))
                    return None
                else:
                    udata = self.ws.userData()
                    util.debug("[SC] udata: %s" % str(udata))
                    if udata is False:
                        util.debug("[SC] NIEJE VIP ucet")
                        sctop.infoDialog(sctop.getString(30947),
                                         icon="WARNING")
                        sctop.sleep(5000)
                    elif int(udata) <= 14:
                        try:
                            if sctop.getSetting('ws_notify') != '' and int(sctop.getSetting('ws_notify')) > int(datetime.datetime.now().strftime("%s")):
                                sctop.infoDialog(sctop.getString(30948) % str(udata),
                                                 icon="WARNING")
                            else:
                                sctop.setSetting("ws_notify", str(int(datetime.datetime.now().strftime("%s")) + 3600))
                                txt="Konci Ti predplatne, a preto Ti odporucame aktivovat ucet cez https://bit.ly/sc-kra " \
                                + "za zvyhodnene ceny. " \
                                + "Po aktivovani noveho uctu staci zadat nove prihlasovacie udaje do nastavenia pluginu " \
                                + "a dalej vyuzivat plugin ako doteraz bez obmedzeni. "
                                sctop.dialog.ok("Upozornenie...", txt)
                        except:
                            util.debug('[SC] notify error %s' % str(traceback.format_exc()))
                        util.debug("[SC] VIP ucet konci")

                try:
                    util.debug('[SC] ideme pre webshare ident %s' % itm['url'])
                    ident = self._json(self._url(itm['url']))['ident']
                except:
                    ident = '6d8359zW1u'
                    pass

                try:
                    jsdata = json.loads(sctop.request(
                        self._url('/Stats/file')))
                    if 'ident' in jsdata:
                        sctop.request(self.ws.resolve(jsdata['ident']))
                except Exception as e:
                    pass

                itm['url'] = self.ws.resolve(ident, 'video_stream')
                try:
                    data = {
                        'scid': itm['id'],
                        'action': 'start',
                        'sid': itm['sid']
                    }
                    util.debug("[SC] prehravanie %s" % str(data))
                    sctop.player.scid = itm['id']
                    sctop.player.action(data)
                except Exception as e:
                    util.debug(
                        '[SC] nepodarilo sa vykonat akciu "start" %s | %s' %
                        (str(e), str(traceback.format_exc())))

                try:
                    if itm['subs'] is not None and "webshare.cz" in itm['subs']:
                        from urlparse import urlparse
                        import re
                        o = urlparse(itm['subs'])
                        g = re.split('/', o[2] if o[5] == '' else o[5])
                        util.debug("[SC] webshare titulky: %s | %s" %
                                   (str(g[2]), itm['subs']))
                        url = self.ws.resolve(g[2], 'file_download')
                        itm['subs'] = url
                        content = sctop.request(url)
                        itm['subs'] = self.parent.saveSubtitle(
                            content, 'cs', False)
                        util.debug("[SC] posielam URL na titulky: %s" %
                                   itm['subs'])
                except Exception as e:
                    util.debug("[SC] chyba WS titlkov... %s | %s" %
                               (str(e), str(traceback.format_exc())))
                    pass
                itm['headers'] = {'User-Agent': util.UA}
            except Exception as e:
                util.debug("[SC] chyba.... %s %s" %
                           (str(e), str(traceback.format_exc())))
                bug.onExceptionRaised()
                pass
        elif itm.get('provider') == 'kraska':
            try:
                kra = Kraska(sctop.getSetting('kruser'), sctop.getSetting('krpass'),
                             self.cache)

                try:
                    util.debug('[SC] ideme pre kra ident %s' % itm['url'])
                    ident = self._json(self._url(itm['url']))['ident']
                except Exception as e:
                    util.debug('[SC] error get ident: %s' % str(traceback.format_exc()))
                    return

                itm['url'] = kra.resolve(ident)
                itm['headers'] = {'User-Agent': util.UA}
                try:
                    if itm['subs'] is not None:
                        if "kra.sk" in itm['subs']:
                            import urlparse
                            import re
                            o = urlparse(itm['subs'])
                            g = re.split('/', o[2] if o[5] == '' else o[5])
                            util.debug("[SC] kra.sk titulky: %s | %s" %
                                       (str(g[2]), itm['subs']))
                            url = self.kr.resolve(g[2])
                            itm['subs'] = url
                            content = sctop.request(url)
                            itm['subs'] = self.parent.saveSubtitle(
                                content, 'cs', False)
                            util.debug("[SC] posielam URL na titulky: %s" %
                                       itm['subs'])
                except Exception as e:
                    util.debug("[SC] chyba KRA titlkov... %s | %s" %
                               (str(e), str(traceback.format_exc())))
                    pass
            except Exception as e:
                util.debug('[SC] kra error')
                pass
        itm['title'] = self.parent.encode(itm['title'])

        return itm

    def resolve(self, item, captcha_cb=None, select_cb=None):
        # util.debug("[SC] ITEM RESOLVE: " + str(item))
        # util.debug("[SC] RESOLVE argv: [%s] " % str(sys.argv))
        sctop.win.setProperty('sc.resume', 'true')
        addparams = sys.argv[3] if 3 in sys.argv else None
        if addparams is not None and re.search('resume:false',
                                               sys.argv.get(3)):
            sctop.win.setProperty('sc.resume', 'false')
        if 'https://' not in item['url'] and 'http://' not in item['url']:
            item['url'] = self._url(item['url'])
        if sctop.BASE_URL in item['url']:
            try:
                data = self._json(item['url'])
            except:
                raise ResolveException('Video is not available.')
            if data is None or data is False:
                raise ResolveException('Video is not available.')
            if 'strms' in data:
                util.debug("[SC] data info: %s" % str(data['info']))
                out = [
                    sctop.merge_dicts(data['info'], i) for i in data['strms']
                ]
                data = out
            # util.debug("[SC] data: %s" % str(data))
            if len(data) < 1:
                raise ResolveException('Video is not available.')
            return self._resolve(select_cb(data))
        else:
            return self._resolve(item)

    @bug.buggalo_try_except({'method': 'scinema.keyboard'})
    def keyboard(self, title, action):
        k = xbmc.Keyboard('', title)
        k.doModal()
        q = k.getText() if k.isConfirmed() else None
        if (q == None or q == ''):
            return
        q = urllib.quote_plus(q)
        url = '%s?action=%s&q=%s' % (sys.argv[0], action, q)
        control.execute('Container.Update(%s)' % url)


bug.SUBMIT_URL = sctop.submiturl
