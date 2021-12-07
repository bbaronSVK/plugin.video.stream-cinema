import xbmcvfs

from resources.lib.common.logger import debug
from resources.lib.gui.dialog import dyesno, dok, dinput
from xbmcgui import INPUT_NUMERIC
import xbmc

from resources.lib.kodiutils import translate_path, get_system_platform, jsonrpc
from resources.lib.language import Strings


def set_kodi_cache_size():
    free_mem = xbmc.getInfoLabel('System.FreeMemory')
    free_mem = int(free_mem) / 1e6 if 'MB' not in free_mem else int(free_mem.replace('MB', ''))
    msg = Strings.txt(Strings.SETUP_VIDEO_CACHE_MSG1)
    user_input = dinput(msg.format(free_mem), '80', type=INPUT_NUMERIC)
    debug('user input: {}'.format(user_input))
    if user_input == '':
        return
    coefficient = int('{}'.format(user_input).replace('%', ''))
    coefficient = 80 if coefficient is None or 1 < coefficient > 80 else coefficient
    filename = translate_path('special://userdata/advancedsettings.xml')

    debug('cache size: {} * {}% / 3 = {}, '.format(free_mem, coefficient, int(free_mem / 3 * (coefficient/100))))
    if xbmcvfs.exists(filename):
        res = dyesno('WARNING', Strings.txt(Strings.SETUP_VIDEO_CACHE_MSG2))
        if not res:
            return False

    cache_size = int(min(500, int(free_mem / 3 * (coefficient/100))) * 1e6)
    debug('Nova cache {}'.format(cache_size))
    advanced_settings = '<advancedsettings>' \
                        '<cache><memorysize>{}</memorysize>' \
                        '<buffermode>1</buffermode>' \
                        '<readfactor>20</readfactor></cache>' \
                        '</advancedsettings>'.format(cache_size)
    debug('Nove advanced settings: {}'.format(advanced_settings))
    f = xbmcvfs.File(filename, 'w')
    f.write(advanced_settings)
    f.close()
    platform = get_system_platform()
    if platform in ['linux', 'windows']:
        res = dyesno('INFO', Strings.txt(Strings.SETUP_VIDEO_CACHE_MSG3))
        if res:
            jsonrpc(method="RestartApp")
    else:
        dok('INFO', Strings.txt(Strings.SETUP_VIDEO_CACHE_MSG4))
    pass


