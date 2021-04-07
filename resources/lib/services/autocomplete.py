from json import dumps

import xbmcgui
import xbmcplugin

from resources.lib.api.sc import Sc
from resources.lib.common.logger import debug
from resources.lib.constants import SC
from resources.lib.kodiutils import get_info_label, jsonrpc, create_plugin_url
from resources.lib.params import params as args


class Autocomplete:
    def __init__(self, args):
        self.args = args
        id = self.args.get(SC.ITEM_ID, ['search'])
        debug('ID: {}'.format(id))
        if id[0] == 'search':
            self.search()
        else:
            self.type()

    def search(self):
        input = self.args.get('name', [''])[0]
        cont = get_info_label('Container.PluginName')
        debug('autocomplet input: {} / {}'.format(cont, input))
        if input == '':
            xbmcplugin.endOfDirectory(args.handle)
            return
        filter = self.args.get('f', [])[0]
        data = Sc.post('/FSug', data={'q': input, 'f': filter})
        debug('data: {}'.format(data))
        items = []
        for (count, result) in enumerate(data):
            debug('{} / {}'.format(count, result))
            listitem = xbmcgui.ListItem(result)
            param = {SC.ITEM_ACTION: 'autocomplet', SC.ITEM_ID: 'type', SC.ITEM_TITLE: result}
            url = create_plugin_url(param)
            listitem.setPath(url)
            listitem.setProperty('path', url)
            listitem.setProperty("index", str(count))
            listitem.setProperty("isPlayable", "false")
            items.append(listitem)
        xbmcplugin.addDirectoryItems(handle=args.handle,
                                     items=[(i.getProperty("path"), i, False) for i in items],
                                     totalItems=len(items))
        xbmcplugin.endOfDirectory(args.handle)

    def type(self):
        text = self.args.get('title', '')
        try:
            window = xbmcgui.Window(10103)
        except Exception:
            return None
        window.setFocusId(300)
        p = {"text": text, "done": False}
        debug('p: {}'.format(p))
        debug('json p: {}'.format(dumps(p)))
        jsonrpc(method="Input.SendText",
                params=p)
        xbmcplugin.endOfDirectory(args.handle)
