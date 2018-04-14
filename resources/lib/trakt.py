# -*- coding: UTF-8 -*-
# /*
# *      Copyright (C) 2017 bbaron
# *
# *
# *  This Program is free software; you can redistribute it and/or modify
# *  it under the terms of the GNU General Public License as published by
# *  the Free Software Foundation; either version 2, or (at your option)
# *  any later version.
# *
# *  This Program is distributed in the hope that it will be useful,
# *  but WITHOUT ANY WARRANTY; without even the implied warranty of
# *  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# *  GNU General Public License for more details.
# *
# *  You should have received a copy of the GNU General Public License
# *  along with this program; see the file COPYING.  If not, write to
# *  the Free Software Foundation, 675 Mass Ave, Cambridge, MA 02139, USA.
# *  http://www.gnu.org/copyleft/gpl.html
# *
# */

import json
import re
import sctop
import traceback
import urlparse
import util
import xbmcutil


def getTrakt(url, post=None):
    try:
        url = urlparse.urljoin('http://api.trakt.tv', url)

        headers = {'trakt-api-key': sctop.trCL, 'trakt-api-version': '2'}

        if getTraktCredentialsInfo() == False:
            util.debug("[SC] gt 1 data: %s %s" % (str(url), str(post)))
            if post is not None:
                result = util.post_json(url, post, headers)
            else:
                result = util.request(url, headers)
            util.debug("[SC] gt 1 result: %s" % str(result))
            return result

        headers['Authorization'] = 'Bearer %s' % sctop.getSetting(
            'trakt.token')
        #util.debug('[SC] token %s' % sctop.getSetting('trakt.token'))

        if post is not None:
            result, code = sctop.post_json(url, post, headers, "extend")
        else:
            result, code = sctop.request(url, headers, "extend")
        #util.debug("[SC] trakt gt result: %s %s" % (str(result), str(code)))
        if not (code == 401 or code == 405): return result

        oauth = 'http://api.trakt.tv/oauth/token'
        opost = {
            'client_id': sctop.trCL,
            'client_secret': sctop.trSC,
            'redirect_uri': 'urn:ietf:wg:oauth:2.0:oob',
            'grant_type': 'refresh_token',
            'refresh_token': sctop.getSetting('trakt.refresh')
        }

        result, code = sctop.post_json(oauth, opost, headers, "extend")
        if code == 401:
            authTrakt()
            result, code = sctop.post_json(oauth, opost, headers, "extend")
        result = json.loads(result)

        token, refresh = result['access_token'], result['refresh_token']

        sctop.setSetting(id='trakt.token', value=token)
        sctop.setSetting(id='trakt.refresh', value=refresh)

        headers['Authorization'] = 'Bearer %s' % token

        util.debug('[SC] token: %s' % token)

        result = sctop.post_json(url, post, headers)
        return result
    except Exception as e:
        util.error(e)
        pass


def authTrakt():
    util.debug("[SC] trakt authTrakt 1")
    try:
        if getTraktCredentialsInfo() == True:
            util.debug("[SC] trakt at 2")
            if sctop.yesnoDialog(
                    sctop.getString(30932).encode('utf-8'),
                    sctop.getString(30933).encode('utf-8'), '', 'Trakt'):
                util.debug("[SC] trakt at 3")
                sctop.setSetting('trakt.user', value='')
                sctop.setSetting('trakt.token', value='')
                sctop.setSetting('trakt.refresh', value='')
            raise Exception("[SC] ERR dialog")

        util.debug("[SC] trakt at 4")
        result = getTrakt('/oauth/device/code', {'client_id': sctop.trCL})
        util.debug("[SC] trakt at 5: %s" % str(result))
        result = json.loads(result)
        util.debug("[SC] trakt at 6: %s" % str(result))
        verification_url = (sctop.getString(30930) %
                            result['verification_url']).encode('utf-8')
        user_code = (
            sctop.getString(30931) % result['user_code']).encode('utf-8')
        expires_in = int(result['expires_in'])
        device_code = result['device_code']
        interval = result['interval']

        progressDialog = sctop.progressDialog
        progressDialog.create('Trakt', verification_url, user_code)

        for i in range(0, expires_in):
            try:
                if progressDialog.iscanceled(): break
                sctop.sleep(500)
                if not float(i) % interval == 0: raise Exception()
                r = getTrakt(
                    '/oauth/device/token', {
                        'client_id': sctop.trCL,
                        'client_secret': sctop.trSC,
                        'code': device_code
                    })
                r = json.loads(r)
                if 'access_token' in r: break
            except:
                pass

        try:
            progressDialog.close()
        except:
            pass

        token, refresh = r['access_token'], r['refresh_token']
        util.debug("[SC] token: %s refresh: %s" % (str(token), str(refresh)))

        headers = {
            'trakt-api-key': sctop.trCL,
            'trakt-api-version': '2',
            'Authorization': 'Bearer %s' % token
        }

        result = util.request('http://api-v2launch.trakt.tv/users/me', headers)
        result = json.loads(result)

        user = result['username']

        sctop.setSetting('trakt.user', value=user)
        sctop.setSetting('trakt.token', value=token)
        sctop.setSetting('trakt.refresh', value=refresh)
        util.debug("[SC] auth: %s %s %s" % (str(user), str(token),
                                            str(refresh)))
        raise Exception("[SC] ERR koniec")
    except:
        util.debug("[SC] trakt ERROR: %s" % str(traceback.format_exc()))
        sctop.openSettings('0.0')


