# -*- coding: utf-8 -*-
import time
import traceback
import xbmc

try:
    xbmc._set_log_level(1)
except:
    pass


from resources.lib.streamcinema import Scinema
from resources.lib.common.logger import info

try:
    start = time.time()
    Scinema().run()
    end = time.time()
    info('{0} took {1:.2f}ms'.format('ALL', (end - start) * 1000))
except:

    info('-----------------------------------------------------------------')
    info('main error [{}]'.format(str(traceback.format_exc())))
    info('-----------------------------------------------------------------')
    pass
