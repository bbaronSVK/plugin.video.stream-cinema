from resources.lib.gui.dialog import dok
from resources.lib.kodiutils import sleep, set_setting, get_uuid, get_setting, get_system_debug, set_system_debug
from resources.lib.language import Strings
from resources.lib.services.Monitor import monitor
from resources.lib.services.SCPlayer import player
# from resources.lib.trakt.Trakt import trakt
from resources.lib.constants import ADDON
from resources.lib.api.kraska import Kraska


def periodical_check():
    if monitor.can_check():
        player.periodical_check()
        monitor.periodical_check()
        # trakt.check_trakt()
        # debug("settings {}/{}".format(settings.get_setting('stream.lang1'), settings.get_setting('stream.lang2')))


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

    def __init__(self):
        set_setting('system.ver', ADDON.getAddonInfo('version'))
        set_setting('system.uuid', get_uuid())
        if get_setting('kraska.user'):
            kra = Kraska()
            kra.check_user()

    def run(self):
        while not monitor.abortRequested():
            periodical_check()
            sleep(1000 * 1)


service = Service()