def getTraktCredentialsInfo():
    user = sctop.getSetting('trakt.user').strip()
    token = sctop.getSetting('trakt.token')
    refresh = sctop.getSetting('trakt.refresh')
    if (user == '' or token == '' or refresh == ''): return False
    return True


def getTraktAddonMovieInfo():
    try:
        try:
            scrobble = sctop.addon('script.trakt').getSetting('scrobble_movie')
        except:
            scrobble = ''
        try:
            ExcludeHTTP = sctop.addon('script.trakt').getSetting('ExcludeHTTP')
        except:
            ExcludeHTTP = ''
        try:
            authorization = sctop.addon('script.trakt').getSetting(
                'authorization')
        except:
            authorization = ''
        if scrobble == 'true' and ExcludeHTTP == 'false' and not authorization == '':
            return True
        else:
            return False
    except:
        pass
    return False


def getTraktAddonEpisodeInfo():
    try:
        scrobble = sctop.addon('script.trakt').getSetting('scrobble_episode')
    except:
        scrobble = ''
    try:
        ExcludeHTTP = sctop.addon('script.trakt').getSetting('ExcludeHTTP')
    except:
        ExcludeHTTP = ''
    try:
        authorization = sctop.addon('script.trakt').getSetting('authorization')
    except:
        authorization = ''
    if scrobble == 'true' and ExcludeHTTP == 'false' and not authorization == '':
        return True
    else:
        return False


def addTraktCollection(info):
    result = getTrakt('/sync/collection', post=info)
    try:
        ret = json.loads(result)
    except:
        ret = None
        pass
    return ret


def getLists():
    result = getTrakt('/users/me/lists')
    if not result:
        return []
    result = json.loads(result)

    items = [
        {
            'type': 'dir',
            'title': '[B]$30944[/B]',
            #'url': 'cmd://Container.Update("%s")' % \
            'action': 'traktShowList',
            'id': 'watchlist',
            'tl': 'watchlist'
        },
        {
            'type': 'dir',
            'title': '[B]$30958[/B]',
            'action': 'traktHistory',
            'id': 'history',
            'tl': 'history',
        }
        #,
        #{
        #    'type': 'dir',
        #    'title': 'Nedokoncene',
        #    'url': 'cmd://Container.Update("%s")' % \
        #        (xbmcutil._create_plugin_url({'action':'traktShowList', 'id':'progress'}))
        #}
    ]
    lists = [{
        'action': 'traktShowList',
        'title': i['name'],
        'id': i['ids']['slug'],
        'type': 'dir',
        'tl': i['ids']['slug']
    } for i in result]
    items += lists
    return items


def getHistory():

    items = [{
        'type': 'dir',
        'title': '$30959',
        'action': 'traktShowList',
        'id': 'rated_movies',
        'tl': 'rated_movies',
    }, {
        'type': 'dir',
        'title': '$30960',
        'action': 'traktShowList',
        'id': 'rated_shows',
        'tl': 'rated_shows',
    }, {
        'type': 'dir',
        'title': '$30961',
        'action': 'traktShowList',
        'id': 'watched_movies',
        'tl': 'watched_movies'
    }, {
        'type': 'dir',
        'title': '$30962',
        'action': 'traktShowList',
        'id': 'watched_shows',
        'tl': 'watched_shows'
    }, '''
        {
            'type': 'dir',
            'title': '$30963',
            'action': 'traktShowList',
            'id': 'progress',
            'tl': 'progress',
            'content': 'movies'
        },
        {
            'type': 'dir',
            'title': '$30964',
            'action': 'traktShowList',
            'id': 'progress',
            'tl': 'progress',
            'content': 'episodes'
        }
        ''']
    return items


