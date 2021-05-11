from __future__ import print_function, unicode_literals

import traceback

from resources.lib.api.kraska import Kraska
from resources.lib.common.android import AndroidTv
from resources.lib.common.logger import debug
from resources.lib.services import websocket
from resources.lib.services.next_episodes import NextEp
from resources.lib.trakt.Trakt import trakt
from resources.lib.constants import ADDON, ADDON_ID
from resources.lib.gui.dialog import dok, dtextviewer
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
    next_ep = None
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
        debug('START SERVICE....................................................................')
        last_changelog = get_setting('system.changelog')

        if last_changelog != ADDON.getAddonInfo('version'):
            debug('SYSTEM.CHANGELOG: {}'.format(ADDON.getAddonInfo('changelog')))
            set_setting('system.changelog', '{}'.format(ADDON.getAddonInfo('version')))
            dtextviewer('', ADDON.getAddonInfo('changelog'))

        if get_setting_as_bool('system.autoexec'):
            try:
                exec_build_in('ActivateWindow(videos,plugin://{})'.format(ADDON_ID))
            except:
                pass

        if get_setting('kraska.user'):
            kra = Kraska()
            kra.check_user()

        if get_setting_as_bool('system.ws.remote.enable'):
            ws = websocket.WS()
            ws.reconnect()

        self.next_ep = NextEp()

        while not monitor.abortRequested():
            try:
                self.periodical_check()
            except:
                debug('error: {}'.format(traceback.format_exc()))
                pass
            sleep(1000 * 1)

    def periodical_check(self):
        if monitor.can_check():
            try:
                player.periodical_check()
            except:
                debug('player err: {}'.format(traceback.format_exc()))
                pass

            try:
                monitor.periodical_check()
            except:
                debug('monitor err: {}'.format(traceback.format_exc()))
                pass

            try:
                if self.atv:
                    self.atv.run()
            except:
                debug('android tv err: {}'.format(traceback.format_exc()))
                pass

            try:
                trakt.check_trakt()
            except:
                debug('trakt err: {}'.format(traceback.format_exc()))
                pass

            try:
                self.next_ep.run()
            except:
                debug('nextep err: {}'.format(traceback.format_exc()))
                pass


service = Service()
