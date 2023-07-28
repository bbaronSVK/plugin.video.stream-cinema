from __future__ import print_function, unicode_literals

import traceback
from datetime import datetime, timedelta as td
from json import loads
from time import time

from xbmc import Player, Monitor

from resources.lib.common.storage import Storage
from resources.lib.services.Settings import settings
from resources.lib.api.sc import Sc
from resources.lib.common.lists import SCKODIItem
from resources.lib.common.logger import debug
from resources.lib.constants import ADDON, ADDON_ID, SC
from resources.lib.gui import home_win, get_cond_visibility as gcv
from resources.lib.gui.item import SCUpNext
from resources.lib.gui.skip import Skip
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
        self.skipped_item = None
        self.skip_button = None
        self.skip_time_start = False
        self.skip_time_end = False
        self.skip_start = False

    def onPlayBackStarted(self):
        self.onAVStarted()

    def set_item(self, item=None):
        self.up_next = False
        self.skip_start = False
        # self.item = item
        json_data = self.win.getProperty('SC.play_item')
        debug('set_item json_data: {}'.format(json_data))
        if not json_data:
            return
        item_data = loads(json_data)
        self.item = item_data.get('info')
        debug('ITEM: {}'.format(self.item.get('info', {}).get('unique_ids')))
        linfo = item_data.get('strms').get('linfo')
        ids = self.win.getProperty('{}.ids'.format(ADDON_ID))
        self.win.clearProperty('{}.ids'.format(ADDON_ID))
        self.ids = loads(ids) if ids else {}
        self.my_id = self.ids.get('sc') if self.ids.get('sc') else None
        debug('my ids: {}'.format(self.ids))
        if self.my_id is not None:
            if self.skipped_item is not False and self.skipped_item != self.my_id:
                self.skipped_item = False
            self.win.setProperty('{}.play'.format(ADDON_ID), '1')
            all_item_data = loads(self.win.getProperty(SC.SELECTED_ITEM))
            if SC.NOTIFICATIONS in all_item_data:
                if SC.SKIP_START in all_item_data.get(SC.NOTIFICATIONS, {}):
                    notification = all_item_data.get(SC.NOTIFICATIONS, {})
                    self.skip_time_start = notification.get(SC.SKIP_START, False)
                    self.skip_time_end = notification.get(SC.SKIP_END, False)
                    debug('NOTIFICATIONS set SKIP TIME: {}s to {}s'.format(td(seconds=self.skip_time_start), td(seconds=self.skip_time_end)))
            debug('je to moj plugin')
            self.is_my_plugin = True
            series = self.item['info'].get('season')
            episode = self.item['info'].get('episode')
            self.movie = SCKODIItem(self.my_id, series=series, episode=episode, trakt=self.ids.get('trakt'))
            self.movie.scrobble(self.percent_played(), SCKODIItem.SCROBBLE_START)
            audio = self.getAvailableAudioStreams()
            if len(audio) == 1:
                debug('Nemame na vyber, mame len jednu audio stopu')
                return

            if linfo:
                audio = linfo
            debug('AvailableAudioStreams {}'.format(len(audio)))
            lang1 = settings.get_setting('stream.lang1').lower()
            lang2 = settings.get_setting('stream.lang2').lower()
            if Sc.parental_control_is_active():
                lang1 = settings.get_setting('parental.control.lang1').lower()
                lang2 = settings.get_setting('parental.control.lang2').lower()

            plf = Storage(SC.ITEM_PREFERRED_LANG)
            plf.load(True)
            debug('PREF LANGS: {} / {}'.format(self.my_id, plf.data))
            force_lang = plf.get(self.my_id)
            force = False
            if force_lang is not None:
                lang = force_lang.lower()
                debug('mame force lang {}'.format(force_lang))
                force = self.try_audio(lang, audio)

            if force is False and self.try_audio(lang1, audio) is False:
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
            language_list = [lang.lower(), lang.upper()]

        for i in language_list:
            if i in streams:
                debug("mame audio: {} pre jazyk {}".format(i, lang))
                stream_number = streams.index(i)
                self.setAudioStream(stream_number)
                # dnotify(lang, '', time=1000, sound=False)
                return True
        return False

    def onAVStarted(self):
        debug('player onAVStarted')
        for i in range(0, 500):
            if self.isPlayback():
                break
            else:
                debug('not playing')
                sleep(1000)
        self.set_item()

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
        self.win.clearProperty('SC.play_item')
        self.win.clearProperty(SC.SELECTED_ITEM)
        self.current_time = 0
        self.ids = {}
        self.is_my_plugin = False
        self.item = None
        self.movie = None
        self.my_id = None
        self.up_next = False
        self.total_time = 0
        self.watched = False
        self.skip_time_start = False
        self.skip_time_end = False
        self.skip_start = False

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
            self.win.setProperty('{}.stop'.format(ADDON_ID), '1')
            percent_played = self.percent_played()

            self.movie.scrobble(percent_played, SCKODIItem.SCROBBLE_STOP)

            if percent_played > 80:
                play_count = self.movie.get_play_count()
                play_count = int(play_count) + 1 if play_count is not None else 1
                debug('playcount {}'.format(play_count))
                d = datetime.fromtimestamp(time())
                self.movie.set_play_count(play_count, True)
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

    def run(self):
        debug('START player bg service')
        m = Monitor()
        self.skip_button = Skip("SkipButton.xml", ADDON.getAddonInfo('path'), "default", "1080i")

        while not m.abortRequested():
            sleep(200)
            try:
                self.periodical_check()
            except:
                debug('player bg service ERR {}'.format(traceback.format_exc()))
        debug('END player bg service')

    def getTime1(self):  # type: () -> float
        try:
            return self.getTime()
        except:
            return 0

    def isPlayingVideo1(self):  # type: () -> bool
        try:
            return self.isPlayingVideo()
        except:
            return False

    def periodical_check(self):
        if self.skip_button.is_button_visible is True:
            debug('rusim SKIP button Notification')
            self.skip_button.close()
            self.skip_button.set_visibility()

        if not self.isPlayback() or self.is_my_plugin is False:
            return

        self.current_time = self.getTime()
        self.total_time = self.getTotalTime()

        if settings.get_setting_as_bool('plugin.show.skip.button') and self.isSkipTime():
            debug('skip: {} / {} / {}'.format(self.skipped_item, self.my_id, self.skip_start))
            if self.skipped_item == self.my_id and self.skip_start is False:
                self.skipStart()
            else:
                self.skip_button.show_with_callback(self.skipStart)
        elif settings.get_setting_as_bool('plugin.show.skip.button'):
            if self.skip_button.is_button_visible is True:
                debug('rusim SKIP button Notification')
                self.skip_button.close()
                self.skip_button.set_visibility()

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

    def isSkipTime(self):
        if self.skip_time_start is False or self.skip_time_end is False:
            return False

        return self.skip_time_start <= self.current_time < self.skip_time_end - 5

    def skipStart(self):
        self.skipped_item = self.my_id
        self.skip_start = True
        self.seekTime(self.skip_time_end)

    def isPlayback(self):  # type: () -> bool
        return self.isPlaying() and self.isPlayingVideo() and self.getTime() >= 0


player = SCPlayer()
