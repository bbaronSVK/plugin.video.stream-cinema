import xbmc
import xbmcgui
import util
from platform import machine

ACTION_PLAYER_STOP = 13
try:
    OS_MACHINE = machine()
except:
    OS_MACHINE = ''


class NextUpInfo(xbmcgui.WindowXMLDialog):
    item = None
    cancel = False
    watchnow = False

    def __init__(self, *args, **kwargs):
        if OS_MACHINE[0:5] == 'armv7':
            xbmcgui.WindowXMLDialog.__init__(self)
        else:
            try:
                xbmcgui.WindowXMLDialog.__init__(self, *args, **kwargs)
            except:
                try:
                    xbmcgui.WindowXMLDialog.__init__(self)
                except:
                    pass

    def onInit(self):
        self.action_exitkeys_id = [10, 13]
        image = self.item['art'].get('poster', '')
        thumb = self.item['art'].get('thumb', '')
        clearartimage = self.item['art'].get('tvshow.clearart', '')
        landscapeimage = self.item['art'].get('tvshow.landscape', '')
        fanartimage = self.item['art'].get('fanart', '')
        overview = self.item.get('plot')
        tvshowtitle = self.item['tvshowtitle']
        name = self.item['title']

        season = self.item['season']
        episodeNum = self.item['episode']
        episodeInfo = str(season) + 'x' + str(episodeNum) + '.'

        if 'rating' in self.item:
            rating = str(round(float(self.item['rating']), 1))
        year = self.item.get('year', '')
        info = year

        # set the dialog data
        self.getControl(3000).setLabel(name)
        self.getControl(3001).setText(overview)
        self.getControl(3002).setLabel(episodeInfo)
        self.getControl(3004).setLabel(info)

        if rating is not None:
            self.getControl(3003).setLabel(rating)
        else:
            self.getControl(3003).setVisible(False)

        try:
            tvShowControl = self.getControl(3007)
            if tvShowControl != None:
                tvShowControl.setLabel(tvshowtitle)
        except:
            pass

        try:
            posterControl = self.getControl(3009)
            if posterControl != None:
                posterControl.setImage(image)
        except:
            pass

        try:
            fanartControl = self.getControl(3005)
            if fanartControl != None:
                util.debug(
                    "[SC] upNext fanart: %s" %
                    fanartimage.replace('thetvdb.com', 'stream-cinema.online'))
                fanartControl.setImage(
                    fanartimage.replace('thetvdb.com', 'stream-cinema.online'))
            else:
                util.debug("[SC] upNext fanart: NEMAME CONTROL %s" %
                           fanartimage)
        except:
            pass

        try:
            thumbControl = self.getControl(3008)
            if thumbControl != None:
                self.getControl(3008).setImage(thumb)
        except:
            pass

        try:
            landscapeControl = self.getControl(3010)
            if landscapeControl != None:
                self.getControl(3010).setImage(landscapeimage)
        except:
            pass

        try:
            clearartimageControl = self.getControl(3006)
            if clearartimageControl != None:
                self.getControl(3006).setImage(clearartimage)
        except:
            pass

        try:
            seasonControl = self.getControl(3015)
            if seasonControl != None:
                seasonControl.setLabel(str(season))
        except:
            pass

        try:
            episodeControl = self.getControl(3016)
            if episodeControl != None:
                episodeControl.setLabel(str(episodeNum))
        except:
            pass

        try:
            resolutionControl = self.getControl(3011)
            if resolutionControl != None:
                resolution1 = self.get('mvideo')
                resolution = resolution1.get('height')
                resolutionControl.setLabel(str(resolution))
        except:
            pass

    def setItem(self, item):
        self.item = item

    def setCancel(self, cancel):
        self.cancel = cancel

    def isCancel(self):
        return self.cancel

    def setWatchNow(self, watchnow):
        self.watchnow = watchnow

    def isWatchNow(self):
        return self.watchnow

    def onFocus(self, controlId):
        pass

    def doAction(self):
        pass

    def closeDialog(self):
        self.close()

    def onClick(self, controlID):

        util.debug('nextup info onclick: ' + str(controlID))

        if controlID == 3012:

            # watch now
            self.setWatchNow(True)
            self.close()
        elif controlID == 3013:

            # cancel
            self.setCancel(True)
            self.close()

        pass

    def onAction(self, action):

        util.debug('nextup info action: ' + str(action.getId()))
        if action == ACTION_PLAYER_STOP:
            self.close()
