# -*- coding: UTF-8 -*-
import xbmc
import xbmcgui
import json
import time
import top
import os
from datetime import datetime, timedelta
import _strptime
import buggalo
import util
import traceback
import scutils

class MyPlayer(xbmc.Player):

    def __init__(self, *args, **kwargs):
        try:
            self.log("[SC] player 1")
            self.estimateFinishTime = '00:00:00'
            self.realFinishTime = '00:00:00'
            self.itemDuration = '00:00:00'
            self.win = xbmcgui.Window(10000)
            self.scid = None
            self.itemDBID = None
            self.itemType = None
            self.parent = None
        except Exception:
            self.log("SC Chyba MyPlayer: %s" % str(traceback.format_exc()))

    @staticmethod
    def executeJSON(request):
        # =================================================================
        # Execute JSON-RPC Command
        # Args:
        # request: Dictionary with JSON-RPC Commands
        # Found code in xbmc-addon-service-watchedlist
        # =================================================================
        rpccmd = json.dumps(request)  # create string from dict
        json_query = xbmc.executeJSONRPC(rpccmd)
        json_query = unicode(json_query, 'utf-8', errors='ignore')
        json_response = json.loads(json_query)
        return json_response

    @staticmethod
    def get_sec(time_str):
        # nasty bug appears only for 2nd and more attempts during session
        # workaround from: http://forum.kodi.tv/showthread.php?tid=112916
        try:
            t = datetime.strptime(time_str, "%H:%M:%S")
        except TypeError:
            t = datetime(*(time.strptime(time_str, "%H:%M:%S")[0:6]))
        return timedelta(hours=t.hour, minutes=t.minute, seconds=t.second)

    @staticmethod
    def log(text):
        xbmc.log(str([text]), xbmc.LOGDEBUG)
        
    def setWatched(self):
        if self.itemDBID == None:
            return
        if self.itemType == 'episode':
            metaReq = {"jsonrpc": "2.0",
                       "method": "VideoLibrary.SetEpisodeDetails",
                       "params": {"episodeid": self.itemDBID,
                                  "playcount": 1},
                       "id": 1}
            self.executeJSON(metaReq)
        elif self.itemType == 'movie':
            metaReq = {"jsonrpc": "2.0",
                       "method": "VideoLibrary.SetMovieDetails",
                       "params": {"movieid": self.itemDBID,
                                  "playcount": 1},
                       "id": 1}
            self.executeJSON(metaReq)

    def createResumePoint(self, seconds, total):
        return
        try:
            pomer = seconds / total
            if pomer < 0.05:
                return
            self.pomSlovnik.update({self.itemDBID: seconds})
        except Exception:
            buggalo.onExceptionRaised({'seconds: ': seconds})
        return

    def onPlayBackStarted(self):
        self.log("[SC] Zacalo sa prehravat")
        mojPlugin = self.win.getProperty(top.__scriptid__)
        if top.__scriptid__ not in mojPlugin:
            util.debug("[SC] Nieje to moj plugin ... ")
            return;
        util.debug("[SC] JE to moj plugin ... %s" % str(mojPlugin))
        self.scid = self.win.getProperty('scid')
        self.win.clearProperty(top.__scriptid__)
        self.win.clearProperty('scid')
        try:
            if not self.isPlayingVideo():
                return
            
            while True:
                scutils.KODISCLib.sleep(1000)
                if xbmc.abortRequested:
                    return
                self.itemDuration = xbmc.getInfoLabel(
                    'Player.TimeRemaining(hh:mm:ss)')
                if (self.itemDuration != '') and (self.itemDuration != '00:00:00'):
                    self.itemDuration = self.get_sec(self.itemDuration)
                    break
            # plánovaný čas dokončení 100 % přehrání
            self.estimateFinishTime = xbmc.getInfoLabel(
                'Player.FinishTime(hh:mm:ss)')
            season = xbmc.getInfoLabel('VideoPlayer.Season')
            episode = xbmc.getInfoLabel('VideoPlayer.Episode')
            showtitle = xbmc.getInfoLabel('VideoPlayer.TVShowTitle')
            year = xbmc.getInfoLabel('VideoPlayer.Year')
            title = xbmc.getInfoLabel('VideoPlayer.Title')
            imdb = xbmc.getInfoLabel("VideoPlayer.IMDBNumber") #"ListItem.IMDBNumber")

            if showtitle:
                self.itemType = 'episode'
            else:
                self.itemType = 'movie'

            try:
                if self.itemType == 'movie':
                    method = 'VideoLibrary.GetMovies'
                    value = "%s (%s).strm" % (str(title), str(year))
                    field = 'filename'
                    res = self.executeJSON({'jsonrpc': '2.0', 'method': method, 
                        'params': {'filter':
                            {'operator': 'contains', 'field': field, 'value': value}
                        }, 'id': 1})

                    if 'result' in res:
                        for m in res['result']['movies']:
                            util.debug("[SC] m: %s" % str(m))
                            if 'movieid' in m:
                                self.itemDBID = m['movieid']
                                break
                else:
                    if self.parent is not None:
                        try:
                            self.parent.addLast(self.scid)
                        except Exception, e:
                            util.error(e)
                            pass
                        
                    method = 'VideoLibrary.GetTVShows'
                    value = showtitle #/Season %s/%sx%s.strm" % (showtitle, season, season, episode)
                    field = 'path'
                    res = self.executeJSON({'jsonrpc': '2.0', 'method': method, 
                        'params': {'filter':
                            {'operator': 'contains', 'field': field, 'value': value}
                        }, 'id': 1})

                    if 'result' in res:
                        for m in res['result']['tvshows']:
                            if 'tvshowid' in m:
                                self.itemDBID = int(m['tvshowid'])
                                res = self.executeJSON({'jsonrpc': '2.0', 
                                    'method': 'VideoLibrary.GetEpisodes', 'params': {
                                        'tvshowid': int(m['tvshowid']), 'season': int(season), 
                                        'properties': ['episode', 'file'], 
                                        'sort': {'method': 'episode'}
                                        }, 'id': 1})
                                for e in res['result']['episodes']:
                                    if int(e['episode']) == int(episode):
                                        self.itemDBID = e['episodeid']
                                        break
                                break

            except Exception:
                self.log("[SC] Chyba JSONRPC: %s" % str(traceback.format_exc()))
                pass
                        
            res = self.executeJSON({'jsonrpc': '2.0', 'method': 'Player.GetItem', 
                'params': {'playerid': 1}, 'id': 1})
            if res:
                _filename = None
                try:
                    _filename = os.path.basename(self.getPlayingFile())
                except:
                    util.debug("[SC] onPlayBackStarted() - Exception trying to get playing filename, player suddenly stopped.")
                    return
                util.debug("[SC] Zacalo sa prehravat: DBID: [%s], SCID: [%s] imdb: %s dur: %s est: %s fi: [%s] | %sx%s - title: %s (year: %s) showtitle: %s" % (str(self.itemDBID), str(self.scid), str(imdb), self.itemDuration, self.estimateFinishTime, _filename, str(season), str(episode), str(title), str(year), str(showtitle)))
                data = {'scid': self.scid, 'action': 'start', 'ep': episode, 'se': season}
                    
                self.action(data)
                if 'item' in res and 'id' not in res['item']:
                    util.debug("[SC] prehravanie mimo kniznice")
        except Exception:
            self.log("[SC] Chyba MyPlayer: %s" % str(traceback.format_exc()))
            pass

    def onPlayBackEnded(self):
        self.log("[SC] Skoncilo sa prehravat")
        self.setWatched()
        data = {'scid': self.scid, 'action': 'end'}
        self.action(data)
        self.itemDBID = None;
        return

    def onPlayBackStopped(self):
        self.log("[SC] Stoplo sa prehravanie")
        data = {'scid': self.scid, 'action': 'stop'}
        self.action(data)
        self.itemDBID = None;
        try:
            self.realFinishTime = xbmc.getInfoLabel(
                'Player.FinishTime(hh:mm:ss)')
            timeDifference = self.get_sec(self.estimateFinishTime) - \
                self.get_sec(self.realFinishTime)
            timeRatio = timeDifference.seconds / \
                float((self.itemDuration).seconds)
            if abs(timeRatio) < 0.2:
                util.debug("[SC] videne %s" % str(timeRatio))
                self.setWatched()
            else:
                util.debug("[SC] vytvorit pokracovanie %s" % str(timeRatio))
                self.createResumePoint((1 - timeRatio) * float((self.itemDuration).seconds),
                                       float((self.itemDuration).seconds))
        except Exception:
            pass
        return
        
    def waitForChange(self):
        scutils.KODISCLib.sleep(200)
        while True:
            if xbmc.abortRequested or not self.isPlayingVideo():
                return
            pom = xbmc.getInfoLabel('Player.FinishTime(hh:mm:ss)')
            if pom != self.estimateFinishTime:
                self.estimateFinishTime = pom
                break
            scutils.KODISCLib.sleep(100)

    def onPlayBackResumed(self):
        self.log("[SC] Znova sa prehrava")
        self.waitForChange()
        data = {'scid': self.scid, 'action': 'resume'}
        self.action(data)
        return;

    def onPlayBackSpeedChanged(self, speed):
        self.log("[SC] Zmennila sa rychlost prehravania %s" % speed)
        self.waitForChange()
        data = {'scid': self.scid, 'action': 'speed', 'speed': speed}
        self.action(data)
        return

    def onPlayBackSeek(self, time, seekOffset):
        self.log("[SC] Seekujem %s %s" % (time, seekOffset))
        self.waitForChange()
        data = {'scid': self.scid, 'action': 'seek', 'time': time, 'seekOffset': seekOffset}
        self.action(data)
        return
    
    def onPlayBackPaused(self):
        self.log("[SC] Pauza")
        self.waitForChange()
        data = {'scid': self.scid, 'action': 'pause'}
        self.action(data)
        return
    
    def action(self, data):
        url = "%s/Stats" % (top.BASE_URL)
        data.update({'est': self.estimateFinishTime})
        if (self.itemDuration).seconds > 0:
            data.update({'dur':(self.itemDuration).seconds})
        self.log("[SC] action: %s" % str(data))
        util.post_json(url, data, {'X-UID': top.uid})
        
