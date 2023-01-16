import sqlite3
import xbmcgui
import xbmcplugin
import time
import datetime
import urllib
from resources.lib.helper_functions import __logger, __ask, c_download, table_select, convert, __get_token_reset
from resources.lib.variables import *

SEARCH_QUERY = []


def __search(query, search_type='tv'):
    del SEARCH_QUERY[:]
    channel_url = "https://www.googleapis.com/youtube/v3/search?type=channel&part=id,snippet&maxResults=10&q="\
                  + query + "&key=" + addon.getSetting('API_key')
    reply = c_download(channel_url)
    try:
        if 'error' in reply:
            e_reason = reply['error']['errors'][0]['reason']
            e_message = reply['error']['errors'][0]['message']
            if e_reason == 'quotaExceeded':
                e_message = "The request cannot be completed because you have exceeded your quota.Quota resets in :" \
                            "\n\n" + convert(__get_token_reset(), 'text')
            __print(e_message)
            raise SystemExit(" error")
    except NameError:
        pass    
    if 'items' not in reply:
        __print(30015)
        raise SystemExit(" error")

    for item in reply['items']:
        data = {'title': item['snippet']['title'], 'id': item['snippet']['channelId'],
                'description': item['snippet']['description'],
                'thumbnail': item['snippet']['thumbnails']['high']['url']}
        SEARCH_QUERY.append(data)
    __folders('search', search_type)


def __build_url(query):
    if PY_V >= 3:                       # Python 3
        return base_url + '?' + urllib.parse.urlencode(query)
    else:                               # Python 2
        return base_url + u'?' + urllib.urlencode(query)


