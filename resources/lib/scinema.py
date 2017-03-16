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
import urllib
import util
import xbmcplugin
import top
import tracker

reload(sys)
sys.setrecursionlimit(10000)
sys.setdefaultencoding('utf-8')

class StreamCinemaContentProvider(ContentProvider):
    par = None
    subs = None

    def __init__(self, username=None, password=None, filter=None, uid=None):
        ContentProvider.__init__(self, name='czsklib', base_url=top.BASE_URL, username=username,
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
        return ['resolve', 'categories', 'search']
    
    def get_subs(self):
        return self.parent.get_subs()
    
    @buggalo.buggalo_try_except({'method': 'scinema._url'})
    def _url(self, url):
        
        if url.startswith('http'):
            return url
        
        if url.startswith('plugin://') or url.startswith('cmd://'):
            return url
        
        if url.startswith('/'):
            return top.BASE_URL + url
        
        return self.base_url.rstrip('/') + '/' + url.lstrip('./')
    
    @buggalo.buggalo_try_except({'method': 'scinema._json'})
    def _json(self, url):
        return json.loads(self.get_data_cached(url))
    
    @buggalo.buggalo_try_except({'method': 'scinema.items'})
    def items(self, url):
        self.subs = self.get_subs()
        data = self._json(url)
        result = []
        if data.get("menu"):
            for m in data["menu"]:
                try:
                    #util.debug("MENU: %s" % str(m))
                    if m['type'] == 'dir':
                        item = self._dir_item(m)
                    else:
                        item = self._video_item(m)
                    result.append(item)
                except Exception:
                    pass
            if 'system' in data:
                #util.debug("SYSTEM!!!!")
                self.system(data["system"])
        else:
            result = [{'title': 'i failed', 'url':'failed'}]
        #util.debug('--------------------- DONE -----------------')
        return result

    @buggalo.buggalo_try_except({'method': 'scinema.system'})
    def system(self, data):
        if "setContent" in data:
            xbmcplugin.setContent(int(sys.argv[1]), data["setContent"])
        
        if "setPluginCategory" in data:
            xbmcplugin.setPluginCategory(int(sys.argv[1]), data["setPluginCategory"])
        
        if "addSortMethod" in data:
            xbmcplugin.addSortMethod(int(sys.argv[1]), top.sortmethod[int(data["addSortMethod"])])

        if data.get('addSortMethods'):
            for m in data.get("addSortMethods"):
                xbmcplugin.addSortMethod(int(sys.argv[1]), top.sortmethod[int(m)])
        
        if "setPluginFanart" in data:
            xbmcplugin.setPluginFanart(int(sys.argv[1]), data["setPluginFanart"])

    @buggalo.buggalo_try_except({'method': 'scinema.categories'})
    def categories(self):
        return self.list(self._url(''))
    
    @buggalo.buggalo_try_except({'method': 'scinema.list'})
    def list(self, url):
        self.base_url = url
        return self.items(url)
    
    @buggalo.buggalo_try_except({'method': 'scinema.get_data_cached'})
    #@cached(ttl=1)
    def get_data_cached(self, url):
        headers = {
            'X-UID': self.uid,
            'X-LANG': self.tr['language'],
            'Accept' : 'application/vnd.bbaron.kodi-plugin-v%s+json' % (top.API_VERSION),
        }
        url = self._url(url)
        util.debug("GET URL: %s" % url)
        ret = util.request(url, headers)
        #util.debug("RET: %s" % str(ret))
        return ret
    
    @buggalo.buggalo_try_except({'method': 'scinema._dir_item'})
    def _dir_item(self, m):
        item = self.dir_item(title=m['title'], url=self._url(m['url']))
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
        
        if 'id' in data and data['type'] != 'dir':
            try:
                id = int(data['id'])
                menu.update({"report stream": {"action": "report", "id": data['id'], "title": data['title']}})
            except Exception:
                pass
            
        if 'id' in data and 'season' not in data:
            menu.update({"$30918": {"action": "add-to-lib", "id": data['id'], "title": data['title']}})
            #util.debug("[SC] MAME menu!")
            
        if 'season' in data:
            #util.debug("[SC] mame SERIAL")
            if data['id'] in self.subs.keys():
                item['title'] = "[COLOR red]*[/COLOR] %s" % item['title']
                #util.debug("[SC] Serial je v odoberani: %s" % data['title'])
                menu.update({"$30924": {"action": "remove-from-sub", "id": data['id'], "title": data['title']}})
            else:
                #util.debug("[SC] Serial neodoberam: %s" % data['title'])
                menu.update({"$30918": {"action": "add-to-lib", "id": data['id'], "title": data['title']}})
                menu.update({"$30923": {"action": "add-to-lib-sub", "id": data['id'], "title": data['title']}})
        menu.update({"$30922": {"cmd":'Addon.OpenSettings("%s")' % top.__scriptid__}})
        item['menu'] = menu
        return item
    @buggalo.buggalo_try_except({'method': 'scinema.search'})
    def search(self, keyword):
        sq = {'search': keyword}
        return self.list_by_params(MOVIES_BASE_URL + '/list/search?' + urllib.urlencode(sq))

    @buggalo.buggalo_try_except({'method': 'scinema._resolve'})
    def _resolve(self, itm):
        if itm is None:
            return None;
        if itm.get('provider') == 'plugin.video.online-files' and itm.get('params').get('cp') == 'webshare.cz':
            if self.parent.getSetting('wsuser') != "":
                try:
                    if self.ws is None:
                        from myprovider.webshare import Webshare as wx
                        self.ws = wx(self.parent.getSetting('wsuser'), self.parent.getSetting('wspass'))
                    itm['url'] = self.ws.resolve(itm.get('params').get('play').get('ident'))
                except:
                    pass
        else:
            try:
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
        data = json.loads(self.get_data_cached(item['url']))
        if len(data) < 1:
            raise ResolveException('Video is not available.')
        if len(data) == 1:
            return self._resolve(data[0])
        elif len(data) > 1 and select_cb:
            return self._resolve(select_cb(data))

    def keyboard(self, title, action):
        k = xbmc.Keyboard('', title);
        k.doModal()
        q = k.getText() if k.isConfirmed() else None
        if (q == None or q == ''): 
            return
        q = urllib.quote_plus(q)
        url = '%s?action=%s&q=%s' % (sys.argv[0], action, q)
        control.execute('Container.Update(%s)' % url)
        
buggalo.SUBMIT_URL = top.submiturl