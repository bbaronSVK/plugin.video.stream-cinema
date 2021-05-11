from time import time

from resources.lib.api.sc import Sc
from resources.lib.common.lists import SCKODIItem
from resources.lib.common.logger import debug
from resources.lib.common.storage import Storage
from resources.lib.constants import ADDON_ID
from resources.lib.gui import get_cond_visibility
from resources.lib.gui.dialog import dprogressgb
from resources.lib.gui.item import SCUpNext
from resources.lib.services.Monitor import monitor
from resources.lib.services.Settings import settings


class NextEp:

    def __init__(self):
        self.list = Storage('nextep')
        self.last_run = settings.get_setting_as_int('system.next_ep.last_run')
        if self.last_run is None:
            self.last_run = 0

    def run(self, force=False):
        now = time()
        if force or self.last_run + 3600 < now:
            self.update_items()
            self.last_run = now
            settings.set_setting('system.next_ep.last_run', '{}'.format(int(now)))

    def update_items(self):
        query = 'select item_key, item_value from storage where item_key like ? and item_value like ?'
        search = '{}-%'.format(SCKODIItem.ITEM_NAME)
        debug('search: {}'.format(search))
        res = self.list._db.execute(query, search, '%"last_ep"%').fetchall()
        total = len(res)
        dialog = dprogressgb()
        dialog.create('sync in progress')
        pos = 0
        for i in res:
            if monitor.abortRequested() or get_cond_visibility('!System.AddonIsEnabled({})'.format(ADDON_ID)):
                return
            pos += 1
            _, item_id = i[0].split('-')
            item = SCKODIItem(item_id)
            last_ep = item.get_last_ep()
            debug('sync in progress: {}%'.format(int(pos / total * 100)))
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

    def get(self):
        tmp = {}
        for k in self.list._data.items():
            if k[1]['t'] is not None:
                tmp.update({k[0]: k[1]})
            else:
                debug('ERR ITEM: {}'.format(k))

        debug('GET NEXT EP: {}'.format(tmp))
        ret = [k[0] for k in sorted(tmp.items(), key=lambda x: x[1]['t'], reverse=True)]
        debug('zoznam: {}'.format(len(ret)))
        return ret
