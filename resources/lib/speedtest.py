import bisect
import random
import re
import traceback
import util

from math import sqrt
from threading import currentThread, Thread
from time import time

try:
    from httplib import HTTPConnection, HTTPSConnection
except ImportError:
    from http.client import HTTPConnection, HTTPSConnection

try:
    from urllib import urlencode
except ImportError:
    from urllib.parse import urlencode


class speedTest():
    USER_AGENTS = {
        'Linux':
        'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:41.0) Gecko/20100101 Firefox/41.0',
        'Darwin':
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.10; rv:41.0) Gecko/20100101 Firefox/41.0',
        'Windows':
        'Mozilla/5.0 (Windows NT 6.3; WOW64; rv:41.0) Gecko/20100101 Firefox/41.0',
        'Java': 'Java/1.6.0_12',
    }

    def __init__(self, host=None, runs=3, size=[1500, 2000], type='http'):
        self._host = host
        self.type = type
        self.runs = runs
        self.DOWNLOAD_FILES = []
        util.debug("size: %s" % str(size))
        for i in size:
            self.DOWNLOAD_FILES.append('/speedtest/random%sx%s.jpg' % (i, i))
        util.debug('FILES: %s' % str(self.DOWNLOAD_FILES))

    @property
    def host(self):
        if not self._host:
            self._host = self.chooseserver()
        return self._host

    @host.setter
    def host(self, new_host):
        self._host = new_host

    def connect(self, url):
        try:
            connection = HTTPConnection(
                url) if self.type == 'http' else HTTPSConnection(url)
            connection.connect()
            return connection
        except:
            raise Exception('Unable to connect to %r' % url)

    def downloadthread(self, connection, url):
        connection.request('GET', url, None, {'Connection': 'Keep-Alive'})
        response = connection.getresponse()
        self_thread = currentThread()
        self_thread.downloaded = len(response.read())

    def download(self, urls=None):
        total_downloaded = 0
        if urls is None:
            connections = [self.connect(self.host) for i in range(self.runs)]
        else:
            connections = [self.connect(h['host']) for h in urls]
        total_start_time = time()
        for current_file in self.DOWNLOAD_FILES:
            threads = []
            for run in range(self.runs):
                thread = Thread(target=self.downloadthread,
                                args=(connections[run], '%s?x=%d' %
                                      (current_file, int(time() * 1000))
                                      if urls is None else urls[run]['url']))
                thread.run_number = run + 1
                thread.start()
                threads.append(thread)
            for thread in threads:
                try:
                    thread.join()
                    total_downloaded += thread.downloaded
                    util.debug('[SC] Run %d for %s finished' %
                               (thread.run_number, current_file))
                except:
                    pass
        total_ms = (time() - total_start_time) * 1000
        for connection in connections:
            connection.close()
        util.info('[SC] Took %d ms to download %d bytes' %
                  (total_ms, total_downloaded))
        return total_downloaded * 8000 / total_ms

    def ping(self, server=None):
        if not server:
            server = self.host

        connection = self.connect(server)
        times = []
        worst = 0
        for _ in range(5):
            total_start_time = time()
            connection.request('GET',
                               '/speedtest/latency.txt?x=%d' % randint(), None,
                               {'Connection': 'Keep-Alive'})
            response = connection.getresponse()
            response.read()
            total_ms = time() - total_start_time
            times.append(total_ms)
            if total_ms > worst:
                worst = total_ms
        times.remove(worst)
        total_ms = sum(times) * 250  # * 1000 / number of tries (4) = 250
        connection.close()
        util.debug('[SC] Latency for %s - %d' % (server, total_ms))
        return total_ms

    def chooseserver(self):
        connection = self.connect('c.speedtest.net')
        now = int(time() * 1000)
        # really contribute to speedtest.net OS statistics
        # maybe they won't block us again...
        extra_headers = {
            'Connection': 'Keep-Alive',
            'User-Agent': self.USER_AGENTS['Linux']
        }
        connection.request('GET', '/speedtest-config.php?x=%d' % now, None,
                           extra_headers)
        response = connection.getresponse()
        reply = response.read().decode('utf-8')
        match = re.search(r'<client ip="([^"]*)" lat="([^"]*)" lon="([^"]*)"',
                          reply)
        location = None
        if match is None:
            util.info('[SC] Failed to retrieve coordinates')
            return None
        location = match.groups()
        util.info('[SC] Your IP: %s' % location[0])
        util.info('[SC] Your latitude: %s' % location[1])
        util.info('[SC] Your longitude: %s' % location[2])
        try:
            connection.request('GET', '/speedtest-servers.php?x=%d' % now,
                               None, extra_headers)
            response = connection.getresponse()
            reply = response.read().decode('utf-8')
            server_list = re.findall(
                r'<server url="([^"]*)" lat="([^"]*)" lon="([^"]*)"', reply)
            my_lat = float(location[1])
            my_lon = float(location[2])
            sorted_server_list = []
            for server in server_list:
                s_lat = float(server[1])
                s_lon = float(server[2])
                distance = sqrt(
                    pow(s_lat - my_lat, 2) + pow(s_lon - my_lon, 2))
                bisect.insort_left(sorted_server_list, (distance, server[0]))
            best_server = (999999, '')
            for server in sorted_server_list[:10]:
                util.debug('[SC] server: %s' % server[1])
                match = re.search(r'http://([^/]+)/speedtest/upload\.php',
                                  server[1])
                if match is None:
                    continue
                server_host = match.groups()[0]
                try:
                    latency = self.ping(server_host)
                except Exception as e:
                    util.debug('[SC] ping exception: %s' % e)
                    continue
                if latency < best_server[0]:
                    best_server = (latency, server_host)
            if not best_server[1]:
                raise Exception('Cannot find a test server')
            util.debug('[SC] Best server: %s' % best_server[1])
            return best_server[1]
        except Exception as e:
            pass
        raise Exception('Cannot find a test server')


def pretty_speed(speed):
    units = ['bps', 'Kbps', 'Mbps', 'Gbps']
    unit = 0
    while speed >= 1024:
        speed /= 1024
        unit += 1
    return '%0.2f %s' % (speed, units[unit])


def randint():
    """Return a random 12 digit integer."""
    return random.randint(100000000000, 999999999999)
