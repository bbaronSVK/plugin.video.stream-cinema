from __future__ import print_function, unicode_literals
import json
import math
import sys
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
from resources.lib.language import translate
from resources.lib.common.txt import _decode

addon = xbmcaddon.Addon(id=ADDON_ID)


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
    cmd = ('{"jsonrpc":"2.0", "method":"Application.GetProperties",'
           '"params": {"properties": ["name"]}, "id":1}')
    try:
        data = json.loads(xbmc.executeJSONRPC(cmd))
        if "result" in data and "name" in data["result"]:
            return data["result"]["name"]
    except:
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
    if uuid_value:
        debug('UUID from settings: {}'.format(uuid_value))
        return uuid_value

    uuid_value = None
    system = get_system_platform()
    if system in ['windows', 'uwp']:
        uuid_value = _get_windows_uuid()
        debug('Windows UUID Found')
    elif system == 'android':
        uuid_value = _get_android_uuid()
        debug('Android UUID Found')
    elif system == 'linux':
        uuid_value = _get_linux_uuid()
        debug('Linux UUID Found')
    elif system == 'osx':
        uuid_value = _get_macos_uuid()
        debug('OSX, IOS UUID Found {}'.format(uuid_value))
    if not uuid_value:
        debug('It is not possible to get a system UUID creating a new UUID')
        uuid_value = get_setting('system.uuid')
        debug('UUID from settings: {}'.format(uuid_value))
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
    values = ''
    try:
        # Due to the new android security we cannot get any type of serials
        sys_prop = ['ro.product.board', 'ro.product.brand', 'ro.product.device', 'ro.product.locale'
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
            "dtitle", "url", "action", "list", "cmd", "down", "play",
            "force", "search-list", "search", "csearch", "search-remove",
            "search-edit", "tl", "id", "subtype", "title", "name", "imdb",
            "tvdb", "csfd", "trakt", "content", "tu", "page", "list", "selectStream"
        ]:
            continue

        value = '{}'.format(translate(param[key]))

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
    data = [_decode(b64encode(json.dumps(next_info).encode()))]
    notify(sender=sender + '.SIGNAL', message='upnext_data', data=data)


def notify(sender, message, data):
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