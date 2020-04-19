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
from datetime import timedelta


def getTrakt(url, post=None, output='content', method=None):
    try:
        use_ssl = sctop.getSettingAsBool('UseSSL')
        url = urlparse.urljoin(
            'http%s://api.trakt.tv' % ('s' if use_ssl else ''), url)

        headers = {'trakt-api-key': sctop.trCL, 'trakt-api-version': '2'}

        if getTraktCredentialsInfo() is False:
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
            info = None
        else:
            result, code, info = sctop.request(url,
                                               headers,
                                               "info",
                                               method=method)
        #util.debug("[SC] trakt gt result: %s %s" % (str(result), str(code)))
        if not (code == 401 or code == 405):
            if output == "content":
                return result
            else:
                return (result, code, info)

        oauth = 'http%s://api.trakt.tv/oauth/token' % ('s' if use_ssl else '')
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

        sctop.setSetting(setting='trakt.token', value=token)
        sctop.setSetting(setting='trakt.refresh', value=refresh)

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
        if getTraktCredentialsInfo() is True:
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
        user_code = (sctop.getString(30931) %
                     result['user_code']).encode('utf-8')
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
        util.debug("[SC] auth: %s %s %s" %
                   (str(user), str(token), str(refresh)))
        raise Exception("[SC] ERR koniec")
    except:
        util.debug("[SC] trakt ERROR: %s" % str(traceback.format_exc()))
        sctop.openSettings('0.0')


def getTraktCredentialsInfo():
    user = sctop.getSetting('trakt.user').strip()
    token = sctop.getSetting('trakt.token')
    refresh = sctop.getSetting('trakt.refresh')
    if user == '' or token == '' or refresh == '': return False
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


def getLists(user='me'):
    result = getTrakt('/users/%s/lists' % user)

    if not result:
        return []
    result = json.loads(result)

    items = []
    items_below = []
    if sctop.getSettingAsBool('trakt.watchlist') or user != 'me':
        items += [{
            'type': 'dir',
            'title': '[B]$30944[/B]',
            'action': 'traktShowList',
            'id': 'watchlist',
            'tl': 'watchlist',
            'tu': user
        }]

    items += [{
        'type': 'dir',
        'title': '[B]$30958[/B]',
        'action': 'traktHistory',
        'id': 'history',
        'tu': user
    }]
    #,
    #{
    #    'type': 'dir',
    #    'title': 'Nedokoncene',
    #    'url': 'cmd://Container.Update("%s")' % \
    #        (xbmcutil._create_plugin_url({'action':'traktShowList', 'id':'progress'}))
    #}

    if user == "me":
        if sctop.getSettingAsBool('trakt.following'):
            below = sctop.getSettingAsBool('trakt.following-below')
            (items_below if below else items).append({
                'action': 'traktFollowing',
                'title': '[B]$30963[/B]',
                'id': 'following',
                'type': 'dir'
            })

        for l, t in (('liked', '$30964'), ('popular', '$30965'), ('trending',
                                                                  '$30966')):
            if sctop.getSettingAsBool('trakt.%s' % l):
                (items_below if sctop.getSettingAsBool('trakt.%s-below' %
                                                       l) else items).append({
                                                           'action':
                                                           'traktSpecialLists',
                                                           'title':
                                                           '[B]%s[/B]' % t,
                                                           'id':
                                                           '%s_lists' % l,
                                                           'type':
                                                           'dir',
                                                           'page':
                                                           '1'
                                                       })

    lists = [{
        'action': 'traktShowList',
        'title': i['name'],
        'id': i['ids']['slug'],
        'type': 'dir',
        'tl': i['ids']['slug'],
        'tu': user,
        'list': 'user'
    } for i in result]

    items += lists

    return items + items_below


def getFollowing():
    following = (json.loads(getTrakt("/users/me/friends")),
                 json.loads(getTrakt("/users/me/following")))

    friends = [u['user']['ids']['slug'] for u in following[0]]
    items = []
    for key, users in enumerate(following):
        for i in sorted(users, key=lambda u: _getUserName(u['user']).lower()):
            if key == 1 and i['user']['ids']['slug'] in friends: continue
            items.append({
                'action':
                'traktWatchlist',
                'title':
                ("[B]%s[/B]" if key == 0 else "%s") % _getUserName(i['user']),
                'type':
                'dir',
                'tu':
                i['user']['ids']['slug']
            })

    return items


