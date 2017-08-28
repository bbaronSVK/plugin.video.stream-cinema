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

import resolver
import os
import sys
sys.path.append(os.path.join(os.path.dirname(resolver.__file__), 'usage'))
sys.path.append(os.path.join(os.path.dirname(resolver.__file__), 'contentprovider'))
import buggalo
import json
from provider import ContentProvider
from provider import ResolveException
from provider import cached
from urlparse import urlparse, parse_qs, urlunsplit
import urllib
from hashlib import md5
import util
import xbmcplugin
import xbmcgui
import xbmc
import sctop
import trakt
import tracker

reload(sys)
sys.setrecursionlimit(10000)
sys.setdefaultencoding('utf-8')

class StreamCinemaContentProvider(ContentProvider):
    par = None
    subs = None

    def __init__(self, username=None, password=None, filter=None, uid=None):
        ContentProvider.__init__(self, name='czsklib', base_url=sctop.BASE_URL, username=username,
                                 password=password, filter=filter)
        
        self.tr = tracker.TrackerInfo().getSystemInfo()
        self.uid = uid
        util.UA = self.tr['useragent']
        #util.debug("[SC] tr: %s" % str(self.tr))
        
        util.init_urllib(self.cache)
        cookies = self.cache.get('cookies')
        if not cookies or len(cookies) == 0:
            util.request(self.base_url)
        self.ws = None
        
        
    def capabilities(self):
        return ['resolve', 'categories'] # , 'search']
    
    def getSubs(self):
        return self.parent.getSubs()
    
    @buggalo.buggalo_try_except({'method': 'scinema._url'})
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
            o = urlparse(self.base_url)
        else:
            o = urlparse(url)
        q = parse_qs(o.query)
        q.update({'uid': self.uid, 'ver': sctop.API_VERSION})
        if not url.startswith('http'):
            n = [str(o[0]),str(o[1]),str(o[2]).rstrip('./') + '/' + url.lstrip('./'),str(o[3]), '']
        else:
            n = [str(o[0]),str(o[1]),str(o[2]),str(o[3]), '']
        n[3] = urllib.urlencode(q, True)
        nurl = urlunsplit(n)
        return nurl

    @buggalo.buggalo_try_except({'method': 'scinema._json'})
    def _json(self, url, post=False):
        try:
            return json.loads(self.get_data_cached(url, post))
        except Exception, e:
            util.debug("[SC] chybna URL %s" % str(url))
            util.error(e)
    
    @buggalo.buggalo_try_except({'method': 'scinema.items'})
    def items(self, url=None, data=None):
        self.subs = self.getSubs()
        if data is None and url is not None:
            data = self._json(url)
        if data is None or isinstance(data, list):
            self._oldapi()
        result = []
        if data is not None and data.get("menu"):
            for m in data["menu"]:
                try:
                    #util.debug("MENU: %s" % str(m))
                    if m['type'] == 'dir':
                        item = self._dir_item(m)
                    elif m['type'] == 'video':
                        item = self._video_item(m)
                    else:
                        item = self._video_item(m)
                    result.append(item)
                except Exception:
                    pass
            if 'system' in data:
                #util.debug("SYSTEM!!!!")
                self.system(data["system"])
        else:
            result = [{'title': 'i failed', 'url':'failed', 'type':'dir'}]
        #util.debug('--------------------- DONE -----------------')
        return result

    @buggalo.buggalo_try_except({'method': 'scinema.system'})
    def system(self, data):
        if "setContent" in data:
            xbmcplugin.setContent(int(sys.argv[1]), data["setContent"])
        
        if "setPluginCategory" in data:
            xbmcplugin.setPluginCategory(int(sys.argv[1]), data["setPluginCategory"])
        
        if "addSortMethod" in data:
            xbmcplugin.addSortMethod(int(sys.argv[1]), sctop.sortmethod[int(data["addSortMethod"])])

        if data.get('addSortMethods'):
            for m in data.get("addSortMethods"):
                xbmcplugin.addSortMethod(int(sys.argv[1]), sctop.sortmethod[int(m)])
        
        if "setPluginFanart" in data:
            xbmcplugin.setPluginFanart(int(sys.argv[1]), data["setPluginFanart"])

    @buggalo.buggalo_try_except({'method': 'scinema.categories'})
    def categories(self):
        return self.list(self._url(''))
    
    @buggalo.buggalo_try_except({'method': 'scinema.list'})
    def list(self, url):
        self.base_url = url
        return self.items(url)
    
    def _oldapi(self):
        xbmc.executebuiltin("Container.Update(plugin://%s)" % (sctop.__scriptid__))
        
    @buggalo.buggalo_try_except({'method': 'scinema.get_data_cached'})
    #@cached(ttl=1)
    def get_data_cached(self, url, post=False):
        try:
            url.index('/json/')
            self._oldapi()
        except Exception:
            pass
        headers = {
            'X-UID': self.uid,
            'X-LANG': self.tr['language'],
            'X-VER': sctop.API_VERSION,
            'Accept' : 'application/vnd.bbaron.kodi-plugin-v%s+json' % (sctop.API_VERSION),
        }
        url = self._url(url)
        try:
            if post != False:
                util.debug("POST URL: %s %s" % (url, str(post)))
                return util.post(url, post, headers)
            util.debug("GET URL: %s" % url)
            return util.request(url, headers)
        except:
            sctop.dialog.ok("error", url)
            return None
        #util.debug("RET: %s" % str(ret))
    
    @buggalo.buggalo_try_except({'method': 'scinema._dir_item'})
    def _dir_item(self, m):
        if 'url' in m:
            item = self.dir_item(title=m['title'], url=self._url(m['url']))
        else:
            item = self.dir_item(title=m['title'])
        for k in m.keys():
            if k != 'url':
                item[k] = m[k]
        item = self.ctx(item, m)

        return item

    @buggalo.buggalo_try_except({'method': 'scinema._video_item'})
    def _video_item(self, m):
        item = self.video_item(self._url(m['url']), img=m['poster'])
        for k in m.keys():
            if k != 'url':
                item[k] = m[k]
        item = self.ctx(item, m)
        return item
    
    def ctx(self, item, data):
        menu = {}
        #util.debug("CTX ITM: %s" % str(item))
        #util.debug("CTX DAT: %s" % str(data))
        #if 'dir' in data and data['dir'] == 'tvshows':
        
        if 'tl' in item:
            menu.update({"$30918": {"action": "add-to-lib-trakt", "tl": item['tl'], "title": data['title']}})
        
        if 'id' in data and data['id'].isdigit():
            menu.update({"$30942": {"cmd":'Action("Info")'}})
            params = self.parent.params()
            params.update({'action':'play-force','url':item['url'],'play':item['url'],'dtitle':item['title'],'force':'true'})
            menu.update({"$30949": params})
            try:
                id = int(data['id'])
                #menu.update({"report stream": {"action": "report", "id": data['id'], "title": data['title']}})
            except Exception:
                pass
            
        if 'trakt' in data and data['trakt'].isdigit() and trakt.getTraktCredentialsInfo() == True:
            #name, imdb, tvdb, content
            content = 'series' if 'season' in data and data['season'].isdigit() else 'movie' 
            imdb = 'tt%07d' % int(data['imdb']) if 'imdb' in data else 0
            tvdb = data['tvdb'] if 'tvdb' in data else 0
            menu.update({"Trakt menu": {"action": "traktManager", 'name': data['title'], 'imdb': imdb, 'tvdb': tvdb, 'content':content}})
            
        if 'id' in data and data['id'].isdigit() and 'season' not in data:
            menu.update({"$30918": {"action": "add-to-lib", "id": 'movies/%d' % int(data['id']), "title": data['title']}})
            
        if 'id' in data and data['id'] == 'series':
            menu.update({"$30923": {"action": "add-to-lib-sub", "id": data['id'], "title": data['title']}})
            
        if 'id' in data and data['id'] == 'movies':
            menu.update({"$30918": {"action": "add-to-lib", "id": data['id'], "title": data['title']}})
            menu.update({"$30926": {"action": "add-to-lib", "id": data['id'], "title": data['title'], "force": "1"}})
            #util.debug("[SC] MAME menu!")
            
        #util.debug("[SC] data %s" % str(data))
        if 'season' in data or data.get('id') == 'series':
            if data['id'] in self.subs.keys() and data['id'] != 'series':
                item['title'] = "[COLOR red]*[/COLOR] %s" % item['title']
                #util.debug("[SC] Serial je v odoberani: %s" % data['title'])
                menu.update({"$30924": {"action": "remove-from-sub", "id": data['id'], "title": data['title']}})
            else:
                #util.debug("[SC] Serial neodoberam: %s" % data['title'])
                menu.update({"$30918": {"action": "add-to-lib", "id": data['id'], "title": data['title']}})
                menu.update({"$30923": {"action": "add-to-lib-sub", "id": data['id'], "title": data['title']}})
        #menu.update({"$30922": {"cmd":'Addon.OpenSettings("%s")' % sctop.__scriptid__}})
        #menu.update({"run Schedule": {"action": "subs"}})
        #menu.update({"test": {"action": "test"}})
        #menu.update({"last": {'cp': 'czsklib', 'list': 'http://stream-cinema.online/json/movies-a-z'}})
        
        item['menu'] = menu
        return item
    
    @buggalo.buggalo_try_except({'method': 'scinema.search'})
    def search(self, keyword, id=None):
        sq = {'search': keyword, 'id': id}
        if str(id).startswith('search-people'):
            sq.update({'ms':'1'})
        util.debug("[SC] search %s" % str(sq))
        return self.items(None, self._json(self._url('/Search/'), sq))

    @buggalo.buggalo_try_except({'method': 'scinema._resolve'})
    def _resolve(self, itm):
        if itm is None:
            return None;
        if itm.get('provider') == 'plugin.video.online-files' and itm.get('params').get('cp') == 'webshare.cz':
            if sctop.getSetting('wsuser') == "":
                res = sctop.yesnoDialog(sctop.getString(30945), sctop.getString(30946), "")
                if res == True:
                    sctop.openSettings('201.101')
                    return None
            try:
                from myprovider.webshare import Webshare as wx
                self.ws = wx(sctop.getSetting('wsuser'), sctop.getSetting('wspass'))
                if not self.ws.login():
                    res = sctop.yesnoDialog(sctop.getString(30945), sctop.getString(30946), "")
                    if res == True:
                        sctop.openSettings('201.101')
                    return None
                else:
                    udata = self.ws.userData()
                    util.debug("[SC] udata: %s" % str(udata))
                    if udata == False:
                        util.debug("[SC] NIEJE VIP ucet")
                        sctop.infoDialog(sctop.getString(30947), icon="WARNING")
                        sctop.sleep(5000)
                    elif int(udata) <= 14:
                        sctop.infoDialog(sctop.getString(30948) % str(udata), icon="WARNING")
                        util.debug("[SC] VIP ucet konci")

                itm['url'] = self.ws.resolve(itm.get('params').get('play').get('ident'))
            except:
                buggalo.onExceptionRaised()
                pass
                        
        else:
            try:
                raise ResolveException('zatial nic...')
                hmf = urlresolver.HostedMediaFile(url=itm['url'], include_disabled=False,
                                                  include_universal=False)
                if hmf.valid_url() is True:
                    try:
                        itm['url'] = hmf.resolve()
                    except:
                        pass
            except:
                pass
        itm['title'] = self.parent.encode(itm['title'])
        
        return itm
    
    @buggalo.buggalo_try_except({'method': 'scinema.resolve'})
    def resolve(self, item, captcha_cb=None, select_cb=None):
        #util.debug("ITEM RESOLVE: " + str(item))
        item['url'] = self._url(item['url'])
        if sctop.BASE_URL in item['url']:
            data = self._json(item['url']) #json.loads(self.get_data_cached(item['url']))
            if 'strms' in data:
                util.debug("[SC] data info: %s" % str(data['info']))
                out = [sctop.merge_dicts(data['info'], i) for i in data['strms']]
                data = out
            #util.debug("[SC] data: %s" % str(data))
            if len(data) < 1:
                raise ResolveException('Video is not available.')
            return self._resolve(select_cb(data))
        else:
            return self._resolve(item)

    def keyboard(self, title, action):
        k = xbmc.Keyboard('', title);
        k.doModal()
        q = k.getText() if k.isConfirmed() else None
        if (q == None or q == ''): 
            return
        q = urllib.quote_plus(q)
        url = '%s?action=%s&q=%s' % (sys.argv[0], action, q)
        control.execute('Container.Update(%s)' % url)
        
buggalo.SUBMIT_URL = sctop.submiturl