import xbmcgui
import xbmc

from resources.lib.system import SYSTEM_VERSION

cur_win = xbmcgui.Window(xbmcgui.getCurrentWindowId())
home_win = xbmcgui.Window(10000)  # komunikacne okno


def get_cond_visibility(text):
    if SYSTEM_VERSION < 17:
        text = text.replace("Integer.IsGreater", "IntegerGreaterThan")
        text = text.replace("String.Contains", "SubString")
        text = text.replace("String.IsEqual", "StringCompare")
    return xbmc.getCondVisibility(text)
