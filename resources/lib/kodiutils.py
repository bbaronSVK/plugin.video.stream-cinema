from __future__ import print_function, unicode_literals

import json
import math
import os
import sys
import time
import traceback

try:
    from urllib.parse import urlparse, urlencode, parse_qs
except ImportError:
    from urlparse import urlparse, parse_qs
    from urllib import urlencode

import xbmc
import xbmcaddon
import xbmcvfs
from base64 import b64encode

from resources.lib.constants import ADDON_ID, PY2, SC
from resources.lib.common.logger import debug

addon = xbmcaddon.Addon(id=ADDON_ID)


def encode(s, encoding='utf-8', errors='strict'):
    if PY2 and isinstance(s, unicode):
        s = s.encode(encoding, errors)
    return s


def decode(s, encoding='utf-8', errors='strict'):
    if PY2 and isinstance(s, str):
        s = s.decode(encoding, errors)
    return s


def translate_path(path):
    try:
        return xbmcvfs.translatePath(path)
    except:
        return xbmc.translatePath(path)


def get_setting(key):
    return addon.getSetting(key)


def set_setting(key, val):
    debug('set_settings {} {}'.format(key, val))
    return addon.setSetting(key, '{}'.format(val))


def set_setting_as_bool(key, val):
    set_setting(key, val is True or val == 'true' or val == 'True')


def get_setting_as_bool(key):
    try:
        return addon.getSettingBool(key)
    except:
        return get_setting(key) == 'True' or get_setting(key) == 'true'


def get_setting_as_int(key):
    try:
        return addon.getSettingInt(key)
    except:
        return int(addon.getSetting(key)) if addon.getSetting(key) else None


def get_system_debug():
    return jsonrpc(method='Settings.GetSettingValue',
                   params=dict(setting="debug.showloginfo")).get('result', {}).get('value', False)


def set_system_debug(new_val):
    return jsonrpc(method='Settings.SetSettingValue', params=dict(setting="debug.showloginfo", value=new_val))


def get_app_name():
    try:
        data = jsonrpc(method='Application.GetProperties', params=dict(properties=["name"]))
        if "result" in data and "name" in data["result"]:
            return data["result"]["name"]
    except:
        debug('ERR app name: {}'.format(traceback.format_exc()))
        pass
    return "EKodi"


def get_info_label(str):
    return xbmc.getInfoLabel(str)


def get_kodi_version():
    return get_info_label('System.BuildVersion')


def get_screen_width():
    return get_info_label('System.ScreenWidth')


def get_screen_height():
    return get_info_label('System.ScreenHeight')


def get_os_version():
    return get_info_label('System.OSVersionInfo')


def sleep(sleep_time):
    mon = xbmc.Monitor()
    while not mon.abortRequested() and sleep_time > 0:
        sleep_time -= 100
        xbmc.sleep(99)


def get_il():
    '''
    toto je len pre debug, aby som vedel co ktory parameter vrati
    '''
    il = ["System.AlarmPos", "System.BatteryLevel", "System.BuildDate", "System.BuildVersion",
          "System.BuildVersionCode", "System.BuildVersionGit", "System.CpuFrequency",
          "System.CPUTemperature", "System.CpuUsage", "System.CurrentControl", "System.CurrentControlID",
          "System.CurrentWindow", "System.Date", "System.DVDLabel", "System.FanSpeed",
          "System.FPS", "System.FreeMemory", "System.FreeSpace", "System.FreeSpacePercent", "System.FriendlyName",
          "System.GPUTemperature", "System.HddTemperature", "System.InternetState",
          "System.Language", "System.Memory(free)", "System.OSVersionInfo", "System.ProfileAutoLogin",
          "System.ProfileCount", "System.ProfileName", "System.Progressbar", "System.ScreenHeight", "System.ScreenMode",
          "System.ScreenResolution", "System.ScreenWidth", "System.StartupWindow", "System.StereoscopicMode",
          "System.TemperatureUnits", "System.Time", "System.TotalSpace", "System.TotalUptime",
          "System.Uptime", "System.UsedSpace", "System.UsedSpacePercent", "System.VideoEncoderInfo"]
    for f in il:
        debug("[{}]: [{}]".format(f, xbmc.getInfoLabel(f)))


