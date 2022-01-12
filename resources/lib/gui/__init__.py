import xbmcgui
import xbmc
import re

from resources.lib.common.lists import List
from resources.lib.common.logger import debug
from resources.lib.common.storage import Storage
from resources.lib.kodiutils import get_setting
from resources.lib.system import SYSTEM_VERSION

cur_win = xbmcgui.Window(xbmcgui.getCurrentWindowId())
home_win = xbmcgui.Window(10000)  # komunikacne okno


def get_cond_visibility(text):
    # debug('get_cond_visibility: {}'.format(text))
    if 'sc://' in text:
        return translate_cond_visibility(text)

    if SYSTEM_VERSION < 17:
        text = text.replace("Integer.IsGreater", "IntegerGreaterThan")
        text = text.replace("String.Contains", "SubString")
        text = text.replace("String.IsEqual", "StringCompare")
    # debug('final: {} / {}'.format(text, xbmc.getCondVisibility(text)))
    return xbmc.getCondVisibility(text)


def translate_cond_visibility(text):
    m = re.search('sc://(?P<typ>[^\(]+)\((?P<param1>[^\s,\)]+),(?P<param2>[^\s,\)]+)\)', text)
    debug('najdene: {} / {} ({}, {})'.format(m.group(0), m.group('typ'), m.group('param1'), m.group('param2')))
    ret = text
    if m.group('typ') == 'config':
        debug('{} vs {}'.format(get_setting(m.group('param1')), m.group('param2')))
        p1 = m.group('param1')
        p2 = m.group('param2')
        val = get_setting(p1)
        if p2 == 'notempty':
            ret = val is not None and val != ''
        elif p2 == 'empty':
            ret = val is None or val == ''
        else:
            ret = '{}'.format(val) == '{}'.format(p2)
    elif m.group('typ') == 'history':
        from resources.lib.gui.item import get_history_item_name
        name = get_history_item_name(m.group('param1'))
        st = List(name)
        ret = len(st.get()) > int(m.group('param2'))
    elif m.group('typ') == 'listlen':
        st = List(m.group('param1'))
        p1 = len(st.get())
        p2 = int(m.group('param2'))
        debug('p1 {} p2 {}'.format(p1, p2))
        return p1 > p2
    elif m.group('typ') == 'storagelen':
        st = Storage(m.group('param1'))
        p1 = len(st._data)
        p2 = int(m.group('param2'))
        debug('p1 {} p2 {}'.format(p1, p2))
        return p1 > p2

    debug('{} -> {}'.format(text, ret))
    return ret
