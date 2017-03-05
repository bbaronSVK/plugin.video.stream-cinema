# -*- coding: UTF-8 -*-
# /*
# *      Copyright (C) 2015 bbaron
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

import buggalo
import json
import os
from provider import ContentProvider
from provider import ResolveException
from provider import cached
import resolver
import sys
import urllib
import util
import xbmcplugin

sys.path.append(os.path.join(os.path.dirname(resolver.__file__), 'usage'))
import tracker

reload(sys)
sys.setrecursionlimit(10000)
sys.setdefaultencoding('utf-8')

BASE_URL="http://stream-cinema.online"
MOVIES_BASE_URL = BASE_URL + "/json"
SERIES_BASE_URL = BASE_URL + "/json/series"

MOVIES_A_TO_Z_TYPE = "movies-a-z"

submiturl = 'http://stream-cinema.online/plugin/submit/'

class StreamCinemaContentProvider(ContentProvider):
    par = None

    def __init__(self, username=None, password=None, filter=None, uid=None):
        ContentProvider.__init__(self, name='czsklib', base_url=MOVIES_BASE_URL, username=username,
                                 password=password, filter=filter)
        
        self.tr = tracker.TrackerInfo().getSystemInfo()
        self.uid = uid
        util.UA = self.tr['useragent']
        
        util.init_urllib(self.cache)
        cookies = self.cache.get('cookies')
        if not cookies or len(cookies) == 0:
            util.request(self.base_url)
        self.ws = None
        
    def capabilities(self):
        return ['resolve', 'categories', 'search']

    @buggalo.buggalo_try_except({'method': 'scinema.categories'})
    def categories(self):
        result = []
        data = json.loads(self.get_data_cached(MOVIES_BASE_URL + '/list/hp'))
        for m in data:
            item = self.dir_item(title=m['title'], url=MOVIES_BASE_URL + str(m['url']))
            result.append(item)
        return result

    @buggalo.buggalo_try_except({'method': 'scinema.a_to_z'})
    def a_to_z(self, url_type):
        result = []
        for letter in ['0-9', 'a', 'b', 'c', 'd', 'e', 'f', 'g', 'e', 'h', 'i', 'j', 'k', 'l', 'm',
                       'n', 'o', 'p', 'q', 'r', 's', 't', 'u', 'v', 'w', 'x', 'y', 'z']:
            item = self.dir_item(title=letter.upper())
            item['url'] = self.base_url + "/movie/letter/" + letter
            result.append(item)
        return result

    @buggalo.buggalo_try_except({'method': 'scinema.list'})
    def list(self, url):
        xbmcplugin.setContent(int(sys.argv[1]), 'movies')
        
        util.debug("URL: %s" % (url))
        if MOVIES_A_TO_Z_TYPE in url:
            return self.a_to_z(MOVIES_A_TO_Z_TYPE)
        if "/letter/" in url:
            return self.list_by_letter(url)
        if "/series/" in url:
            self.base_url = SERIES_BASE_URL
            return self.list_series(url)
        if "/list/" in url:
            return self.list_by_params(url)
        
        return [self.dir_item(title="I failed", url="fail")]

    @buggalo.buggalo_try_except({'method': 'scinema.list_by_params'})
    def list_by_params(self, url):
        data = json.loads(self.get_data_cached(url))
        result = []
        xbmcplugin.addSortMethod(int(sys.argv[1]), xbmcplugin.SORT_METHOD_UNSORTED)
        xbmcplugin.addSortMethod(int(sys.argv[1]), xbmcplugin.SORT_METHOD_VIDEO_RATING)
        xbmcplugin.addSortMethod(int(sys.argv[1]), xbmcplugin.SORT_METHOD_MPAA_RATING)
        xbmcplugin.addSortMethod(int(sys.argv[1]), xbmcplugin.SORT_METHOD_VIDEO_SORT_TITLE)
        xbmcplugin.addSortMethod(int(sys.argv[1]), xbmcplugin.SORT_METHOD_VIDEO_YEAR)
        xbmcplugin.addSortMethod(int(sys.argv[1]), xbmcplugin.SORT_METHOD_DATEADDED)
        xbmcplugin.addSortMethod(int(sys.argv[1]), xbmcplugin.SORT_METHOD_VIDEO_RUNTIME)
        for m in data:
            if m['typ'] == 'dir':
                item = self.dir_item(title=m['title'], url= MOVIES_BASE_URL + m['url'])
                if m['pic'] != '':
                    item['img'] = "%s%s" % (BASE_URL, m['pic'])
            elif m['typ'] != 'latest':
                item = self.dir_item(title=m['title'], url=url + '/' + m['url'])
                if m['pic'] != '':
                    item['img'] = "%s%s" % (BASE_URL, m['pic'])
            else:
                item = self._video_item(m)
                
            self._filter(result, item)
        return result
        
    @buggalo.buggalo_try_except({'method': 'scinema.list_series'})
    def list_series(self, url):
        xbmcplugin.addSortMethod(int(sys.argv[1]), xbmcplugin.SORT_METHOD_UNSORTED)
        xbmcplugin.addSortMethod(int(sys.argv[1]), xbmcplugin.SORT_METHOD_VIDEO_RATING)
        xbmcplugin.addSortMethod(int(sys.argv[1]), xbmcplugin.SORT_METHOD_VIDEO_SORT_TITLE)
        xbmcplugin.addSortMethod(int(sys.argv[1]), xbmcplugin.SORT_METHOD_VIDEO_YEAR)
        xbmcplugin.addSortMethod(int(sys.argv[1]), xbmcplugin.SORT_METHOD_DATEADDED)
        data = json.loads(self.get_data_cached(url))
        result = []
        for m in data:
            if m['typ'] == 'get':
                xbmcplugin.setContent(int(sys.argv[1]), 'episodes')
                item = self._video_item(m)
            if m['typ'] == 'latest':
                xbmcplugin.setContent(int(sys.argv[1]), 'tvshows')
                item = self._dir_item(m)
                if m['poster'] != '':
                    item['img'] = m['poster']
            else:
                item = self._video_item(m)
                
            self._filter(result, item)
        return result
    
    @buggalo.buggalo_try_except({'method': 'scinema._dir_item'})
    def _dir_item(self, m):
        item = self.dir_item(title=m['name'], url=SERIES_BASE_URL + '/get/' + m['url'])
        for k in m.keys():
            if k != 'url':
                item[k] = m[k]
        year = m['release']
        item['plot'] = m['description']
        item['originaltitle'] = m['name_orig']
        item['sorttitle'] = m['name_seo']
        item['studio'] = m['studio']
        item['genre'] = m['genres']
        item['year'] = year[:4]
        
        art = {}
        if m['fanart'] != '':
            art['fanart'] = m['fanart']
        if 'banner' in m:
            art['banner'] = m['banner']
        item['art'] = art

        if int(year[:4]) > 0:
            item['title'] = m['name'] + ' (' + year[:4] + ')'
        else:
            item['title'] = m['name']
        return item
        
    @buggalo.buggalo_try_except({'method': 'scinema._video_item'})
    def _video_item(self, m):
        if '/json/series' in self.base_url:
            item = self.video_item(url=self.base_url + '/play/%s/%s/%s' % (m['id'], m['season'], m['episode']), img=m['poster'])
        else:
            item = self.video_item(url=self.base_url + '/play/' + m['id'], img=m['poster'])
        for k in m.keys():
            if k != 'url':
                item[k] = m[k]
        year = m['release']
        if m['rating'] > 0:
            item['rating'] = float(m['rating']) / 10
        
        if int(year[:4]) > 0:
            item['title'] = m['name'] + ' (' + year[:4] + ')'
        else:
            item['title'] = m['name']
        item['genre'] = m['genres']
        item['year'] = year[:4]
        item['cast'] = m['cast'].split(', ')
        item['director'] = m['director']
        if m['mpaa'] != '':
            item['mpaa'] = m['mpaa']
        item['plot'] = m['description']
        item['originaltitle'] = m['name_orig']
        item['sorttitle'] = m['name_seo']
        item['studio'] = m['studio']
        
        if m['imdb'] != '':
            item['code'] = 'tt' + m['imdb']
        art = {}
        if m['fanart'] != '':
            art['fanart'] = m['fanart']
        if 'banner' in m:
            art['banner'] = m['banner']
        item['art'] = art
        
        return item
    
    @buggalo.buggalo_try_except({'method': 'scinema.get_data_cached'})
    @cached(ttl=1)
    def get_data_cached(self, url):
        return util.request(url,{'X-UID':self.uid})

    @buggalo.buggalo_try_except({'method': 'scinema.list_by_letter'})
    def list_by_letter(self, url):
        result = []
        util.debug("Ideme na pismeno!")
        data = json.loads(self.get_data_cached(url))
        for m in data:
            util.debug(m)
            item = self._video_item(m)
            self._filter(result, item)
        util.debug(result)
        return result

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
        return itm
    
    @buggalo.buggalo_try_except({'method': 'scinema.resolve'})
    def resolve(self, item, captcha_cb=None, select_cb=None):
        util.debug("ITEM RESOLVE: " + str(item))
        data = json.loads(self.get_data_cached(item['url']))
        if len(data) < 1:
            raise ResolveException('Video is not available.')
        if len(data) == 1:
            return self._resolve(data[0])
        elif len(data) > 1 and select_cb:
            return self._resolve(select_cb(data))

buggalo.SUBMIT_URL = submiturl