def get_system_platform():
    platform = "unknown"
    if xbmc.getCondVisibility('system.platform.linux') and not xbmc.getCondVisibility('system.platform.android'):
        platform = "linux"
    elif xbmc.getCondVisibility('system.platform.linux') and xbmc.getCondVisibility('system.platform.android'):
        platform = "android"
    elif xbmc.getCondVisibility('system.platform.uwp'):
        platform = "uwp"
    elif xbmc.getCondVisibility('system.platform.windows'):
        platform = "windows"
    elif xbmc.getCondVisibility('system.platform.osx'):
        platform = "osx"
    elif xbmc.getCondVisibility('system.platform.ios'):
        platform = "ios"
    return platform


__CRYPT_KEY__ = None


def get_uuid():
    # pylint: disable=global-statement
    global __CRYPT_KEY__
    if not __CRYPT_KEY__:
        __CRYPT_KEY__ = _get_system_uuid()
    return __CRYPT_KEY__


def _get_system_uuid():
    uuid_value = get_setting('system.uuid')
    if uuid_value and "'" not in uuid_value:
        debug('UUID from settings: {}'.format(uuid_value))
        return uuid_value
    else:
        uuid_value = ''

    system = get_system_platform()
    if system in ['windows', 'uwp']:
        uuid_value = _get_windows_uuid()
        debug('Windows UUID Found')
    # elif system == 'android':
    #     uuid_value = _get_android_uuid()
    #     debug('Android UUID Found')
    elif system == 'linux':
        uuid_value = _get_linux_uuid()
        debug('Linux UUID Found')
    elif system == 'osx':
        uuid_value = _get_macos_uuid()
        debug('OSX, IOS UUID Found {}'.format(uuid_value))
    if not uuid_value or "'" in uuid_value:
        debug('It is not possible to get a system UUID creating a new UUID')
        if not uuid_value:
            debug('get fake uuid')
            uuid_value = _get_fake_uuid()
            set_setting('system.uuid', uuid_value)
    if sys.version_info > (3, 0):
        return str(uuid_value)
    return uuid_value.encode('ascii', 'replace')


def _get_windows_uuid():
    # pylint: disable=broad-except
    # pylint: disable=import-error  # Under linux pylint rightly complains
    uuid_value = None
    try:
        import winreg
        registry = winreg.HKEY_LOCAL_MACHINE
        address = 'SOFTWARE\\Microsoft\\Cryptography'
        keyargs = winreg.KEY_READ | winreg.KEY_WOW64_64KEY
        key = winreg.OpenKey(registry, address, 0, keyargs)
        value = winreg.QueryValueEx(key, 'MachineGuid')
        winreg.CloseKey(key)
        uuid_value = value[0].strip()
    except Exception:
        pass
    if not uuid_value:
        try:
            import subprocess
            output = subprocess.check_output(['vol', 'c:'])
            output = output.split()
            uuid_value = output[len(output) - 1:].strip()
        except Exception:
            pass
    return uuid_value


def _get_linux_uuid():
    # pylint: disable=broad-except
    import subprocess
    uuid_value = None
    try:
        uuid_value = subprocess.check_output(['cat', '/var/lib/dbus/machine-id']).strip().decode('utf-8')
    except Exception as exc:
        import traceback
    if not uuid_value:
        try:
            # Fedora linux
            uuid_value = subprocess.check_output(['cat', '/etc/machine-id']).strip().decode('utf-8')
        except Exception as exc:
            pass
    return uuid_value


