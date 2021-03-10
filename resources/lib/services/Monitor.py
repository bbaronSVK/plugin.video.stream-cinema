from xbmc import Monitor as KMonitor
from resources.lib.common.logger import debug
from resources.lib.constants import ADDON_ID
from resources.lib.kodiutils import encode, decode, exec_build_in, create_plugin_url
from resources.lib.services.Settings import settings
from resources.lib.gui import home_win
from resources.lib.services.SCPlayer import player

from json import loads


class Monitor(KMonitor):
    def __init__(self):
        self.win = home_win
        self.settings = settings
        self.is_screensaver = False
        self.is_DPMS = False
        self.is_scanning = False
        self.is_cleaning = False
        pass

    def onSettingsChanged(self):
        debug('monitor onSettingsChanged')
        # self.settings.refresh()
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

    def onNotification(self, sender, method, data):
        debug('monitor onNotification {} {} {}'.format(decode(sender), decode(method), decode(data)))
        if sender == 'xbmc' and method == 'Player.OnAVStart':
            debug('monitor Player.OnAVChange, set item to: {}'.format(loads(data).get('item')))
            player.set_item(loads(data).get('item'))
        if sender == 'xbmc' and method == 'System.OnSleep':
            self.is_DPMS = True
        if sender == 'xbmc' and method == 'System.OnWake':
            self.is_DPMS = False
        if sender == 'upnextprovider.SIGNAL' and method == 'Other.{}_play_action'.format(ADDON_ID):
            from base64 import b64decode
            exec_build_in('PlayMedia({})'.format(create_plugin_url(loads(b64decode(data)))))
            pass

    def periodical_check(self):
        pass

    def can_check(self):
        return not self.is_screensaver and not self.is_DPMS


monitor = Monitor()
