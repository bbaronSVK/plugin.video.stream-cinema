from __future__ import print_function, unicode_literals

LOG = 2
APP = 'SC'

try:  # noqa C901
    import xbmc

    def debug(text):
        xbmc.log('[{}] {}'.format(APP, text), xbmc.LOGDEBUG)

    def info(text):
        xbmc.log('[{}] {}'.format(APP, text), xbmc.LOGINFO)

    def warning(text):
        xbmc.log('[{}] {}'.format(APP, text), xbmc.LOGWARNING)

    def error(text):
        xbmc.log('[{}] {}'.format(APP, text), xbmc.LOGERROR)
except Exception as e:
    def debug(text):
        if LOG > 1:
            print('[DEBUG] ' + str([text]))

    def info(text):
        if LOG > 0:
            print('[INFO] ' + str([text]))

    def warning(text):
        print('[WARNING] ' + str([text]))

    def error(text):
        print('[ERROR] ' + str([text]))