def _get_android_uuid():
    # pylint: disable=broad-except
    import subprocess
    import re
    values = 'xxx'
    try:
        # Due to the new android security we cannot get any type of serials
        sys_prop = ['ro.product.board', 'ro.product.brand', 'ro.product.device', 'ro.product.locale',
                    'ro.product.manufacturer',
                    'ro.product.model', 'ro.product.platform',
                    'persist.sys.timezone', 'persist.sys.locale', 'net.hostname']
        # Warning net.hostname property starting from android 10 is deprecated return empty
        proc = subprocess.Popen(['/system/bin/getprop'], stdout=subprocess.PIPE)
        output_data = proc.communicate()[0].decode('utf-8')
        list_values = output_data.splitlines()
        for value in list_values:
            value_splitted = re.sub(r'\[|\]|\s', '', value).split(':')
            if value_splitted[0] in sys_prop:
                values += value_splitted[1]
    except Exception:
        pass
    return values.strip().encode('utf-8')


def _get_macos_uuid():
    # pylint: disable=broad-except
    import subprocess
    sp_dict_values = None
    try:
        proc = subprocess.Popen(
            ['/usr/sbin/system_profiler', 'SPHardwareDataType', '-detaillevel', 'full', '-xml'],
            stdout=subprocess.PIPE)
        output_data = proc.communicate()[0].decode('utf-8')
        if output_data:
            sp_dict_values = _parse_osx_xml_plist_data(output_data)
    except Exception as exc:
        debug('error on popen {}'.format(exc))
        pass
    if sp_dict_values:
        if 'UUID' in list(sp_dict_values.keys()):
            return sp_dict_values['UUID'].strip()
        if 'serialnumber' in list(sp_dict_values.keys()):
            return sp_dict_values['serialnumber'].strip()
    return None


def _parse_osx_xml_plist_data(data):
    import plistlib
    import re
    dict_values = {}
    try:
        xml_data = plistlib.loads(data.encode())
    except:
        xml_data = plistlib.readPlistFromString(data)
    items_dict = xml_data[0]['_items'][0]
    r = re.compile(r'.*UUID.*')  # Find to example "platform_UUID" key
    uuid_keys = list(filter(r.match, list(items_dict.keys())))
    if uuid_keys:
        dict_values['UUID'] = items_dict[uuid_keys[0]]
    if not uuid_keys:
        r = re.compile(r'.*serial.*number.*')  # Find to example "serial_number" key
        serialnumber_keys = list(filter(r.match, list(items_dict.keys())))
        if serialnumber_keys:
            dict_values['serialnumber'] = items_dict[serialnumber_keys[0]]
    return dict_values


def _get_fake_uuid():
    import uuid
    return str(uuid.uuid4())


def params(url):
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    for p in qs.keys():
        try:
            qs[p] = qs[p][0].decode('hex') if PY2 else bytes.fromhex(qs[p][0]).decode('utf-8')
        except:
            pass

    return qs


def exec_build_in(cmd):
    cmd = cmd.replace('__self__', ADDON_ID)
    debug('exec {}'.format(cmd))
    xbmc.executebuiltin(cmd)


def container_refresh():
    debug('container refresh')
    exec_build_in('Container.Refresh')


def container_update(url, replace=False):
    if replace:
        debug('containter replace {}'.format(url))
        exec_build_in('Container.Update({},replace)'.format(url))
    else:
        debug('containter update {}'.format(url))
        exec_build_in('Container.Update({})'.format(url))


def run_plugin(url):
    debug('run plugin {}'.format(url))
    exec_build_in(SC.RUN_PLUGIN.format(url))


def get_skin_name():
    return xbmc.getSkinDir()


def hexlify(value):
    if PY2:
        value = value.encode('utf-8').encode('hex')
    else:
        try:
            value = value.encode('utf-8').hex()
        except:
            import binascii
            value = binascii.hexlify(value)
    return value