def __folders(*args):
    if 'search' in args:
        smode = args[1]
        for items in SEARCH_QUERY:
            __logger(json.dumps(items))
            li = xbmcgui.ListItem(items['title'])
            info = {'plot': items['description']}
            li.setInfo('video', info)
            li.setArt({'thumb': items['thumbnail']})
            url = __build_url({'mode': 'AddItem_'+smode, 'foldername': items['id']})
            xbmcplugin.addDirectoryItem(handle=addon_handle, url=url, listitem=li, isFolder=True)
    elif 'Manage' in args:
        # Connect to the database
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        sql = "select id, title, description, thumb_url, disable_update from channel where media_type = 'series'" \
              "and removed = False order by title"
        cursor.execute(sql)
        result1 = cursor.fetchall()
        sql = "select id, title, channel_title, description, thumbnail_url, disable_update from playlist " \
              "where media_type = 'series' order by channel_title, title"
        cursor.execute(sql)
        result2 = cursor.fetchall()
        sql = "select c.id, c.title, c.description, c.thumb_url, c.disable_update, cnt, last_video " \
              "from channel c left join (" \
              "select channel_id, count(*) as cnt, strftime('%d-%m-%Y', max(v.published_at)) as last_video " \
              "from videos v " \
              "group by channel_id) v on c.id = v.channel_id " \
              "where c.media_type = 'movies' and c.removed = False " \
              "group by c.id, c.title, c.description, c.thumb_url, c.disable_update " \
              "order by c.title"
        cursor.execute(sql)
        result3 = cursor.fetchall()
        sql = "select id, title, channel_title, description, thumbnail_url, disable_update from playlist " \
              "where media_type = 'movies' order by channel_title, title"
        cursor.execute(sql)
        result4 = cursor.fetchall()
        conn.close()

        # TV SHOWS
        thumb = addon_resources+'/media/buttons/TV_show.png'
        li = xbmcgui.ListItem(AddonString(30043)+':')
        li.setArt({'thumb': thumb})
        xbmcplugin.addDirectoryItem(handle=addon_handle, url='', listitem=li, isFolder=False)
        for items in result1:
            title = items[1]
            plot = items[2] or ''
            thumb = items[3] or addon_resources+'/media/youtube_logo.jpg'
            disable_update = items[4]
            if disable_update == 'USER':
                li = xbmcgui.ListItem('[COLOR khaki]' + title + '[/COLOR]')
            elif disable_update == 'AUTO':
                li = xbmcgui.ListItem('[COLOR crimson]' + title + '[/COLOR]')
            else:
                li = xbmcgui.ListItem(title)
            li.setInfo('video', plot)
            li.setArt({'thumb': thumb})
            url = __build_url({'mode': 'C_MENU', 'foldername': items[0]})
            xbmcplugin.addDirectoryItem(handle=addon_handle, url=url, listitem=li, isFolder=True)

        # TV PLAYLISTS
        thumb = addon_resources+'/media/buttons/TV_playlist.png'
        li = xbmcgui.ListItem(AddonString(30045)+':')
        li.setArt({'thumb': thumb})
        xbmcplugin.addDirectoryItem(handle=addon_handle, url='', listitem=li, isFolder=False)
        for items in result2:
            title = items[1]
            channel_title = items[2]
            plot = items[3] or ''
            thumb = items[4] or addon_resources+'/media/youtube_logo.jpg'
            disable_update = items[5]
            if disable_update == 'USER':
                li = xbmcgui.ListItem('[COLOR khaki]' + channel_title + ": " + title + '[/COLOR]')
            elif disable_update == 'AUTO':
                li = xbmcgui.ListItem('[COLOR crimson]' + channel_title + ": " + title + '[/COLOR]')
            else:
                li = xbmcgui.ListItem(channel_title + ": " + title)
            li.setInfo('video', plot)
            li.setArt({'thumb': thumb})
            url = __build_url({'mode': 'PLAYLIST_MENU', 'foldername': items[0]})
            xbmcplugin.addDirectoryItem(handle=addon_handle, url=url, listitem=li, isFolder=True)

        # MOVIES
        thumb = addon_resources+'/media/buttons/Movie.png'
        li = xbmcgui.ListItem(AddonString(30054)+':')
        li.setArt({'thumb': thumb})
        xbmcplugin.addDirectoryItem(handle=addon_handle, url='', listitem=li, isFolder=False)
        for items in result3:
            title = items[1]
            plot = items[2] or ''
            thumb = items[3] or addon_resources+'/media/youtube_logo.jpg'
            disable_update = items[4]
            cnt = 0
            if items[5]:
                cnt = items[5]
            last_video = 'never'
            if items[6]:
                last_video = items[6]
            if disable_update == 'USER':
                li = xbmcgui.ListItem('[COLOR khaki]' + title + '  (' + str(cnt) + ' videos up to: ' + last_video + ')[/COLOR]')
            elif disable_update == 'AUTO':
                li = xbmcgui.ListItem('[COLOR crimson]' + title + '  (' + str(cnt) + ' videos up to: ' + last_video + ')[/COLOR]')
            else:
                li = xbmcgui.ListItem(title + '  (' + str(cnt) + ' videos up to: ' + last_video + ')')
            li.setInfo('video', plot)
            li.setArt({'thumb': thumb})
            url = __build_url({'mode': 'M_MENU', 'foldername': items[0]})
            xbmcplugin.addDirectoryItem(handle=addon_handle, url=url, listitem=li, isFolder=True)

        # MOVIES PLAYLISTS
        thumb = addon_resources+'/media/buttons/Movie.png'
        li = xbmcgui.ListItem('Movies '+AddonString(30045)+':')
        li.setArt({'thumb': thumb})
        xbmcplugin.addDirectoryItem(handle=addon_handle, url='', listitem=li, isFolder=False)
        for items in result4:
            title = items[1]
            channel_title = items[2]
            plot = items[3] or ''
            thumb = items[4] or addon_resources+'/media/youtube_logo.jpg'
            disable_update = items[5]
            if disable_update == 'USER':
                li = xbmcgui.ListItem('[COLOR khaki]' + channel_title + ": " + title + '[/COLOR]')
            elif disable_update == 'AUTO':
                li = xbmcgui.ListItem('[COLOR crimson]' + channel_title + ": " + title + '[/COLOR]')
            else:
                li = xbmcgui.ListItem(channel_title + ": " + title)
            li.setInfo('video', plot)
            li.setArt({'thumb': thumb})
            url = __build_url({'mode': 'M_PLAYLIST_MENU', 'foldername': items[0]})
            xbmcplugin.addDirectoryItem(handle=addon_handle, url=url, listitem=li, isFolder=True)
    elif 'menu' in args:
        # ADD CHANNEL [as a tv show]
        thumb = addon_resources+'/media/buttons/Add_TV_show.png'
        li = xbmcgui.ListItem(AddonString(30052)+AddonString(30028) + ' ['+AddonString(30040) + ']')
        li.setArt({'thumb': thumb})
        url = __build_url({'mode': 'ManageItem', 'foldername': 'Add_Channel_tv' })
        xbmcplugin.addDirectoryItem(handle=addon_handle, url=url, listitem=li, isFolder=True)
        # ADD PLAYLIST[as a tv show]
        thumb = addon_resources+'/media/buttons/Add_TV_show.png'
        li = xbmcgui.ListItem(AddonString(30052) + AddonString(30051) + '['+AddonString(30040) + ']')
        li.setArt({'thumb': thumb})
        url = __build_url({'mode': 'ManageItem', 'foldername': 'Add_Channel_tv_playlist' })
        xbmcplugin.addDirectoryItem(handle=addon_handle, url=url, listitem=li, isFolder=True)
        # ADD CHANNEL[as movies]
        thumb = addon_resources + '/media/buttons/Add_movies.png'
        li = xbmcgui.ListItem(AddonString(30052) + AddonString(30028) + ' [' + AddonString(30053) + ']')
        li.setArt({'thumb': thumb})
        url = __build_url({'mode': 'ManageItem', 'foldername': 'Add_Channel_movies'})
        xbmcplugin.addDirectoryItem(handle=addon_handle, url=url, listitem=li, isFolder=True)
        # ADD PLAYLIST[as movies]
        thumb = addon_resources + '/media/buttons/Add_movies.png'
        li = xbmcgui.ListItem(AddonString(30052) + AddonString(30051) + '[' + AddonString(30053) + ']')
        li.setArt({'thumb': thumb})
        url = __build_url({'mode': 'ManageItem', 'foldername': 'Add_Channel_movies_playlist'})
        xbmcplugin.addDirectoryItem(handle=addon_handle, url=url, listitem=li, isFolder=True)
        # Manage
        thumb = addon_resources+'/media/buttons/Manage.png'
        li = xbmcgui.ListItem(AddonString(30029))
        li.setArt({'thumb': thumb})
        url = __build_url({'mode': 'ManageItem', 'foldername': 'Manage'})
        xbmcplugin.addDirectoryItem(handle=addon_handle, url=url, listitem=li, isFolder=True)
        # REFRESH CHANNELS
        thumb = addon_resources+'/media/buttons/Refresh_All.png'
        li = xbmcgui.ListItem(AddonString(30031))
        li.setArt({'thumb': thumb})
        url = __build_url({'mode': 'ManageItem', 'foldername': 'Refresh'})
        xbmcplugin.addDirectoryItem(handle=addon_handle, url=url, listitem=li, isFolder=True)
        # DISCOVER MOVIES
        thumb = addon_resources+'/media/buttons/discover.png'
        li = xbmcgui.ListItem("Discover Movies")
        li.setArt({'thumb': thumb})
        url = __build_url({'mode': 'ManageItem', 'foldername': 'Discover'})
        xbmcplugin.addDirectoryItem(handle=addon_handle, url=url, listitem=li, isFolder=True)
        # ADDON SETTINGS
        thumb = addon_resources+'/media/buttons/Settings.png'
        li = xbmcgui.ListItem('Addon Settings')
        li.setArt({'thumb': thumb})
        url = __build_url({'mode': 'OpenSettings', 'foldername': ' '})
        xbmcplugin.addDirectoryItem(handle=addon_handle, url=url, listitem=li, isFolder=True)
        # ADDON INFO (Next update)
        if addon.getSetting('auto_refresh') == 'true':
            now = int(time.time())
            # Connect to the database
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            title = ''
            for cat in ('series', 'movies'):
                # Retrieve last updates from database
                sql = f"select {cat} from last_update"
                cursor.execute(sql)
                # Fetch the rows and extract the values from the tuple
                row = cursor.fetchone()
                last_scan = row
                countdown = last_scan[0] + int(xbmcaddon.Addon().getSetting(cat + '_update_interval'))*3600
                title += cat.upper()[:5] + ': ' + convert(countdown - now) + ' | '
                li = xbmcgui.ListItem(title[:-3], 'text')
        else:
            li = xbmcgui.ListItem('Automatic refresh disabled in settings', 'text')
        thumb = addon_resources+'/media/buttons/Update.png'
        li.setArt({'thumb': thumb})
        url = __build_url({'mode': 'OpenSettings', 'foldername': ' '})
        xbmcplugin.addDirectoryItem(handle=addon_handle, url=url, listitem=li, isFolder=False)
    xbmcplugin.endOfDirectory(addon_handle)
