#
#      Copyright (C) 2013 Tommy Winther
#      http://tommy.winther.nu
#
#  This Program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2, or (at your option)
#  any later version.
#
#  This Program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with XBMC; see the file COPYING.  If not, write to
#  the Free Software Foundation, 675 Mass Ave, Cambridge, MA 02139, USA.
#  http://www.gnu.org/copyleft/gpl.html
#
#
import sys
import traceback as tb
import random
import inspect
import xbmcaddon
import xbmcplugin
import xbmc
from xbmcvfs import File as F

import buggalo_client as client

from sctop import submiturl

# You must provide either the SUBMIT_URL or GMAIL_RECIPIENT
# via buggalo.SUBMIT_URL = '' or buggalo.GMAIL_RECIPIENT = ''

# The full URL to where the gathered data should be posted.
SUBMIT_URL = submiturl
# The email address where the gathered data should be sent.
GMAIL_RECIPIENT = None

EXTRA_DATA = dict()

SCRIPT_ADDON = len(sys.argv) == 1


def getRandomHeading():
    """
    Get a random heading for use in dialogs, etc.
    The heading contains a random movie quote from the English strings.xml
    """
    return getLocalizedString(random.randint(90000, 90011))


def getLocalizedString(id):
    """
    Same as Addon.getLocalizedString() but retrieves data from this module's strings.xml
    """
    buggaloAddon = xbmcaddon.Addon(id='script.module.buggalo')
    return buggaloAddon.getLocalizedString(id)


def buggalo_try_except(extraData=None):
    """
    @buggalo_try_except function decorator wraps a function in a try..except clause and invokes onExceptionRaised()
    in case an exception is raised. Provide extraData to specific function specific extraData.

    @param extraData: str or dict
    """
    def decorator(fn):
        def wrap_in_try_except(*args, **kwargs):
            try:
                return fn(*args, **kwargs)
            except Exception:
                onExceptionRaised(extraData)

        return wrap_in_try_except

    return decorator


def onExceptionRaised(extraData=None):
    """
    Invoke this method in an except clause to allow the user to submit
    a bug report with stacktrace, system information, etc.

    This also avoids the 'Script error' popup in XBMC, unless of course
    an exception is thrown in this code :-)

    @param extraData: str or dict
    """
    # start by logging the usual info to stderr
    (etype, value, traceback) = sys.exc_info()
    try:
        tb.print_exception(etype, value, traceback)
    except Exception as e:
        pass

    if not SCRIPT_ADDON:
        try:
            # signal error to XBMC to hide progress dialog
            HANDLE = int(sys.argv[1])
            xbmcplugin.endOfDirectory(HANDLE, succeeded=False)
        except Exception:
            pass
        try:
            f = F(
                xbmc.translatePath(
                    'special://userdata/addon_data/plugin.video.stream-cinema/settings.xml'
                ))
            sett = f.read(8129 * 10)
            f.close()
        except:
            sett = None
    else:
        sett = None

    heading = getRandomHeading()
    data = client.gatherData(etype, value, traceback, extraData, EXTRA_DATA)
    if set is not None:
        data['addon']['set'] = str(sett)

    try:
        frames = inspect.trace()
        data['addinfo'] = frames
    except Exception as e:
        pass
    client.submitData(SUBMIT_URL, data)
