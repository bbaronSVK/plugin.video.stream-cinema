import traceback

from xbmc import Monitor as KMonitor
from resources.lib.common.logger import debug
from resources.lib.common.storage import KodiViewModeDb
from resources.lib.constants import ADDON_ID
from resources.lib.kodiutils import encode, decode, exec_build_in, create_plugin_url, container_refresh
from resources.lib.services.Settings import settings
from resources.lib.gui import home_win
from resources.lib.services.SCPlayer import player

from json import loads


class Monitor(KMonitor):
    SORT_ASC = 1
    SORT_DESC = 2

    SORT_METHOD_NONE = 0
    SORT_METHOD_RATING = 17
    SORT_METHOD_MPAA = 31
    SORT_METHOD_TITLE = 29
    SORT_METHOD_YEAR = 16
    SORT_METHOD_DATE_ADDED = 40

    def __init__(self):
        self.win = home_win
        self.settings = settings
        self.is_screensaver = False
        self.is_DPMS = False
        self.is_scanning = False
        self.is_cleaning = False
        self.sort_method = self.SORT_METHOD_NONE
        self.sort_order = self.SORT_ASC
        self.last_url = None
        self.filter = {}
        self.callback = {
            'Player.OnAVStart': self.PlayerOnAVStart,
            'System.OnSleep': self.onSleep,
            'System.OnWake': self.onWake,
        }
        pass

    def onSettingsChanged(self):
        debug('monitor onSettingsChanged')
        self.settings.refresh()
        pass

    def onScreensaverActivated(self):
        debug('monitor onScreensaverActivated')
        self.is_screensaver = True
        pass

    def onScreensaverDeactivated(self):
        debug('monitor onScreensaverDeactivated')
        self.is_screensaver = False
        pass

    def onDPMSActivated(self):
        debug('monitor onDPMSActivated')
        self.is_DPMS = True
        pass

    def onDPMSDeactivated(self):
        debug('monitor onDPMSDeactivated')
        self.is_DPMS = False
        pass

    def onScanStarted(self, library):
        debug('monitor onScanStarted {}'.format(library))
        self.is_scanning = True
        pass

    def onScanFinished(self, library):
        debug('monitor onScanFinished {}'.format(library))
        self.is_scanning = False
        pass

    def onCleanStarted(self, library):
        debug('monitor onCleanStarted {}'.format(library))
        self.is_cleaning = True
        pass

    def onCleanFinished(self, library):
        debug('monitor onCleanFinished {}'.format(library))
        self.is_cleaning = False
        pass

    def onSleep(self, data):
        self.is_DPMS = True

    def onWake(self, data):
        self.is_DPMS = False

    def PlayerOnAVStart(self, data):
        debug('Monitor PlayerOnAVStart')
        # player.set_item(loads(data).get('item'))

    def onNotification(self, sender, method, data):
        debug('monitor onNotification {} {} {}'.format(decode(sender), decode(method), decode(data)))
        if method in self.callback:
            debug('callback for {}'.format(method))
            self.callback[method](data)
        # if sender == 'xbmc' and method == 'Player.OnAVStart':
            # debug('monitor Player.OnAVChange, set item to: {}'.format(loads(data).get('item')))
            # player.set_item(loads(data).get('item'))
        if sender == 'xbmc' and method == 'System.OnSleep':
            self.is_DPMS = True
        if sender == 'xbmc' and method == 'System.OnWake':
            self.is_DPMS = False
        if sender == 'upnextprovider.SIGNAL' and method == 'Other.{}_play_action'.format(ADDON_ID):
            from base64 import b64decode
            exec_build_in('PlayMedia({})'.format(create_plugin_url(loads(b64decode(data)))))
            pass
        # if sender == ADDON_ID and method == 'Other.List.Sort':
        #     from base64 import b64decode
        #     info = loads(b64decode(data))
        #     debug('new List.Sort: method: {} order {} url: {}'.format(info['m'], info['o'], info['u']))
        #     self.sort_method = info['m']
        #     self.sort_order = info['o']
        #     self.last_url = info['u']
        #     self.filter = info['f']

    def periodical_check(self):
        return
        try:
            kv = KodiViewModeDb()
            sort = kv.get_sort(self.last_url)
            if sort is None:
                sort = (0, 1)
        except:
            debug('ERR: {}'.format(traceback.format_exc()))
            sort = (0, 1)
        # debug("{}/{} => {}/{} | {}".format(sort[0], sort[1], self.sort_method, self.sort_order, self.last_url))
        if self.last_url and (sort[0] != self.sort_method or sort[1] != self.sort_order):
            debug('============ refresh {} ============'.format(self.last_url))
            # container_refresh()

    def can_check(self):
        return not self.is_screensaver and not self.is_DPMS and not player.isPlayback()


monitor = Monitor()
