# -*- coding: UTF-8 -*-
# /*
#  *      Copyright (C) 2013 bbaron
#  *
#  *
#  *  This Program is free software; you can redistribute it and/or modify
#  *  it under the terms of the GNU General Public License as published by
#  *  the Free Software Foundation; either version 2, or (at your option)
#  *  any later version.
#  *
#  *  This Program is distributed in the hope that it will be useful,
#  *  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  *  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#  *  GNU General Public License for more details.
#  *
#  *  You should have received a copy of the GNU General Public License
#  *  along with this program; see the file COPYING.  If not, write to
#  *  the Free Software Foundation, 675 Mass Ave, Cambridge, MA 02139, USA.
#  *  http://www.gnu.org/copyleft/gpl.html
#  *
#  */

import xbmcaddon, xbmc, uuid
import util
from resources.lib.scinema import StreamCinemaContentProvider
from resources.lib.scutils import KODISCLib
from resources.lib.top import __scriptid__, __scriptname__,__addon__

#__scriptid__ = 'plugin.video.stream-cinema'
#__scriptname__ = 'stream-cinema.online'
__language__ = __addon__.getLocalizedString
__set__ = __addon__.getSetting

settings = {'quality': __set__('quality'), 'downloads': xbmc.translatePath(__set__('downloads'))}
uid = __set__('uid')
if uid == '':
    uid = str(uuid.uuid4())
    __addon__.setSetting('uid', uid)

params = util.params()
util.info('[sc] PARAMS: ' + str(params))
KODISCLib(StreamCinemaContentProvider(username=__set__('wsuser'),password=__set__('wspass'),uid=uid), settings, __addon__).run(params)