def getHistory(user='me'):
    items = [{
        'type': 'dir',
        'title': '$30959',
        'action': 'traktShowList',
        'id': 'rated_movies',
        'tl': 'rated_movies',
        'tu': user
    }, {
        'type': 'dir',
        'title': '$30960',
        'action': 'traktShowList',
        'id': 'rated_shows',
        'tl': 'rated_shows',
        'tu': user
    }, {
        'type': 'dir',
        'title': '$30961',
        'action': 'traktShowList',
        'id': 'watched_movies',
        'tl': 'watched_movies',
        'tu': user
    }, {
        'type': 'dir',
        'title': '$30962',
        'action': 'traktShowList',
        'id': 'watched_shows',
        'tl': 'watched_shows',
        'tu': user
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


def getList(slug, content=None, user='me'):
    content = content if content is not None else ''
    util.debug('[SC] getList slug: %s, content: %s, user: %s' %
               (slug, content, user))
    ratings = False
    if slug == 'watchlist':
        result = getTrakt('/users/%s/watchlist/%s' % (user, content))
    elif slug == 'progress':
        result = getTrakt('sync/playback/%s' % content)
    elif slug[0:5] == 'rated':
        result = getTrakt('/users/%s/ratings/%s/' % (user, slug[6:]))
        ratings = {}
    elif slug[0:7] == 'watched':
        result = getTrakt('/users/%s/history/%s/?limit=1000000' %
                          (user, slug[8:]))
        content = slug[8:-1]
    else:
        result = getTrakt('/users/%s/lists/%s/items/%s' %
                          (user, slug, content))

    result = json.loads(result)
    ids = []
    types = {'movie': 0, 'show': 3}
    content_type = 'movies'
    for i in result:
        item_type = i['type'] if 'type' in i else content
        if item_type == 'episode':
            item_type = 'show'
        if item_type not in types:
            continue
        if item_type == 'show':
            content_type = 'videos'

        if item_type in i and 'trakt' in i[item_type]['ids']:
            id = '%d,%d' % (types[item_type], i[item_type]['ids']['trakt'])
            if id not in ids:
                ids.append(id)
            if ratings != False and 'rating' in i:
                ratings[i[item_type]['ids']['trakt']] = i['rating']
        else:
            util.debug('[SC] trakt LIST: %s' % str(i))
    return (content_type, ids, ratings)


def getSpecialLists(slug, page=1):
    if slug == 'liked_lists':
        url = '/users/likes/lists?page=%s&limit=200'
    elif slug == 'popular_lists':
        url = '/lists/popular?page=%s&limit=200'
    elif slug == 'trending_lists':
        url = '/lists/trending?page=%s&limit=200'

    result, __, info = getTrakt(url % str(page), output='info')
    result = json.loads(result)

    items = [{
        'title': i['list']['name'],
        'type': 'dir',
        'action': 'traktShowList',
        'id': i['list']['ids']['slug'],
        'tu': i['list']['user']['ids']['slug'],
        'tl': i['list']['ids']['slug'],
        'list': slug[0:-6]
    } if 'user' in i['list'] else None for i in result]

    if (page != int(info.dict['x-pagination-page-count'])):
        items.append({
            'title': '$30982',
            'type': 'dir',
            'action': 'traktSpecialLists',
            'id': slug,
            'page': page + 1
        })
    return items


def manager(name, trakt, content):
    try:
        icon = sctop.infoLabel('ListItem.Icon')
        message = sctop.getString(30941).encode('utf-8')
        content = "movies" if content == 'movie' else "shows"
        post = {content: [{"ids": {"trakt": trakt}}]}
        trakt = int(trakt)
        relevant = sctop.getSettingAsBool('trakt.relevant_menu')

        items = []
        if sctop.getSettingAsBool('trakt.collections'):
            key = 'trakt.collection.%s.ids' % content
            if relevant:
                ids = _get_cached_ids(key, '/users/me/collection/%s' % content)

            if not relevant or trakt not in ids:
                items = [(sctop.getString(30934).encode('utf-8'),
                          '/sync/collection', key)]
            if not relevant or trakt in ids:
                items += [(sctop.getString(30935).encode('utf-8'),
                           '/sync/collection/remove', key)]

        if sctop.getSettingAsBool('trakt.watchlist'):
            key = 'trakt.watchlist.%s.ids' % content
            if relevant:
                ids = _get_cached_ids(key, '/users/me/watchlist/%s' % content)

            if not relevant or trakt not in ids:
                items += [(sctop.getString(30936).encode('utf-8'),
                           '/sync/watchlist', key)]
            if not relevant or trakt in ids:
                items += [(sctop.getString(30937).encode('utf-8'),
                           '/sync/watchlist/remove', key)]

        items += [(sctop.getString(30989), 'rating')]

        lists = sctop.cache.get('trakt.lists')
        if not relevant or not lists:
            result = getTrakt('/users/me/lists')
            lists = json.loads(result)
            sctop.cache.set('trakt.lists', lists)

        util.debug("[SC] string %s" % sctop.getString(30939))

        for lst in lists:
            key = 'trakt.lists.%s.%s.ids' % (lst['ids']['trakt'], content)
            if relevant:
                ids = _get_cached_ids(
                    key, '/users/me/lists/%s/items/%s' %
                    (lst['ids']['slug'], content))
            if not relevant or trakt not in ids:
                items.append(
                    ((sctop.getString(30939) % lst['name']).encode('utf-8'),
                     '/users/me/lists/%s/items' % lst['ids']['slug'], key))

            if not relevant or trakt in ids:
                items.append(
                    ((sctop.getString(30940) % lst['name']).encode('utf-8'),
                     '/users/me/lists/%s/items/remove' % lst['ids']['slug'],
                     key))

        items += [(sctop.getString(30938).encode('utf-8'),
                   '/users/me/lists/%s/items')]

        if relevant:
            items.append(
                (sctop.getString(30811).encode('utf-8'), 'clear_cache'))

        select = sctop.selectDialog([i[0] for i in items],
                                    sctop.getString(30941).encode('utf-8'))

        if select == -1:
            return
        elif items[select][1] == 'rating':
            ratings = [(sctop.getString(i + 30990).encode('utf-8'), i)
                       for i in range(10, -1, -1)]
            select = sctop.selectDialog([i[0] for i in ratings], str(name))
            url = "/sync/ratings/remove"
            if select == -1:
                return
            elif ratings[select][1] != 0:
                url = "/sync/ratings"
                post[content][0]['rating'] = ratings[select][1]
            try:
                result = getTrakt(url, post=post)
                result = json.loads(result)
            except:
                return sctop.infoDialog(sctop.getString(30941).encode('utf-8'),
                                        heading=str(name),
                                        sound=True,
                                        icon='ERROR')

            if 'added' in result:
                if result['added'][content]:
                    message = sctop.getString(30987).encode(
                        'utf-8') % ratings[select][1]
                else:
                    return

            if 'deleted' in result:
                if result['deleted'][content]:
                    message = sctop.getString(30988).encode('utf-8')
                else:
                    return

        elif items[select][1] == '/users/me/lists/%s/items':
            t = sctop.getString(30938).encode('utf-8')
            k = sctop.keyboard('', t)
            k.doModal()
            new = k.getText() if k.isConfirmed() else None
            if (new == None or new == ''): return
            result = getTrakt('/users/me/lists',
                              post={
                                  "name": new,
                                  "privacy": "private"
                              })
            sctop.cache.set('trakt.lists', None, expiration=timedelta())
            try:
                slug = json.loads(result)['ids']['slug']
            except:
                return sctop.infoDialog(sctop.getString(30941).encode('utf-8'),
                                        heading=str(name),
                                        sound=True,
                                        icon='ERROR')
            result = getTrakt(items[select][1] % slug, post=post)
        elif items[select][1] == 'clear_cache':
            ttl = timedelta()
            sctop.cache.set('trakt.lists', None, expiration=ttl)

            contents = ['shows', 'movies']
            for l in ['watchlist', 'collection']:
                for c in contents:
                    key = 'trakt.%s.%s.ids' % (l, c)
                    sctop.cache.set(key, None, expiration=ttl)

            result = getTrakt('/users/me/lists')
            lists = json.loads(result)
            for l in lists:
                for c in contents:
                    key = 'trakt.lists.%s.%s.ids' % (l['ids']['trakt'], c)
                    sctop.cache.set(key, None, expiration=ttl)

            message = sctop.getString(30812).encode('utf-8')
            name = sctop.getString(30941).encode('utf-8')
        else:
            result = getTrakt(items[select][1], post=post)
            key = items[select][2]
            if result and relevant:
                ids = sctop.cache.get(key)
                if type(ids) is list:
                    if items[select][1][-7:] == '/remove':
                        ids = [i for i in ids if i != trakt]
                    else:
                        ids.append(trakt)
                    sctop.cache.set(key, ids)

        icon = icon if not result == None else 'ERROR'

        sctop.infoDialog(message, heading=str(name), sound=True, icon=icon)
    except Exception as e:
        util.debug("[SC] trakt error: %s" % str(traceback.format_exc()))
        return


def listAppendToCustom(user, list_id):
    lists = json.loads(getTrakt('/users/me/lists'))
    lists = [(i['ids']['slug'], i['name'], i['ids']['trakt']) for i in lists]
    select = sctop.selectDialog([i[1] for i in lists],
                                sctop.getString(30968).encode("utf-8"))
    if select == -1: return

    dst_list = lists[select]
    dst_items = _getListItemsForImport(user, list_id)
    result, code, info = getTrakt('/users/me/lists/%s/items' % dst_list[0],
                                  post=dst_items,
                                  output="info")
    if code == 201:
        sctop.infoDialog("%s" % dst_list[1],
                         sctop.getString(30969).encode("utf-8"))
        for c in ['shows', 'movies']:
            sctop.cache.set('trakt.lists.%s.%s' % (dst_list[2], c),
                            None,
                            expiration=timedelta())
    else:
        util.debug('[SC] import to %s failed. %d, %s' %
                   (dst_list[0], code, result))


def listClone(user, list_id):
    src = json.loads(getTrakt('/users/%s/lists/%s' % (user, list_id)))
    dst = {
        'name': '%s (%s)' % (src['name'], _getUserName(src['user'])),
        'privacy': 'private',
        'display_numbers': False
    }

    if not sctop.yesnoDialog(
            sctop.getString(30970).encode("utf-8"), "[B]%s[/B]?" % dst['name'],
            ""):
        return False

    for key in ['description', 'sort_by', 'sort_how']:
        dst[key] = src[key]

    dst = json.loads(getTrakt('/users/me/lists', post=dst))
    dst_items = _getListItemsForImport(user, list_id)
    result, code, info = getTrakt('/users/me/lists/%s/items' %
                                  dst['ids']['slug'],
                                  post=dst_items,
                                  output="info")
    if code == 201:
        sctop.cache.set('trakt.lists', None, expiration=timedelta())
        sctop.infoDialog('%s' % dst['name'],
                         sctop.getString(30976).encode("utf-8"))
    else:
        util.debug('[SC] List %s/%s: %d, %s' % (user, list_id, code, result))


def listCustomRemove(title, list_id):
    if not sctop.yesnoDialog(
            sctop.getString(30972).encode("utf-8"), "[B]%s[/B]?" % title, ""):
        return False

    result, code, info = getTrakt('/users/me/lists/%s' % list_id,
                                  output="info",
                                  method="DELETE")

    if code == 204:
        sctop.cache.set('trakt.lists', None, expiration=timedelta())
        sctop.infoDialog("%s" % title, sctop.getString(30973).encode("utf-8"))
    else:
        util.debug("[SC] List remove: code %d" % code)


def listLike(title, user, list_id):
    result, code, info = getTrakt('/users/%s/lists/%s/like' % (user, list_id),
                                  post={},
                                  output="info")
    if code == 204:
        sctop.infoDialog("%s" % title, sctop.getString(30975).encode("utf-8"))
    else:
        util.debug("[SC] List like: %s %d" % result, code)


def listUnlike(title, user, list_id):
    result, code, info = getTrakt('/users/%s/lists/%s/like' % (user, list_id),
                                  output="info",
                                  method="DELETE")
    if code == 204:
        sctop.infoDialog("%s" % title, sctop.getString(30974).encode("utf-8"))
    else:
        util.debug("[SC] List unlike: %s %d" % result, code)


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
        if getTraktCredentialsInfo() is False: return
        indicators = getTrakt('/users/me/watched/movies')
        indicators = json.loads(indicators)
        indicators = [i['movie']['ids'] for i in indicators]
        indicators = [str(i['trakt']) for i in indicators if 'trakt' in i]
        return indicators
    except:
        pass


def syncTVShows():
    try:
        if getTraktCredentialsInfo() is False: return
        indicators = getTrakt('/users/me/watched/shows?extended=full')
        indicators = json.loads(indicators)
        indicators = [(i['show']['ids']['trakt'], i['show']['aired_episodes'],
                       sum([[(s['number'], e['number']) for e in s['episodes']]
                            for s in i['seasons']], [])) for i in indicators]
        indicators = [(str(i[0]), int(i[1]), i[2]) for i in indicators]
        return indicators
    except:
        pass


def syncSeason(imdb):
    try:
        if getTraktCredentialsInfo() is False: return
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


def _getListItemsForImport(user, list_id):
    items = json.loads(
        getTrakt('/users/%s/lists/%s/items/movies,shows' % (user, list_id)))
    result = {'movies': [], 'shows': []}
    for i in items:
        result['%ss' % i['type']].append(
            {'ids': {
                'trakt': i[i['type']]['ids']['trakt']
            }})
    return result


def _get_cached_ids(key, url):
    ids = sctop.cache.get(key)
    if type(ids) is not list:
        result = getTrakt(url)
        ids = [i[i['type']]['ids']['trakt'] for i in json.loads(result)]
        sctop.cache.set(key, ids)
    return ids


def _getUserName(user):
    return user['name'] if user['name'] else user['username']