def create_plugin_url(param):
    converted = {}

    for key in param.keys():
        # Ignore unknown params
        if key not in [
            "dtitle", "url", "action", "list", "cmd", "down", "play", "user",
            "force", "search-list", "search", "csearch", "search-remove",
            "search-edit", "tl", "id", "subtype", "title", "name", "imdb",
            "tvdb", "csfd", "trakt", "content", "tu", "page", "list", "selectStream"
        ]:
            continue

        value = '{}'.format(decode(param[key]))

        # Ignore empty
        if not value:
            continue

        converted[key] = hexlify(value)
        # debug("K: {} | V: {} / {}".format(key, value, converted[key]))

    # Keep URLs stable and predictable
    sorted_values = sorted(converted.items(), key=lambda val: val[0])

    return 'plugin://{0}/?{1}'.format(ADDON_ID, urlencode(sorted_values))


def make_table(matrix):
    matrix_length = len(matrix)
    if matrix_length == 0:
        return matrix
    for i in range(len(matrix[0])):
        longest = len(matrix[0][i])
        for r in range(matrix_length):
            length = len(matrix[r][i])
            if length > longest:
                longest = length

        for j, strings in enumerate(matrix):
            string = strings[i]
            length = len(string)
            diff = longest - length
            spaces = "" if length > 0 else ' ' * longest
            for r in range(diff):
                spaces += '  ' if length > 0 else ' '

            matrix[j][i] = spaces + string
    return matrix


def upnext_signal(sender, next_info):
    j = json.dumps(next_info).encode()
    data = [b64encode(j).decode()]
    notify(sender=sender + '.SIGNAL', message='upnext_data', data=data)


def notify(sender, message, data):
    debug('notify: method={}, sender={}, message={}, data={}'.format('JSONRPC.NotifyAll',
                                                                     sender, message, data))
    result = jsonrpc(method='JSONRPC.NotifyAll', params=dict(
        sender=sender,
        message=message,
        data=data,
    ))
    if result.get('result') != 'OK':
        debug('send notification: {}'.format(result.get('error').get('message')))
        return False
    return True


def jsonrpc(**kwargs):
    from json import dumps, loads
    if kwargs.get('id') is None:
        kwargs.update(id=0)
    if kwargs.get('jsonrpc') is None:
        kwargs.update(jsonrpc='2.0')
    return loads(xbmc.executeJSONRPC(dumps(kwargs)))


def convert_bitrate(mbit, with_text=True):
    if mbit == 0 or mbit is None:
        return 0
    p = math.pow(1000, 2)
    s = round(mbit / p, 2)
    return '{:.2f} Mbit/s'.format(s) if with_text else s


def kodi_file(path):
    return jsonrpc(method='Files.GetFileDetails',
                   params=dict(
                       file=path,
                       media='video',
                       properties=['resume', 'playcount', 'file']
                   ))


def open_settings(query=None, id=ADDON_ID):
    try:
        from resources.lib.system import SYSTEM_VERSION
        exec_build_in('Addon.OpenSettings(%s)' % id)
        if query is None:
            raise Exception()
        c, f = query.split('.')
        if SYSTEM_VERSION >= 18:
            f1 = -100 + int(c)
            f2 = -80 + int(f)
        else:
            f1 = int(c) + 100
            f2 = int(f) + 200
        exec_build_in('SetFocus(%i)' % f1)
        exec_build_in('SetFocus(%i)' % f2)
    except:
        return


def validate_path(path):
    from resources.lib.system import SYSTEM_VERSION
    if SYSTEM_VERSION > 18:
        return xbmcvfs.validatePath(path)
    return xbmc.validatePath(path)


def make_legal_filename(path):
    from resources.lib.system import SYSTEM_VERSION
    if SYSTEM_VERSION > 18:
        return xbmcvfs.makeLegalFilename(path)
    return xbmc.makeLegalFilename(path)


def microtime():
    return float(time.time() * 1000)


def get_percentage(val, total):
    return int(val / total * 100)


def mkdir(path):
    xbmcvfs.mkdir(make_legal_filename(path))


