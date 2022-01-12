import xbmcvfs

from resources.lib.api.kraska import Kraska
from resources.lib.common.logger import info, debug
from resources.lib.constants import ADDON_ID
from resources.lib.gui.dialog import dyesno, dinput, dok
from resources.lib.kodiutils import get_setting, set_setting, open_settings, make_legal_filename, translate_path
from resources.lib.language import Strings
from resources.lib.services.Settings import settings


def intro(step=None, credentials_only=False):
    info('Step: {}'.format(step))
    auto_close = 60

    if step is None and get_setting('kraska.user') != '':
        info('Uz nieje treba intro....')
        return
    elif step is None:
        step = 1

    if step == 1:
        start = dyesno(Strings.txt(Strings.INTRO_STEP1_H1), Strings.txt(Strings.INTRO_STEP1_L1), autoclose=auto_close)
        info('RET: [{}] [{}]'.format(start, 'Ano' if start else 'Nie'))
        return intro(step + 1, credentials_only) if start == 1 else 0

    if step == 2:
        user = dinput(Strings.txt(Strings.INTRO_STEP2_H1), get_setting('kraska.user'))
        info(Strings.INTRO_STEP1_H1)
        info(Strings.txt(Strings.INTRO_STEP1_H1))
        info('RET: {}'.format(user))
        settings.set_setting('kraska.user', user)
        if user != settings.get_setting('kraska.user'):
            _remove_settings_file()
            debug('Zmazanie nastaveni')
            return 0

        return intro(step + 1, credentials_only) if user != '' else 0

    if step == 3:
        password = dinput(Strings.txt(Strings.INTRO_STEP3_H1), '')
        info('RET: {}'.format(password))
        settings.set_setting('kraska.pass', password)
        if password != settings.get_setting('kraska.pass'):
            debug('skusam znova zapisat heslo...')
            settings.set_setting('kraska.pass', password)
        kr = Kraska(p=password)
        data = kr.user_info()
        return intro(step + 1, credentials_only) if data is False else intro(step + 2)

    if step == 4:
        dok(Strings.txt(Strings.INTRO_STEP4_H1), Strings.txt(Strings.INTRO_STEP4_L1))
        return intro(step - 2, credentials_only)

    if step == 5 and credentials_only is False:
        res = dyesno(Strings.txt(Strings.INTRO_STEP5_H1), Strings.txt(Strings.INTRO_STEP5_L1))
        if res:
            open_settings('1.0')


def _remove_settings_file():
    try:
        fn = make_legal_filename(translate_path("special://profile/addon_data/{}/settings.xml".format(ADDON_ID)))
        debug('REMOVE SETTINGS FILE: {} -> {}'.format(fn, xbmcvfs.exists(fn)))
        if xbmcvfs.exists(fn):
            xbmcvfs.delete(fn)
    except:
        pass
