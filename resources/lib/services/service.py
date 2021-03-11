from __future__ import print_function, unicode_literals

from resources.lib.api.kraska import Kraska
from resources.lib.common.android import AndroidTv
# from resources.lib.trakt.Trakt import trakt
from resources.lib.constants import ADDON, ADDON_ID
from resources.lib.gui.dialog import dok
from resources.lib.kodiutils import sleep, set_setting, get_uuid, get_setting, get_system_debug, set_system_debug, \
    exec_build_in, get_setting_as_bool
from resources.lib.language import Strings
from resources.lib.services.Monitor import monitor
from resources.lib.services.SCPlayer import player


def check_set_debug(toggle=False):
    cur_system = get_system_debug()
    if toggle:
        cur_system = not cur_system
        set_system_debug(cur_system)
        if cur_system:
            dok(Strings.txt(Strings.SYSTEM_H1), Strings.txt(Strings.SYSTEM_DEBUG_ENABLED))
        else:
            dok(Strings.txt(Strings.SYSTEM_H1), Strings.txt(Strings.SYSTEM_DEBUG_DISABLED))


class Service:
    monitor = None
    player = None
    trakt = None
    atv = None

    def __init__(self):
        set_setting('system.ver', ADDON.getAddonInfo('version'))
        get_uuid()
        if get_setting('androidtv.path'):
            self.atv = AndroidTv()

    def run(self):

        if get_setting_as_bool('system.autoexec'):
            try:
                exec_build_in('ActivateWindow(videos,plugin://{})'.format(ADDON_ID))
            except:
                pass

        if get_setting('kraska.user'):
            kra = Kraska()
            kra.check_user()

        while not monitor.abortRequested():
            self.periodical_check()
            sleep(1000 * 1)

    def periodical_check(self):
        if monitor.can_check():
            player.periodical_check()
            monitor.periodical_check()
            if self.atv:
                self.atv.run()
            # trakt.check_trakt()
            # debug("settings {}/{}".format(settings.get_setting('stream.lang1'), settings.get_setting('stream.lang2')))

service = Service()