def make_nfo_content(item, typ='movie'):
    out = []
    if SC.ITEM_UIDS in item:
        uids = item[SC.ITEM_UIDS]
        if 'csfd' in uids:
            out.append('https://www.csfd.cz/film/{}'.format(uids['csfd']))
        if 'imdb' in uids:
            out.append('https://www.imdb.com/title/tt{}'.format(uids['imdb']))
        if 'tmdb' in uids:
            out.append('https://www.themoviedb.org/{}/{}-'.format(typ, uids['tmdb']))
        if 'tvdb' in uids:
            out.append('https://www.thetvdb.com/dereferrer/series/{}'.format(uids['tvdb']))
        if 'trakt' in uids:
            out.append('https://trakt.tv/{}/{}'.format(typ, uids['trakt']))
    return "\n".join(out)


def update_addon():
    from resources.lib.common.storage import KodiAddonsDb
    addon_db = KodiAddonsDb()
    addon_db.enable_auto_update()
    exec_build_in('UpdateAddonRepos')
    exec_build_in("UpdateLocalAddons")


def download(url, dest, name):
    from resources.lib.gui.dialog import dprogressgb
    filename = make_legal_filename('{}'.format(os.path.join(translate_path(dest), name)))

    headers = {}
    pos = 0
    if xbmcvfs.exists(filename):
        pos = xbmcvfs.Stat(filename).st_size()
        headers.update({'Range': 'bytes={}-'.format(pos)})

    from resources.lib.system import Http
    r = Http.get(url, headers=headers, stream=True)
    total_length = int(r.headers.get('content-length', 0))
    chunk = min(32 * 1024 * 1024, (1024 * 1024 * 4) if total_length is None else int(total_length / 100))
    f = xbmcvfs.File(filename, 'wb')
    start_pos = pos
    last_pos = pos
    last_t = microtime()
    dialog = dprogressgb()
    dialog.create(name)
    from resources.lib.services.Monitor import monitor
    for data in r.iter_content(chunk):
        if not monitor.abortRequested():
            pos += len(data)
            if total_length > 0:
                t = microtime()
                if (t - last_t) > 5:
                    kbps = int(float(pos - last_pos) / float((t - last_t) / 1000) / 1024)
                    done = get_percentage(pos, start_pos + total_length)
                    debug('download: {}% / {}Kbps'.format(done, kbps))
                    dialog.update(done, message='{}Kbps'.format(kbps))
                    last_t = t
                    last_pos = pos
            f.write(data)
        else:
            debug('Koncim download, lebo konci KODI')
            break
    f.close()
    dialog.close()


def convert_bitrate(mbit, with_text=True):
    if mbit == 0 or mbit is None:
        return "%.2f Mbps" % 0 if with_text else 0
    p = math.pow(1000, 2)
    s = round(mbit / p, 2)
    return "%.2f Mbps" % s if with_text else s


def get_isp():
    for fn in [isp_ipinfo, isp_ipapi, isp_dbip]:
        try:
            isp = fn()
            if isp.get('a') is not None:
                debug('*************************************************** ISP: {}'.format(isp))
                return isp
        except:
            debug('ERRO ISP: {}'.format(traceback.format_exc()))

    return None


def isp_ipinfo():
    from resources.lib.system import Http
    r = Http.get('https://ipinfo.io/widget', headers={'referer': 'https://ipinfo.io/'})
    d = r.json()
    debug('isp_ipinfo: {}'.format(r.text))
    asn = d.get('asn', {}).get('asn', 'N/A')
    return {'c': d.get('country', 'N/A'), 'a': asn.replace('AS', '')}


def isp_call(url, ref):
    from resources.lib.api.sc import Sc
    ip = Sc.get('/IP')
    from resources.lib.system import Http
    url = url.format(ip)
    r = Http.get(url, headers={'referer': ref})
    return r.json()


def isp_ipapi():
    url = 'https://ipapi.com/ip_api.php?ip={}'
    d = isp_call(url, 'https://ipapi.com/')
    asn = d.get('connection', {}).get('asn', 'N/A')
    return {'c': d.get('country_code', 'N/A'), 'a': asn}


def isp_dbip():
    url = 'https://db-ip.com/demo/home.php?s={}'
    d = isp_call(url, 'https://db-ip.com/')
    return {'c': d.get('countryCode', 'N/A'), 'a': d.get('asNumber', '')}
