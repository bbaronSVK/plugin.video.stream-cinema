from resources.lib.common.logger import debug
from resources.lib.constants import ADDON_ID
from resources.lib.kodiutils import get_setting
import xbmcaddon
import xbmc


class Settings(xbmc.Monitor):
    addon = None

    def __init__(self):
        self.refresh()
        pass

    def onSettingsChanged(self):
        self.refresh()

    def refresh(self):
        debug('settings refresh')
        self.refresh_addon()
        pass

    def refresh_addon(self):
        self.addon = xbmcaddon.Addon(ADDON_ID)

    def get_setting(self, key):
        return self.addon.getSetting(key)

    def set_setting(self, key, val):
        debug('set_settings {} {}'.format(key, val))
        return self.addon.setSetting(key, '{}'.format(val))

    def get_setting_as_bool(self, key):
        try:
            return self.addon.getSettingBool(key)
        except:
            return self.get_setting(key) == 'True' or self.get_setting(key) == 'true'

    def get_setting_as_int(self, key):
        try:
            return self.addon.getSettingInt(key)
        except:
            return int(self.addon.getSetting(key)) if self.addon.getSetting(key) else None


settings = Settings()
