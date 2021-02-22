from xbmc import Monitor as KMonitor
from resources.lib.common.logger import debug
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
        debug('onSettingsChanged')
        # self.settings.refresh()
        pass

    def onScreensaverActivated(self):
        debug('onScreensaverActivated')
        self.is_screensaver = True
        pass

    def onScreensaverDeactivated(self):
        debug('onScreensaverDeactivated')
        self.is_screensaver = False
        pass

    def onDPMSActivated(self):
        debug('onDPMSActivated')
        self.is_DPMS = True
        pass

    def onDPMSDeactivated(self):
        debug('onDPMSDeactivated')
        self.is_DPMS = False
        pass

    def onScanStarted(self, library):
        debug('onScanStarted {}'.format(library))
        self.is_scanning = True
        pass

    def onScanFinished(self, library):
        debug('onScanFinished {}'.format(library))
        self.is_scanning = False
        pass

    def onCleanStarted(self, library):
        debug('onCleanStarted {}'.format(library))
        self.is_cleaning = True
        pass

    def onCleanFinished(self, library):
        debug('onCleanFinished {}'.format(library))
        self.is_cleaning = False
        pass

    def onNotification(self, sender, method, data):
        debug('onNotification {} {} {}'.format(sender, method, data))
        if sender == 'xbmc' and method == 'Player.OnAVStart':
            debug('monitor Player.OnAVChange, set item to: {}'.format(loads(data).get('item')))
            player.set_item(loads(data).get('item'))
        if sender == 'xbmc' and method == 'System.OnSleep':
            self.is_DPMS = True
        if sender == 'xbmc' and method == 'System.OnWake':
            self.is_DPMS = False

    def periodical_check(self):
        pass

    def can_check(self):
        return not self.is_screensaver and not self.is_DPMS


monitor = Monitor()
