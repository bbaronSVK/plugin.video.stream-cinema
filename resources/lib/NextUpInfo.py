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
        '''
        u'rating': u'7.7', 
        u'code': u'tt0898266', 
        u'art': {
            u'fanart': u'http://thetvdb.com/banners/fanart/original/80379-62.jpg', 
            u'poster': u'http://thetvdb.com/banners/posters/80379-43.jpg', 
            u'banner': u'http://thetvdb.com/banners/graphical/80379-g28.jpg', 
            u'thumb': u'http://thetvdb.com/banners/episodes/80379/332484.jpg'}, 
        u'subs': None, 
        u'maudio': {
            u'channels': 2, 
            u'codec': u'mp3'}, 
        u'csfd': u'234260', 
        u'tmdb': u'0', 
        u'imdb': u'898266', 
        u'year': u'2007', 
        u'duration': u'1375.374000', 
        u'quality': u'SD', 
        u'id': u'3903', 
        u'size': u'174.21 MB', 
        u'plot': u'Kdy\\u017e se Sheldon a Leonard vrac\\xed ze spermobanky pro jedince s vysok\\xfdm IQ, potkaj\\xed svoji novou sousedku Penny, kter\\xe1 se pr\\xe1v\\u011b nast\\u011bhovala do bytu p\\u0159es chodbu, a po chvilce v\\xe1h\\xe1n\\xed ji pozvou k sob\\u011b na j\\xeddlo. Leonardovi Penny ihned u\\u010daruje a i p\\u0159es Sheldonovy nepat\\u0159i\\u010dn\\xe9 pozn\\xe1mky se ji sna\\u017e\\xed co nejl\\xe9pe poznat. Po chv\\xedli ji nab\\xeddne i mo\\u017enost vysprchovat se v jejich koupeln\\u011b, nebo\\u0165 jej\\xed sprcha je nefunk\\u010dn\\xed. Na sc\\xe9nu pot\\xe9 p\\u0159ich\\xe1z\\xed Howard a Rajesh, Sheldonovi a Leonardovi p\\u0159\\xe1tel\\xe9.', 
        u'title': u'01x01 - Teorie velkeho tresku - Pilot', 
        u'tvdb': u'80379', 
        u'mpaa': u'13', 
        u'writer': u'Chuck Lorre, Bill Prady', 
        u'cast': u'Johnny Galecki, Jim Parsons, Kaley Cuoco, Simon Helberg, Kunal Nayyar, Melissa Rauch, Mayim Bialik, Kevin Sussman, Carol Ann Susi, John Ross Bowie', 
        u'originaltitle_seo': u'01x01-pilot-sk', 
        u'params': {
            u'play': {
                u'ident': u'Rp6ba5Qo2w'}, 
            u'cp': u'webshare.cz'}, 
        u'fname': u'Big.Bang.Theory.S01E01.DVDrip.XviD.SK.avi', 
        u'season': u'01', 
        u'type': u'video', 
        u'aired': u'2007-09-24', 
        u'ainfo': u', [MP3 ]', 
        u'poster': u'http://thetvdb.com/banners/posters/80379-43.jpg', 
        u'tvshowtitle': u'The Big Bang Theory', 
        u'provider': u'plugin.video.online-files', 
        u'originaltitle': u'The Big Bang Theory', 
        u'trakt': u'1409', 
        u'director': u'Mark Cendrowski, James Burrows, Ted Wass, Andrew D. Weyman, Joel Murray, Anthony Rich, Peter Chakos, Howard Murray, Gay Linvill, Nicole Lorre', 
        u'imdbnumber': u'tt0898266', 
        u'studio': u'Chuck Lorre Productions', 
        u'mvideo': {
            u'duration': u'1375.374000', 
            u'width': 624, 
            u'codec': u'XVID', 
            u'aspect': u'1.77', 
            u'height': 352}, 
        u'olang': u'SK', 
        u'bitrate': 
        u'1062561', 
        u'lang': u'SK', 
        u'dateadded': u'2017-08-22 15:44:08', 
        u'episode': u'01', 
        u'extension': u'..avi', 
        u'url': u'http://vip.4.dl.webshare.cz/7054/Rp6ba5Qo2w/524288000/eJwljssKwjAURP_lLlyV2yT0RaEIpa4KFa2vRTepxDYgTbl9oeK_G3UxixmGM_MCCTGEEXoceWjlC3BghJj7LBSC+TxwYLbWgQliL4oEs8HwC3qIR5qUA51FpLrBVHYNHlpl6IEl4xvGMTtlpHu8zDrDMkc5a4sn219UPbSSFF6flXvTd1W5+z6opb8zYqnctSIylByLvNiei5VJvq_oP_j+AIwYM2c./8fa00ba801def387f7e33d8397a7c254a5281eab/Big.Bang.Theory.S01E01.DVDrip.XviD.SK.avi', u'sbitrate': u'1.01 Mbit/s', u'banner': u'http://thetvdb.com/banners/graphical/80379-g28.jpg', u'headers': u'', u'trailer': u'https://video.csfd.cz/files/videos/video/159/199/159199129_ae52bd.mp4', 
        u'sorttitle': u'01x01-pilot-sk', 
        u'genre': u'Komedie / Romantick\\xfd', 
        u'sinfo': False}"]
        '''
        image = self.item['art'].get('poster', '')
        thumb = self.item['art'].get('thumb', '')
        clearartimage = self.item['art'].get('tvshow.clearart', '')
        landscapeimage = self.item['art'].get('tvshow.landscape', '')
        fanartimage = self.item['art'].get('fanart', '')
        overview = self.item['plot']
        tvshowtitle = self.item['tvshowtitle']
        name = self.item['title']
        playcount = 0  #self.item['playcount']

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

        try:
            playcountControl = self.getControl(3018)
            if playcountControl != None:
                playcountControl.setLabel(str(playcount))
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