def getList(slug, content=None):
    content = content if content is not None else ''
    util.debug('[SC] getList slug: %s, content: %s' % (slug, content))
    if slug == 'watchlist':
        result = getTrakt('/users/me/watchlist/%s' % content)
    elif slug == 'progress':
        result = getTrakt('sync/playback/%s' % content)
    elif slug[0:5] == 'rated':
        result = getTrakt('/users/me/ratings/%s/' % slug[6:])
    elif slug[0:7] == 'watched':
        result = getTrakt('/users/me/watched/%s/' % slug[8:])
        content = slug[8:-1]
    else:
        result = getTrakt('/users/me/lists/%s/items/%s' % (slug, content))

    result = json.loads(result)
    ids = []
    for i in result:
        if 'type' in i and 'imdb' in i[i['type']]['ids']:
            ids.append(i[i['type']]['ids']['imdb'])
        elif content in i and 'imdb' in i[content]['ids']:
            ids.append(i[content]['ids']['imdb'])
        else:
            util.debug('[SC] trakt LIST: %s' % str(i))
    return ids


def manager(name, imdb, tvdb, content):
    try:
        icon = sctop.infoLabel('ListItem.Icon')
        post = {
            "movies": [{
                "ids": {
                    "imdb": imdb
                }
            }]
        } if content == 'movie' else {
            "shows": [{
                "ids": {
                    "tvdb": tvdb
                }
            }]
        }

        items = [(sctop.getString(30934).encode('utf-8'), '/sync/collection')]
        items += [(sctop.getString(30935).encode('utf-8'),
                   '/sync/collection/remove')]
        items += [(sctop.getString(30936).encode('utf-8'), '/sync/watchlist')]
        items += [(sctop.getString(30937).encode('utf-8'),
                   '/sync/watchlist/remove')]
        items += [(sctop.getString(30938).encode('utf-8'),
                   '/users/me/lists/%s/items')]

        result = getTrakt('/users/me/lists')
        result = json.loads(result)
        lists = [(i['name'], i['ids']['slug']) for i in result]
        lists = [lists[i // 2] for i in range(len(lists) * 2)]
        util.debug("[SC] string %s" % sctop.getString(30939))
        for i in range(0, len(lists), 2):
            lists[i] = ((sctop.getString(30939) % lists[i][0]).encode('utf-8'),
                        '/users/me/lists/%s/items' % lists[i][1])
        for i in range(1, len(lists), 2):
            lists[i] = ((sctop.getString(30940) % lists[i][0]).encode('utf-8'),
                        '/users/me/lists/%s/items/remove' % lists[i][1])
        items += lists

        select = sctop.selectDialog([i[0] for i in items],
                                    sctop.getString(30941).encode('utf-8'))

        if select == -1:
            return
        elif select == 4:
            t = sctop.getString(30938).encode('utf-8')
            k = sctop.keyboard('', t)
            k.doModal()
            new = k.getText() if k.isConfirmed() else None
            if (new == None or new == ''): return
            result = getTrakt(
                '/users/me/lists', post={
                    "name": new,
                    "privacy": "private"
                })

            try:
                slug = json.loads(result)['ids']['slug']
            except:
                return sctop.infoDialog(
                    sctop.getString(30941).encode('utf-8'),
                    heading=str(name),
                    sound=True,
                    icon='ERROR')
            result = getTrakt(items[select][1] % slug, post=post)
        else:
            result = getTrakt(items[select][1], post=post)

        icon = icon if not result == None else 'ERROR'

        sctop.infoDialog(
            sctop.getString(30941).encode('utf-8'),
            heading=str(name),
            sound=True,
            icon=icon)
    except Exception as e:
        util.debug("[SC] trakt error: %s" % str(traceback.format_exc()))
        return


def slug(name):
    name = name.strip()
    name = name.lower()
    name = re.sub('[^a-z0-9_]', '-', name)
    name = re.sub('--+', '-', name)
    return name


def getActivity():
    try:
        result = getTrakt('/sync/last_activities')
        i = json.loads(result)

        activity = []
        activity.append(i['movies']['collected_at'])
        activity.append(i['episodes']['collected_at'])
        activity.append(i['movies']['watchlisted_at'])
        activity.append(i['shows']['watchlisted_at'])
        activity.append(i['seasons']['watchlisted_at'])
        activity.append(i['episodes']['watchlisted_at'])
        activity.append(i['lists']['updated_at'])
        activity.append(i['lists']['liked_at'])
        activity = [int(sctop.iso_2_utc(i)) for i in activity]
        activity = sorted(activity, key=int)[-1]

        return activity
    except:
        pass


def getWatchedActivity():
    try:
        result = getTrakt('/sync/last_activities')
        i = json.loads(result)

        activity = []
        activity.append(i['movies']['watched_at'])
        activity.append(i['episodes']['watched_at'])
        activity = [int(sctop.iso_2_utc(i)) for i in activity]
        activity = sorted(activity, key=int)[-1]

        return activity
    except:
        pass


def syncMovies():
    try:
        if getTraktCredentialsInfo() == False: return
        indicators = getTrakt('/users/me/watched/movies')
        indicators = json.loads(indicators)
        indicators = [i['movie']['ids'] for i in indicators]
        indicators = [str(i['imdb']) for i in indicators if 'imdb' in i]
        return indicators
    except:
        pass


def syncTVShows():
    try:
        if getTraktCredentialsInfo() == False: return
        indicators = getTrakt('/users/me/watched/shows?extended=full')
        indicators = json.loads(indicators)
        indicators = [(i['show']['ids']['tvdb'], i['show']['aired_episodes'],
                       sum([[(s['number'], e['number']) for e in s['episodes']]
                            for s in i['seasons']], [])) for i in indicators]
        indicators = [(str(i[0]), int(i[1]), i[2]) for i in indicators]
        return indicators
    except:
        pass


def syncSeason(imdb):
    try:
        if getTraktCredentialsInfo() == False: return
        indicators = getTrakt(
            '/shows/%s/progress/watched?specials=false&hidden=false' % imdb)
        indicators = json.loads(indicators)['seasons']
        indicators = [(i['number'], [x['completed'] for x in i['episodes']])
                      for i in indicators]
        indicators = [
            '%01d' % int(i[0]) for i in indicators if not False in i[1]
        ]
        return indicators
    except:
        pass


def markMovieAsWatched(imdb):
    if not imdb.startswith('tt'): imdb = 'tt' + imdb
    return getTrakt('/sync/history', {"movies": [{"ids": {"imdb": imdb}}]})


def markMovieAsWatchedT(trakt):
    return getTrakt('/sync/history', {"movies": [{"ids": trakt}]})


def markMovieAsNotWatched(imdb):
    if not imdb.startswith('tt'): imdb = 'tt' + imdb
    return getTrakt('/sync/history/remove',
                    {"movies": [{
                        "ids": {
                            "imdb": imdb
                        }
                    }]})


def markTVShowAsWatched(tvdb):
    return getTrakt('/sync/history', {"shows": [{"ids": {"tvdb": tvdb}}]})


def markTVShowAsNotWatched(tvdb):
    return getTrakt('/sync/history/remove',
                    {"shows": [{
                        "ids": {
                            "tvdb": tvdb
                        }
                    }]})


def markEpisodeAsWatched(tvdb, season, episode):
    season, episode = int('%01d' % int(season)), int('%01d' % int(episode))
    return getTrakt(
        '/sync/history', {
            "shows": [{
                "seasons": [{
                    "episodes": [{
                        "number": episode
                    }],
                    "number": season
                }],
                "ids": {
                    "tvdb": tvdb
                }
            }]
        })


def markEpisodeAsWatchedT(trakt, season, episode):
    season, episode = int('%01d' % int(season)), int('%01d' % int(episode))
    return getTrakt(
        '/sync/history', {
            "shows": [{
                "seasons": [{
                    "episodes": [{
                        "number": episode
                    }],
                    "number": season
                }],
                "ids":
                trakt
            }]
        })


def markEpisodeAsNotWatched(tvdb, season, episode):
    season, episode = int('%01d' % int(season)), int('%01d' % int(episode))
    return getTrakt(
        '/sync/history/remove', {
            "shows": [{
                "seasons": [{
                    "episodes": [{
                        "number": episode
                    }],
                    "number": season
                }],
                "ids": {
                    "tvdb": tvdb
                }
            }]
        })


def getMovieTranslation(id, lang):
    url = '/movies/%s/translations/%s' % (id, lang)
    try:
        return json.loads(getTrakt(url))[0]['title'].encode('utf-8')
    except:
        pass


def getTVShowTranslation(id, lang):
    url = '/shows/%s/translations/%s' % (id, lang)
    try:
        return json.loads(getTrakt(url))[0]['title'].encode('utf-8')
    except:
        pass


def getMovieSummary(id):
    return getTrakt('/movies/%s' % id)


def getTVShowSummary(id):
    return getTrakt('/shows/%s' % id)


def getPlaybackProgress(id):
    return getTrakt('sync/playback/%s' % id)
