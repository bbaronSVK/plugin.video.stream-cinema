import json
import traceback
from hashlib import md5

import util

from resources.lib.sctop import post_json, setSetting, getSetting, infoDialog, getString

BASE = 'https://api.kra.sk'

class ResolveException(Exception):
    pass


class Kraska:
    def __init__(self, username=None, password=None, cache=None):
        self.username = username
        self.password = password
        self.cache = cache
        self.token = self.get_token()

    def login(self):
        try:
            util.debug('[SC] kra login start')
            self.set_token(False)
            data = self.get_data('/api/user/login', {'data': {'username': self.username, 'password': self.password}})
            if "session_id" in data:
                util.debug('[SC] kra login OK')
                self.set_token(data.get('session_id'))
                return True
        except:
            util.debug('[SC] kra err login: %s' % str(traceback.format_exc()))
            pass

        infoDialog(data.get('msg', ''), "Nepodarilo sa prihlasit na kra.sk")
        self.set_token(False)
        util.debug('[SC] kra login FALSE')
        return False

    def set_token(self, token):
        self.token = token
        setSetting('kra_token', token)
        util.debug('[SC] kra set token: %s' % str(token))
        chsum = md5(
            "{}|{}".format(self.password.encode('utf-8'),
                           self.username.encode('utf-8'))).hexdigest()
        setSetting('kra_chsum', chsum)
        util.debug('[SC] kra set chsum: %s' % str(chsum))

    def get_token(self):
        util.debug('[SC] get_token')
        try:
            chsum = getSetting('kra_chsum')
            if chsum is None or chsum == '':
                return
            testchsum = md5(
                "{}|{}".format(self.password.encode('utf-8'),
                           self.username.encode('utf-8'))).hexdigest()
            util.debug('[SC] chsum [{}] [{}]'.format(chsum, testchsum))
            if chsum != testchsum:
                util.debug('[SC] prihlasovacie udaje niesu zhodne s tokenom')
                return
        except Exception as e:
            util.debug('[SC] error get token: %s' % str(traceback.format_exc()))
        util.debug('[SC] get_token 2')
        token = getSetting('kra_token')
        if token == '' or 'False' == token:
            token = False
        return token

    def resolve(self, ident):
        util.debug('[SC] kra resolve: %s token: %s' % (str(ident), str(self.token)))
        if self.token is False and not self.login():
            raise ResolveException()

        user_info = self.user_info()
        if user_info is None:
            self.set_token(False)
            self.login()
            user_info = self.user_info()
        if user_info is None:
            raise ResolveException("User nieje prihlaseny")

        if user_info.get('days_left') is None:
            infoDialog("Nemate aktivne predplatne", "Chyba")

        days_left = int(user_info.get('days_left', 0))
        if 14 > days_left > 0:
            infoDialog(getString(30948) % str(user_info.get('days_left')), icon="WARNING")
        try:
            util.debug('[SC] kraska ident: %s' % ident)
            data = self.get_data('/api/file/download', {"data": {"ident": ident}})
            if "data" in data and "link" in data.get("data", {}):
                util.debug('[SC] kra resolve %s' % data.get("data").get("link"))
                return data.get("data").get("link")
            infoDialog("Video neexistuje", "Chyba")
        finally:
            pass
        util.debug('[SC] kra resolve error')
        raise ResolveException("Chybny subor")

    def get_data(self, endpoint, data=None):
        if data is None:
            data = {}
        if self.token:
            data.update({'session_id': self.get_token()})
        util.debug('[SC] kra req: %s %s' % (endpoint, json.dumps(data)))
        try:
            raw_data = post_json(BASE + endpoint, data, {'Content-Type': 'application/json'})
            util.debug('[SC] kra raw response: %s' % raw_data)
            return json.loads(raw_data)
        except Exception as e:
            return False

    def user_info(self, level=0):
        if self.token is False and not self.login():
            return False
        try:
            data = self.get_data('/api/user/info')
            if "error" in data:
                util.debug('[SC] mame error na info')
                raise Exception(data.msg)
            return data.get('data', None)
        except Exception as e:
            util.debug('[SC] kra erro: %s' % str(traceback.format_exc()))
            self.set_token(False)
            if level == 1:
                pass
            elif level == 0 and self.login():
                util.debug('[SC] kra chyba, znova sa pihlasujem....')
                return self.user_info(1)
