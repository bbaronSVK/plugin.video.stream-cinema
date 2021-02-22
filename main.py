# -*- coding: utf-8 -*-
import traceback
import xbmc

try:
    xbmc._set_log_level(1)
except:
    pass


from resources.lib.streamcinema import scinema
from resources.lib.common.logger import info

try:
    scinema().run()
except:

    info('-----------------------------------------------------------------')
    info('main error [{}]'.format(str(traceback.format_exc())))
    info('-----------------------------------------------------------------')
    pass
