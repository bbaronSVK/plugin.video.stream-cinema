import select
import traceback

import websocket
from xbmc import Monitor

from resources.lib.kodiutils import decode, sleep, get_uuid

try:
    import thread
except ImportError:
    import _thread as thread

from resources.lib.common import logger
from resources.lib.services.Monitor import monitor


class SCDispatcher:
    def __init__(self, app, ping_timeout):
        self.app = app
        self.ping_timeout = ping_timeout

    def read(self, sock, read_callback, check_callback):
        while self.app.keep_running and not monitor.abortRequested():
            logger.debug('[WS] loop')
            r, w, e = select.select(
                (self.app.sock.sock,), (), (), self.ping_timeout)
            if r:
                if not read_callback():
                    break
            check_callback()
        logger.debug('[WS] Koncim....')
        self.app.close(status=websocket.STATUS_PROTOCOL_ERROR)


class SSLSCDispatcher:
    def __init__(self, app, ping_timeout):
        self.app = app
        self.ping_timeout = ping_timeout

    def read(self, sock, read_callback, check_callback):
        while self.app.keep_running and not monitor.abortRequested():
            logger.debug('[WS] loop')
            r = self.select()
            logger.debug('[WS] loop 2 {}'.format(r))
            if r:
                if not read_callback():
                    break
            logger.debug('[WS] loop 3 {}'.format(r))
            check_callback()
        logger.debug('[WS] Koncim....')
        try:
            self.app.close(status=websocket.STATUS_PROTOCOL_ERROR)
        except:
            pass

    def select(self):
        sock = self.app.sock.sock
        if sock.pending():
            return [sock, ]

        r, w, e = select.select((sock,), (), (), self.ping_timeout)
        return r


class SCWebSocketApp(websocket.WebSocketApp):
    def __init__(self, url, header=None,
                 on_open=None, on_message=None, on_error=None,
                 on_close=None, on_ping=None, on_pong=None,
                 on_cont_message=None,
                 keep_running=True, get_mask_key=None, cookie=None,
                 subprotocols=None,
                 on_data=None):
        websocket.WebSocketApp.__init__(self, url, header,
                                        on_open, on_message, on_error,
                                        on_close, on_ping, on_pong,
                                        on_cont_message,
                                        keep_running, get_mask_key, cookie,
                                        subprotocols,
                                        on_data)

    def create_dispatcher(self, ping_timeout):
        timeout = ping_timeout or 1
        if self.sock.is_ssl():
            return SSLSCDispatcher(self, timeout)

        return SCDispatcher(self, timeout)


class WS(Monitor):
    def __init__(self):
        super().__init__()
        self.wsapp = None

    def run(self):
        thread.start_new_thread(self.run_ws, ())

    def run_ws(self):
        self.wsapp = SCWebSocketApp("wss://ws.stream-cinema.online",
                                    cookie='uid={}'.format(get_uuid()), on_message=self.on_message)
        try:
            self.wsapp.run_forever()
            self.reconnect()
        except:
            self.reconnect()

    def onNotification(self, sender, method, data):
        try:
            self.wsapp.send(method)
        except:
            pass
        logger.debug('[WS] monitor onNotification {} {} {}'.format(decode(sender), decode(method), decode(data)))

    def reconnect(self):
        if not monitor.abortRequested():
            sleep(1000)
            self.run()

    def on_message(self, message):
        logger.debug('[WS] on_message: {}'.format(message))
