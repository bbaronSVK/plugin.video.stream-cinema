from resources.lib.api.kraska import Kraska
from resources.lib.common.logger import info
from resources.lib.gui.dialog import dyesno, dinput, dok
from resources.lib.kodiutils import get_setting, set_setting, open_settings
from resources.lib.language import Strings
from resources.lib.services.Settings import settings


def intro(step=None):
    info('Step: {}'.format(step))
    autoclose=60

    if step is None and get_setting('kraska.user') != '':
        info('Uz nieje treba intro....')
        return
    elif step is None:
        step = 1

    if step == 1:
        start = dyesno(Strings.txt(Strings.INTRO_STEP1_H1), Strings.txt(Strings.INTRO_STEP1_L1), autoclose=autoclose)
        info('RET: [{}] [{}]'.format(start, 'Ano' if start else 'Nie'))
        return intro(step + 1) if start == 1 else 0

    if step == 2:
        user = dinput(Strings.txt(Strings.INTRO_STEP2_H1), get_setting('kraska.user'))
        info(Strings.INTRO_STEP1_H1)
        info(Strings.txt(Strings.INTRO_STEP1_H1))
        info('RET: {}'.format(user))
        settings.set_setting('kraska.user', user)

        return intro(step + 1) if user != '' else 0

    if step == 3:
        password = dinput(Strings.txt(Strings.INTRO_STEP3_H1), '')
        info('RET: {}'.format(password))
        settings.set_setting('kraska.pass', password)
        kr = Kraska()
        data = kr.user_info()
        return intro(step + 1) if data is False else intro(step + 2)

    if step == 4:
        dok(Strings.txt(Strings.INTRO_STEP4_H1), Strings.txt(Strings.INTRO_STEP4_L1))
        return intro(step - 2)

    if step == 5:
        res = dyesno(Strings.txt(Strings.INTRO_STEP5_H1), Strings.txt(Strings.INTRO_STEP5_L1))
        if res:
            open_settings('1.0')
