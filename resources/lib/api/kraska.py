import json
import traceback
from hashlib import md5

from resources.lib.common.logger import debug
from resources.lib.constants import ADDON
from resources.lib.gui.dialog import dnotify, dyesno, dok
from resources.lib.kodiutils import open_settings
from resources.lib.language import Strings
from resources.lib.services.Settings import settings
from resources.lib.system import Http

BASE = 'https://api.kra.sk'


class ResolveException(Exception):
    pass


class Kraska:
    token = False

    def __init__(self, u=None, p=None):
        self.username = u if u is not None else settings.get_setting('kraska.user')
        self.password = p if p is not None else settings.get_setting('kraska.pass')

    def login(self):
        try:
            debug('kra login start ****/****'.format(self.username, self.password))
            data = self.get_data('/api/user/login', {'data': {'username': self.username, 'password': self.password}})
            if "session_id" in data:
                debug('kra login OK')
                self.set_token(data.get('session_id'))
                return True
        except:
            debug('kra err login: {}'.format(traceback.format_exc()))
            data = {}
            pass
        self.set_token(False)
        debug('DATA: {}'.format(data))
        debug('kra login FALSE')
        return False

    def set_token(self, token):
        if token != self.token:
            self.token = token
            debug('kra set token: {}'.format(str(token)))
            checksum_credentials = self._get_chsum(self.username, self.password)
            settings.set_setting('kraska.chsum', '{}'.format(checksum_credentials))
            settings.set_setting('kraska.token', '{}'.format(token))
            debug('kra set chsum: {}'.format(checksum_credentials))

    @staticmethod
    def _get_chsum(username, password):
        return md5(
            "{}|{}".format(password.encode('utf-8'),
                           username.encode('utf-8')).encode('utf-8')).hexdigest()

    def get_token(self):
        # debug('get_token start')
        try:
            chsum = settings.get_setting('kraska.chsum')
            if chsum is None or chsum == '':
                self.token = False
                return False
            testchsum = self._get_chsum(self.username, self.password)
            debug('chsum [{}] vs [{}]'.format(chsum, testchsum))
            if chsum != testchsum:
                debug('prihlasovacie udaje niesu zhodne s tokenom, treba login')
                self.token = False
                return False
        except Exception as e:
            debug('error get token: {}'.format(traceback.format_exc()))
            self.token = False
            return False
        # debug('get_token from settings')
        token = settings.get_setting('kraska.token')
        if token == '' or 'False' == token or None is token:
            token = False
        self.token = token
        # debug('get_token: {}'.format(token))
        return token

    def resolve(self, ident):
        # debug('kra resolve: {} token: {}'.format(ident, self.get_token()))
        if self.get_token() is False:
            debug('nemame token v resolve a nepodarilo sa nam ani prihlasit')
            if self.login() is False:
                self.wrong_credential()
                return None

        debug('ideme na zostavajuce dni')
        try:
            days_left = self.get_days_left()
            if days_left is None:
                raise Exception
        except:
            dok(Strings.txt(Strings.RESOLVE_ERROR_H1), Strings.txt(Strings.KRASKA_NOTIFY_NO_SUBSCRIPTION))
            return None

        if 14 >= days_left:
            debug('mame nizky pocet dni predplatneho')
            dnotify(Strings.txt(Strings.KRASKA_NOTIFY_LOW_DAYS_LEFT).format(days_left), '')
        try:
            debug('skusame resolvnut ident: {}'.format(ident))
            data = self.get_data('/api/file/download', {"data": {"ident": ident}})
            if "data" in data and "link" in data.get("data", {}):
                debug('kra resolvovala {}'.format(data.get("data").get("link")))
                return data.get("data").get("link").replace('b01', 'b02')
            debug('Nepodarilo sa resolvnut subor: {}'.format(ident))
        finally:
            pass
        debug('kra resolve error')
        raise ResolveException("Chybny subor")

    def get_days_left(self):
        debug('get days left')
        user_info = self.user_info()
        if user_info is None or user_info is False:
            debug('nepodarilo sa natiahnut info o userovi')
            self.set_token(False)
            raise ResolveException("User nieje prihlaseny")

        if user_info.get('subscribed_until', None) is None:
            debug('user nema aktivne predplatne')
            raise ResolveException("Nieje predplatne")

        debug('idem vratit pocet dni {}'.format(user_info))
        return user_info.get('days_left', 0)

    def get_data(self, endpoint, data=None):
        if data is None:
            data = {}
        if self.token:
            data.update({'session_id': self.token})
        debug('kra req: {}'.format(endpoint, json.dumps(data)))
        try:
            raw_data = Http.post(BASE + endpoint, json=data)
            # debug('kra raw response: {}'.format(raw_data.text))
            return raw_data.json()
        except Exception as e:
            return False

    def user_info(self, level=0):
        debug('skusam natiahnut user info')
        if self.get_token() is False:
            if self.login() is False:
                debug('Nepodarilo sa ziskat info o userovi, lebo nieje prihlaseny')
                return False
        debug('mame token/sme uz prihlaseny')
        try:
            data = self.get_data('/api/user/info')
            if data is False or 'data' not in data:
                debug('mame error na info {}'.format(data))
                raise Exception(data.get('msg', 'kraska error'))
            days_left = data.get('data', {}).get('days_left', 0)
            days_left = 0 if days_left is None else days_left
            settings.set_setting('kraska.days.left', days_left)
            debug('vracame info o userovi {}'.format(data.get('data', False)))
            return data.get('data', False)
        except Exception as e:
            debug('kra erro: {}'.format(traceback.format_exc()))
            self.set_token(False)
            if level == 0:
                debug('skusame znova natiahnut info o userovi')
                return self.user_info(1)
        debug('vzdali sme info o userovi ... nieje prihlaseny')
        return False

    def check_user(self):
        debug('check_user start')
        if settings.get_setting('kraska.user'):
            try:
                if not self.user_info():
                    raise Exception()
            except:
                self.wrong_credential()
                return

            try:
                self.get_days_left()
            except:
                dok('{} - {}'.format(Strings.txt(Strings.RESOLVE_ERROR_H1), ADDON.getAddonInfo('name')), Strings.txt(Strings.KRASKA_NOTIFY_NO_SUBSCRIPTION))

    def wrong_credential(self):
        res = dyesno('{} - {}'.format(Strings.txt(Strings.KRASKA_NOTIFY_CREDENTIAL_H1), ADDON.getAddonInfo('name')),
                     Strings.txt(Strings.KRASKA_NOTIFY_CREDENTIAL_L1))
        if res:
            open_settings('0.0')
