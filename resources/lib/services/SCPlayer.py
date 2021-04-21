from __future__ import print_function, unicode_literals

import traceback
from datetime import datetime
from json import loads
from time import time

from xbmc import Player

from resources.lib.services.Settings import settings
from resources.lib.api.sc import Sc
from resources.lib.common.lists import SCKODIItem
from resources.lib.common.logger import debug
from resources.lib.constants import ADDON_ID
from resources.lib.gui import home_win, get_cond_visibility as gcv
from resources.lib.gui.item import SCUpNext
from resources.lib.kodiutils import upnext_signal, sleep


class SCPlayer(Player):
    def __init__(self):
        self.settings = settings
        self.win = home_win
        self.current_time = 0
        self.item = None
        self.is_my_plugin = False
        self.movie = None
        self.my_id = None
        self.total_time = 0
        self.ids = {}
        self.watched = False
        self.up_next = False

    def onPlayBackStarted(self):
        self.onAVStarted()

    def set_item(self, item):
        self.up_next = False
        # self.item = item
        if not self.win.getProperty('SC.play_item'):
            return
        item_data = loads(self.win.getProperty('SC.play_item'))
        self.win.clearProperty('SC.play_item')
        self.item = item_data.get('info')
        debug('ITEM: {}'.format(self.item.get('info', {}).get('unique_ids')))
        linfo = item_data.get('strms').get('linfo')
        ids = self.win.getProperty('{}.ids'.format(ADDON_ID))
        self.win.clearProperty('{}.ids'.format(ADDON_ID))
        self.ids = loads(ids) if ids else {}
        self.my_id = self.ids.get('sc') if self.ids.get('sc') else None
        debug('my ids: {}'.format(self.ids))
        if self.my_id is not None:
            self.win.setProperty('{}.play'.format(ADDON_ID), 1)
            debug('je to moj plugin')
            self.is_my_plugin = True
            series = self.item['info'].get('season')
            episode = self.item['info'].get('episode')
            self.movie = SCKODIItem(self.my_id, series=series, episode=episode, trakt=self.ids.get('trakt'))
            self.movie.scrobble(self.percent_played(), SCKODIItem.SCROBBLE_START)
            audio = self.getAvailableAudioStreams()
            if linfo:
                audio = linfo
            debug('AvailableAudioStreams {}'.format(audio))
            lang1 = settings.get_setting('stream.lang1').lower()
            lang2 = settings.get_setting('stream.lang2').lower()
            if Sc.parental_control_is_active():
                lang1 = settings.get_setting('parental.control.lang1').lower()
                lang2 = settings.get_setting('parental.control.lang2').lower()
            if self.try_audio(lang1, audio) is False:
                self.try_audio(lang2, audio)

    def try_audio(self, lang, streams):
        if lang == 'sk':
            language_list = ['slo', 'sk', 'slk', 'SK']
        elif lang == 'cz':
            language_list = ['cze', 'cz', 'ces', 'CZ']
        elif lang == 'en':
            language_list = ['eng', 'en', 'EN']
        else:
            debug("iny jazyk {}".format(lang))
            return False
        for i in language_list:
            if i in streams:
                debug("mame audio: {} pre jazyk {}".format(i, lang))
                stream_number = streams.index(i)
                self.setAudioStream(stream_number)
                return True
        return False

    def onAVStarted(self):
        debug('player onAVStarted')

    def onAVChange(self):
        debug('player onAVChange')
        if self.is_my_plugin is True:
            debug('moj plugin')

    def onPlayBackEnded(self):
        debug('player onPlayBackEnded')
        self.end_playback()

    def onPlayBackStopped(self):
        debug('player onPlayBackStopped')
        self.end_playback()

    def onPlayBackError(self):
        debug('player onPlayBackError')
        self.end_playback()

    def onPlayBackPaused(self):
        debug('player onPlayBackPaused')
        self.end_playback()

    def onPlayBackResumed(self):
        debug('player onPlayBackResumed')
        if self.movie is not None:
            self.movie.scrobble(self.percent_played(), SCKODIItem.SCROBBLE_START)

    def onQueueNextItem(self):
        debug('player onQueueNextItem')

    def onPlayBackSpeedChanged(self, speed):
        debug('player onPlayBackSpeedChanged {}'.format(speed))

    def onPlayBackSeek(self, time, seekOffset):
        debug('player onPlayBackSeek {} {}'.format(time, seekOffset))

    def onPlayBackSeekChapter(self, chapter):
        debug('player onPlayBackSeekChapter {}'.format(chapter))

    def clean(self):
        debug('player SCPlayer Clean')
        #
        self.win.clearProperty('{}.play'.format(ADDON_ID))
        self.current_time = 0
        self.ids = {}
        self.is_my_plugin = False
        self.item = None
        self.movie = None
        self.my_id = None
        self.up_next = False
        self.total_time = 0
        self.watched = False

    def end_playback(self):
        self.set_watched()
        self.clean()

    def percent_played(self):
        try:
            return self.current_time / self.total_time * 100
        except:
            return 0

    def set_watched(self):
        if self.is_my_plugin:
            percent_played = self.percent_played()

            self.movie.scrobble(percent_played, SCKODIItem.SCROBBLE_STOP)

            if percent_played > 80:
                play_count = self.movie.get_play_count()
                play_count = int(play_count) + 1 if play_count is not None else 1
                debug('playcount {}'.format(play_count))
                d = datetime.fromtimestamp(time())
                self.movie.set_play_count(play_count)
                self.movie.set_last_played(d.strftime('%Y-%m-%d %H:%M:%S'))
            if 3 < percent_played < 80:
                debug('watched {}'.format(self.current_time))
                self.movie.set_watched(self.current_time)

    def check_up_next(self, percent_played):
        return gcv('System.hasAddon(service.upnext)') and self.item and self.item['info'].get(
            'episode') is not None and self.up_next is False

    def send_up_next(self):
        try:
            series = self.item['info'].get('season')
            episode = self.item['info'].get('episode')
            url = '/upNext/{}/{}/{}'.format(self.my_id, series, episode)
            debug('upnext call {}'.format(url))
            data = Sc.get(url)
            if 'info' in data:
                debug('Mame next item: {}'.format(data))
                d = SCUpNext(data)
                # sleep(3 * 1000)
                upnext_signal(ADDON_ID, d.get())
        except:
            debug('send_up_next ERR {}'.format(traceback.format_exc()))

    def periodical_check(self):
        if not self.isPlayingVideo() or self.is_my_plugin is False:
            return

        self.current_time = self.getTime()
        self.total_time = self.getTotalTime()
        try:
            percent_played = self.current_time / self.total_time * 100
        except:
            percent_played = 0
        # debug('self.watched: {} {}'.format(self.watched, percent_played))
        if percent_played >= 80 and not self.watched:
            self.set_watched()
            self.watched = True
        if self.check_up_next(percent_played):
            debug('Mame upnext nainstalovane')
            try:
                self.send_up_next()
            except:
                pass
            self.up_next = True


player = SCPlayer()
