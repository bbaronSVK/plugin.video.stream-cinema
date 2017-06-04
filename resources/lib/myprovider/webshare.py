# -*- coding: UTF-8 -*-
#/*
# *      Copyright (C) 2013 Libor Zoubek
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
from crypto.md5crypt import md5crypt
import elementtree.ElementTree as ET
import hashlib
from provider import ResolveException
import urlparse
import util

class Webshare():

    def __init__(self,username=None,password=None,cache=None):
        self.username = username
        self.password = password
        self.base_url = 'http://webshare.cz/'
        self.token = ''
        
    def _url(self, url):
        """
        Transforms relative to absolute url based on ``base_url`` class property
        """
        if url.startswith('http'):
            return url
        return self.base_url + url.lstrip('./')

    def _create_request(self,url,base):
        args = dict(urlparse.parse_qsl(url))
        headers = {'X-Requested-With':'XMLHttpRequest','Accept':'text/xml; charset=UTF-8','Referer':self.base_url}
        req = base.copy()
        for key in req:
            if key in args:
                req[key] = args[key]
        return headers,req

    def login(self):
        if not self.username and not self.password:
            return True # fall back to free account
        elif self.username and self.password and len(self.username)>0 and len(self.password)>0:
            util.info('[SC] Login user=%s, pass=*****' % self.username)
            # get salt
            headers,req = self._create_request('',{'username_or_email':self.username})
            data = util.post(self._url('api/salt/'),req,headers=headers)
            xml = ET.fromstring(data)
            if not xml.find('status').text == 'OK':
                util.error('[SC] Server returned error status, response: %s' % data)
                return False
            salt = xml.find('salt').text
            # create hashes
            password = hashlib.sha1(md5crypt(self.password.encode('utf-8'), salt.encode('utf-8'))).hexdigest()
            digest = hashlib.md5(self.username + ':Webshare:' + self.password).hexdigest()
            # login
            headers,req = self._create_request('',{'username_or_email':self.username,'password':password,'digest':digest,'keep_logged_in':1})
            data = util.post(self._url('api/login/'),req,headers=headers)
            xml = ET.fromstring(data)
            if not xml.find('status').text == 'OK':
                util.error('[SC] Server returned error status, response: %s' % data)
                return False
            self.token = xml.find('token').text
            try:
                util.cache_cookies(None)
            except:
                pass
            util.info('[SC] Login successfull')
            return True
        return False

    def userData(self):
        if self.token:
            headers,req = self._create_request('/',{'wst':self.token})
            data = util.post(self._url('api/user_data/'), req, headers=headers)
            xml = ET.fromstring(data)
            if xml.find('vip').text == '1':
                return xml.find('vip_days').text
        return False

    def resolve(self,ident):
        headers,req = self._create_request('/',{'ident':ident,'wst':self.token})
        util.info(headers)
        util.info(req)
        data = util.post(self._url('api/file_link/'), req, headers=headers)
        xml = ET.fromstring(data)
        if not xml.find('status').text == 'OK':
            util.error('[SC] Server returned error status, response: %s' % data)
            raise ResolveException(xml.find('message').text)
        url = xml.find('link').text
        return url
