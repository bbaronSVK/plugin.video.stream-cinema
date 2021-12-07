from time import time
import xbmcvfs

from resources.lib.api.sc import Sc
from resources.lib.common.lists import List
from resources.lib.common.logger import debug
from resources.lib.common.storage import KodiDb
from resources.lib.constants import SC
from resources.lib.gui.item import SCNFO
from resources.lib.kodiutils import get_setting, make_legal_filename, mkdir, create_plugin_url, make_nfo_content, \
    exec_build_in, encode, decode


class AndroidTv(KodiDb):
    def __init__(self):
        KodiDb.__init__(self)
        self.list = List('android')
        self.last_run = 0

    def cleanup_library_path(self, path):
        sql = "" \
              "select " \
              "     'path' as typ, " \
              "     'idPath' as field, " \
              "      idPath as id " \
              "from " \
              "     path " \
              "where " \
              "     idparentpath in (" \
              "         select " \
              "             idpath " \
              "         from " \
              "             path " \
              "         where " \
              "             strpath=?" \
              "     ) " \
              "union all " \
              "select " \
              "     'files' as typ, " \
              "     'idFile' as field, " \
              "     idfile as id " \
              "from " \
              "     files " \
              "where " \
              "     idpath in (" \
              "         select " \
              "             idpath " \
              "         from " \
              "             path " \
              "         where " \
              "             idparentpath in (" \
              "                 select " \
              "                     idpath " \
              "                 from " \
              "                     path " \
              "                 where " \
              "                     strpath=?" \
              "             )" \
              "     ) " \
              "union all " \
              "select " \
              "     'movie' as typ, " \
              "     'idMovie' as field, " \
              "     idmovie as id " \
              "from " \
              "     movie " \
              "where " \
              "     idfile in (" \
              "         select " \
              "             idfile as id " \
              "         from " \
              "             files " \
              "         where " \
              "             idpath in (" \
              "                 select " \
              "                     idpath " \
              "                 from " \
              "                     path " \
              "                 where " \
              "                     idparentpath in (" \
              "                         select " \
              "                             idpath " \
              "                         from " \
              "                             path " \
              "                         where " \
              "                             strpath=?" \
              "                     )" \
              "             )" \
              "     )"
        res = self._db.execute(sql, path, path, path).fetchall()
        for i in res:
            debug('{}'.format(i))
            sql = 'delete from {} where {}=?'.format(i[0], i[1])
            debug('SQL: {}'.format(sql))
            self._db.execute(sql, i[2])
        return True

    def get(self, url):
        pass

    def run(self):
        path = get_setting('androidtv.path')
        cur = int(time())
        if path and self.last_run + 3600 < cur:
            self.last_run = time()
            items = self.list.get()
            for i in items:
                path_name = make_legal_filename('{}/{}/'.format(path, i.get(SC.ITEM_ID)))
                debug('android: {} {}'.format(i, path_name))
                mkdir(path_name)
                files = xbmcvfs.listdir(path_name)
                debug('files {}'.format(files))
                for f in files:
                    if len(f):
                        debug('file: {}'.format(f))
                        xbmcvfs.delete(f[0])
                res = Sc.get(i.get('url'))
                menu = res.get('menu', {})
                if len(menu):
                    debug('Mame menu polozky')
                    for pos, s in enumerate(menu):
                        if pos < 30:
                            url = create_plugin_url({
                                SC.ITEM_ID: '{}'.format(s.get('id', 0)),
                                SC.ITEM_URL: s.get('url', '')
                            })
                            base_name = '{}{:04d}'.format(path_name, pos)
                            fn = make_legal_filename('{}.strm'.format(base_name))
                            # debug('{} -> {} {} {}'.format(pos, fn, url, s.get(SC.ITEM_UIDS)))
                            fs = xbmcvfs.File(fn, 'w')
                            fs.write('{}'.format(url))
                            fs.close()
                            nfo = SCNFO(s)
                            # debug('NFO: {}'.format(encode(nfo.xml())))
                            fs = xbmcvfs.File(make_legal_filename('{}.nfo'.format(base_name)), 'w')
                            fs.write('{}'.format(encode(nfo.xml())))
                            fs.close()
                playlist_base = make_legal_filename('special://profile/playlists/video/')
                xml = '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>' \
                      '<smartplaylist type="movies">' \
                      ' <name>{}</name>' \
                      ' <match>all</match>' \
                      ' <rule field="path" operator="contains"><value>{}</value></rule>' \
                      '</smartplaylist>'
                xbmcvfs.mkdirs(playlist_base)
                filename = make_legal_filename('{}{}.xsp'.format(playlist_base, i.get(SC.ITEM_ID)))
                fs = xbmcvfs.File(filename, 'w')
                fs.write(xml.format(i.get(SC.ITEM_ID), path_name))
                fs.close()
            self.cleanup_library_path(path)
            exec_build_in('UpdateLibrary(video,{})'.format(path))
