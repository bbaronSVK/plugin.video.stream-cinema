from time import time

import xbmc

from resources.lib.api.sc import Sc
from resources.lib.common.lists import SCKODIItem
from resources.lib.common.logger import debug
from resources.lib.common.storage import Storage
from resources.lib.constants import ADDON_ID
from resources.lib.gui import get_cond_visibility
from resources.lib.gui.dialog import dprogressgb
from resources.lib.gui.item import SCUpNext
from resources.lib.services.Monitor import monitor
from resources.lib.services.SCPlayer import player
from resources.lib.services.Settings import settings


class NextEp:

    def __init__(self):
        self.list = Storage('nextep')
        # dal som to sem natvrdo, aby sa oneskoril sync o 10 minut po starte
        last_run = settings.get_setting_as_int('system.next_ep.last_run')
        if last_run is None:
            self.last_run = time()
        else:
            self.last_run = last_run

    def run(self, force=False):
        now = time()
        if not player.isPlayback() and (force or self.last_run + (3600 * 3) < now):
            if self.update_items():
                self.last_run = now
                settings.set_setting('system.next_ep.last_run', '{}'.format(int(now)))

    def update_items(self):
        query = 'select item_key, item_value from storage where item_key like ? and item_value like ?'
        search = '{}-%'.format(SCKODIItem.ITEM_NAME)
        # debug('search: {}'.format(search))
        res = self.list._db.execute(query, search, '%"last_ep"%').fetchall()
        total = len(res)
        skip_list = self.get()
        debug('NEXTEP: {} z {} ({})'.format(len(skip_list), total, total - len(skip_list)))
        dialog = dprogressgb()
        dialog.create('Next Ep in progress')
        pos = 0
        for i in res:
            if monitor.abortRequested() or player.isPlayback():
                dialog.close()
                return False
            pos += 1
            _, item_id = i[0].split('-')
            if item_id in skip_list:
                debug('ITEM {} uz ma nextep, nepotrebujeme update'.format(item_id))
                continue
            item = SCKODIItem(item_id)
            last_ep = item.get_last_ep()
            debug('Next Ep in progress: {}%'.format(int(pos / total * 100)))
            dialog.update(int(pos / total * 100), message='{} - {}x{}'.format(item_id, last_ep[0], last_ep[1]))
            try:
                debug('last {}x{}'.format(last_ep[0], last_ep[1]))
                info = Sc.up_next(item_id, last_ep[0], last_ep[1])
                if 'error' in info or ('info' in info and info.get('info') is None):
                    debug('nemame data k next EP')
                    continue
                new = {
                    's': last_ep[0],
                    'e': last_ep[1],
                    't': int(time()),
                }
                cur = self.list.get(item_id)
                if cur is None or (cur and str(cur.get('e')) != str(new.get('e'))):
                    debug('nextep update {} -> {}'.format(item_id, last_ep))
                    self.list[item_id] = new
                else:
                    debug('nezmenene {} -> {}'.format(item_id, last_ep))
            except:
                debug('mazem serial zo zoznamu {}'.format(item_id))
                del(self.list[item_id])
                pass

        dialog.close()
        debug('LIST NEXT EP: {}'.format(self.list._data))
        return True

    def get(self):
        tmp = {}
        for k in self.list._data.items():
            if k[1]['t'] is not None:
                tmp.update({k[0]: k[1]})
            else:
                debug('ERR ITEM: {}'.format(k))

        debug('GET NEXT EP: {}'.format(tmp))
        ret = [k[0] for k in sorted(tmp.items(), key=lambda x: x[1]['t'], reverse=True)]
        return ret
