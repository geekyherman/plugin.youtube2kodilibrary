import re
import xbmcgui
import datetime
import time
import uuid
from resources.lib.variables import *
from resources.lib.helper_functions import c_download, __save, __logger, __print, __ask, __scrub_text, __yt_duration, \
    __clean_char
from resources.lib.menu import __folders, __search

MIN_MINUTES = int(addon.getSetting('minimum_minutes'))


def __create_channel(channel_id, media_type):
    if media_type not in CONFIG:
        CONFIG[media_type] = {}

    data = {}
    channel_url = "https://www.googleapis.com/youtube/v3/channels?part=brandingSettings,contentDetails," \
                  "contentOwnerDetails,id,localizations,snippet,statistics,status,topicDetails&id="\
                  + channel_id + "&key=" + addon.getSetting('API_key')
    reply = c_download(channel_url)

    if 'items' not in reply:
        __print(AddonString(30015))  # No Such channel
        return "no such channel"

    playlist_type = 'normal'
    if 'playlists' in media_type:
        custom_uuid = 'PL_' + uuid.uuid4().hex
        playlists = __get_playlists(channel_id)
        data_set = __select_playlists(playlists)
        if media_type == 'playlists':
            dialog = xbmcgui.Dialog()
            ret = dialog.yesno('Specify playlist type',
                               'Do you want to import chronologically (Normal) or using the playlist order? (Absolute)',
                               'Normal', 'Absolute')
            if ret:
                playlist_type = 'abs'
        data['channel_id'] = custom_uuid
        data['title'] = __scrub_text(data_set['title'])
        pl_ids = data_set['items']
    else:
        data['channel_id'] = channel_id
        data['title'] = __scrub_text(reply['items'][0]['brandingSettings']['channel']['title'])
        pl_ids = reply['items'][0]['contentDetails']['relatedPlaylists']['uploads']
    if 'description' in reply['items'][0]['brandingSettings']['channel']:
        data['plot'] = __scrub_text(reply['items'][0]['brandingSettings']['channel']['description'])
    else:
        data['plot'] = data['title']

    if 'high' in reply['items'][0]['snippet']['thumbnails']:
        data['thumb'] = reply['items'][0]['snippet']['thumbnails']['high']['url']
    else:
        data['thumb'] = reply['items'][0]['snippet']['thumbnails']['default']['url']

    data['aired'] = reply['items'][0]['snippet']['publishedAt']
    data['banner'] = data['thumb']
    data['fanart'] = data['thumb']

    if data['channel_id'] not in CONFIG[media_type]:
        CONFIG[media_type][data['channel_id']] = {}

    CONFIG[media_type][data['channel_id']]['channel_name'] = data['title']
    CONFIG[media_type][data['channel_id']]['branding'] = {}
    CONFIG[media_type][data['channel_id']]['branding']['thumbnail'] = data['thumb']
    CONFIG[media_type][data['channel_id']]['branding']['fanart'] = data['fanart']
    CONFIG[media_type][data['channel_id']]['branding']['banner'] = data['banner']
    CONFIG[media_type][data['channel_id']]['branding']['description'] = data['plot']
    CONFIG[media_type][data['channel_id']]['playlist_id'] = pl_ids

    if media_type == 'playlists':
        CONFIG[media_type][data['channel_id']]['original_channel_id'] = channel_id
        CONFIG[media_type][data['channel_id']]['playlist_type'] = playlist_type

    if media_type == 'movies' or media_type == 'movies_playlists':
        xbmcvfs.mkdirs(MOVIES + '\\' + data['channel_id'])
        CONFIG[media_type][data['channel_id']]['channel_type'] = 'movies'
    else:
        xbmcvfs.mkdirs(CHANNELS + '\\' + data['channel_id'])
        CONFIG[media_type][data['channel_id']]['channel_type'] = 'series'
        output = u"""
<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n
    <tvshow>
            <title>{title}</title>
            <showtitle>{title}</showtitle>
            <plot>{plot}</plot>
            <genre>None</genre>
            <premiered>{aired}</premiered>
            <aired>{aired}</aired>
            <studio>{title}</studio>
            <thumb>{thumb}</thumb>
            <thumb aspect="poster">{fanart}</thumb>
            <thumb aspect="banner">{banner}</thumb>
            <fanart>
                    <thumb>{fanart}</thumb>
            </fanart>
            <tag>Youtube</tag>
    </tvshow>
    """.format(**data)
        tvshow_file = CHANNELS + '\\' + data['channel_id'] + '\\' + 'tvshow.nfo'
        if PY_V >= 3:
            with xbmcvfs.File(tvshow_file, 'w') as f:           # Python 3
                f.write(output)
        else:
            f = xbmcvfs.File(tvshow_file, 'w')                  # Python 2
            f.write(bytearray(output.encode('utf-8')))
            f.close()
    __save()
    PARSER['update_type'] = 'add'
    PARSER['refresh_type'] = 'single'
    __parse_videos(pl_ids, data['channel_id'], media_type)
    if addon.getSetting('refresh_after_add') == 'true' and HIDE['progress'] is False:
        if CONFIG[media_type][data['channel_id']]['channel_type'] == 'series':
            xbmc.executebuiltin("UpdateLibrary(video,"+CHANNELS+")")
        else:
            xbmc.executebuiltin("UpdateLibrary(video,"+MOVIES+")")


def __parse_videos(pl_ids, channel_id, media_type):
    if isinstance(pl_ids, str):
        pl_ids = [pl_ids]
    channel_name = CONFIG[media_type][channel_id]['channel_name']
    if 'disable_update' in CONFIG[media_type][channel_id]:
        __logger(channel_name + ": Updates not enabled")
        return
    VIDEOS.clear()
    VIDEO_DURATION.clear()
    result = __populate_local_index(media_type, channel_id)
    local_index = result[0]
    local_index_file = result[1]
    message = channel_name
    if PARSER['refresh_type'] == 'single':
        if media_type == 'channels' or media_type == 'playlists':
            PARSER['total_steps'] = len(CONFIG['channels']) + len(CONFIG['playlists'])
        elif media_type == 'movies' or media_type == 'movies_playlists':
            PARSER['total_steps'] = len(CONFIG['movies']) + len(CONFIG['movies_playlists'])

    for enum, p in enumerate(pl_ids):
        url = "https://www.googleapis.com/youtube/v3/playlistItems?part=snippet&maxResults=50&playlistId=" \
              + p + "&key=" + addon.getSetting('API_key')
        __logger(url)
        reply = c_download(url)
        if not __mark_extinct_channel(reply, media_type, channel_id):
            try:
                last_video_id = CONFIG[media_type][channel_id]['last_video']['video_id']
            except KeyError:
                last_video_id = ''
                __logger('no previous scan found')
            if HIDE['progress'] is False:
                heading = AddonString(30016)  # "Downloading channel info... "
                if len(pl_ids) > 1:
                    message = channel_name + ':  Playlist: ' + str(enum+1) + '/' + str(len(pl_ids))
                PDIALOG.create(heading, message)
            isExit = False
            while True:
                vid = []
                for item in reply['items']:
                    if HIDE['progress'] is False and PDIALOG.iscanceled():
                        return
                    item_vid = item['snippet']['resourceId']['videoId']
                    if 'playlist' in media_type:
                        item['snippet']['channelId'] = channel_id
                        if item_vid in INDEX or item['snippet']['title'] in ('Private video', 'Deleted video'):
                            continue
                    else:
                        if item_vid in INDEX or item_vid == last_video_id:
                            isExit = True
                            break
                    VIDEOS.append(item)
                    vid.append(item['snippet']['resourceId']['videoId'])
                    INDEX.append(item['snippet']['resourceId']['videoId'])
                    local_index.append(item['snippet']['resourceId']['videoId'])
                if len(vid) > 0:
                    __get_video_details(vid, False, media_type)
                if 'nextPageToken' not in reply or isExit:
                    break
                page_token = reply['nextPageToken']
                url = "https://www.googleapis.com/youtube/v3/playlistItems?part=snippet&maxResults=50&playlistId=" \
                      + p + "&pageToken=" + page_token + "&key=" + addon.getSetting('API_key')
                reply = c_download(url)
    if len(VIDEOS) > 0:
        __save(data=local_index, file=local_index_file)
        if media_type == 'channels' or media_type == 'playlists':
            __render_series(media_type, channel_name)
        elif media_type == 'movies' or media_type == 'movies_playlists':
            __render_movies(media_type, channel_name)
    else:
        PARSER['steps'] += 1
        if HIDE['progress'] is False:
            PARSER['percent'] = int(100 * PARSER['steps'] / PARSER['total_steps'])
            PDIALOG.update(PARSER['percent'], message)


def __render_series(media_type, channel_name):
    playlist_type = 'normal'
    channelId = VIDEOS[0]['snippet']['channelId']
    if media_type == 'playlists' and 'playlist_type' in CONFIG['playlists'][channelId]:
        playlist_type = CONFIG['playlists'][channelId]['playlist_type']

    if 'last_video' in CONFIG[media_type][channelId]:
        year = int(CONFIG[media_type][channelId]['last_video']['season'])
        episode = int(CONFIG[media_type][channelId]['last_video']['episode'])
        latest_aired = int(CONFIG[media_type][channelId]['last_video']['aired'])
        last_video_id = CONFIG[media_type][channelId]['last_video']['video_id']
    else:
        year = 0
        episode = 0

    for item in VIDEOS:
        item['snippet']['publishedAt'] = PUBLISHED_AT[item['snippet']['resourceId']['videoId']]

    sorted_videos = sorted(VIDEOS, key=lambda i: i["snippet"]["publishedAt"], reverse=False)
    if playlist_type == 'abs':
        sorted_videos = VIDEOS

    for enum, item in enumerate(sorted_videos):
        PARSER['steps'] += 1
        video_id = item['snippet']['resourceId']['videoId']
        aired = item['snippet']['publishedAt'].split('T')[0]
        ttime = item['snippet']['publishedAt'].split('T')[1]
        aired_datetime = datetime.datetime(int(aired.split('-')[0]), int(aired.split('-')[1]), int(aired.split('-')[2]),
                                           int(ttime.split(':')[0]), int(ttime.split(':')[1]), 0, 0)
        aired_timestamp = int((aired_datetime - datetime.datetime(1970, 1, 1)).total_seconds())
        try:
            if latest_aired > aired_timestamp or last_video_id == video_id:
                continue
        except NameError:
            pass

        season = int(aired.split('-')[0])
        if playlist_type == 'abs':
            season = 1
        else:
            if year != season:
                year = season
                episode = 0
        episode += 1

        try:
            vd = VIDEO_DURATION[video_id]
        except KeyError:
            vd = 0

        data = {'video_id': video_id, 'aired': aired, 'season': season, 'episode': episode, 'video_duration': vd,
                'author': item['snippet']['channelTitle'], 'channelId': item['snippet']['channelId'],
                'title': __scrub_text(item['snippet']['title']),
                'plot': __scrub_text(item['snippet']['description'])}

        for res in ('maxres', 'high', 'standard', 'default'):
            if res in item['snippet']['thumbnails']:
                data['thumb'] = item['snippet']['thumbnails'][res]['url']
                break
        if not xbmcvfs.exists(CHANNELS + '\\' + data['channelId'] + '\\' + str(data['season'])):
            xbmcvfs.mkdirs(CHANNELS + '\\' + data['channelId'] + '\\' + str(data['season']))
        output = u"""<? xml version = \"1.0\" encoding = \"UTF-8\" standalone = \"yes\"?>
<episodedetails>
    <title>{title}</title>
    <season>{season}</season>
    <episode>{episode}</episode>
    <plot>{plot}</plot>
    <aired>{aired}</aired>
    <studio>{author}</studio>
    <credits>{author}</credits>
    <director>{author}</director>
    <thumb>{thumb}</thumb>
    <runtime>{video_duration}</runtime>
    <fileinfo>
        <streamdetails>
        <durationinseconds>{video_duration}</durationinseconds>
        </streamdetails>
    </fileinfo>
</episodedetails>
""".format(**data)
        file_location = CHANNELS + '\\' + data['channelId'] + '\\' + str(data['season']) + '\\s' + str(data['season']) \
                        + 'e' + str(data['episode'])
        write_file = file_location+'.nfo'
        if PY_V >= 3:
            with xbmcvfs.File(write_file, 'w') as f:
                f.write(output)
        else:
            f = xbmcvfs.File(write_file, 'w')
            f.write(bytearray(output.encode('utf-8')))
            f.close()
        write_file = file_location + '.strm'
        if PY_V >= 3:
            with xbmcvfs.File(write_file, 'w') as f:
                f.write(YOUTUBE_CLIENT + data['video_id'])
        else:
            f = xbmcvfs.File(write_file, 'w')              # Python 2
            f.write(bytearray(YOUTUBE_CLIENT + data['video_id'].encode('utf-8')))
            f.close()

        if HIDE['progress'] is False:
            if PY_V >= 3:
                message = channel_name + ':  Episodes: ' + str(enum+1) + '/' + str(len(VIDEOS)) + \
                          '\n' + data['title']
            else:
                message = channel_name + ':  Episodes: ' + str(enum+1) + '/' + str(len(VIDEOS))
            if PARSER['refresh_type'] == 'multi':
                PARSER['percent'] = int(100 * PARSER['steps'] / PARSER['total_steps'])
            else:
                PARSER['percent'] = int(100 * (enum+1) / len(VIDEOS))
            PDIALOG.update(PARSER['percent'], message)

        CONFIG[media_type][data['channelId']]['last_video'] = {'video_id': data['video_id'],
                                                               'aired': aired_timestamp,
                                                               'season': str(data['season']),
                                                               'episode': str(data['episode'])}
        __save()
        __save(data=INDEX, file=index_file)


def __render_movies(media_type, channel_name):
    movie_re = addon.getSetting('movie_re')
    channelId = VIDEOS[0]['snippet']['channelId']
    channelName = CONFIG[media_type][channelId]['channel_name']
    folder = MOVIES + '\\' + channelId
    if not xbmcvfs.exists(folder):
        xbmcvfs.mkdirs(folder)
    if media_type == 'movies':
        if 'last_video' in CONFIG[media_type][channelId]:
            latest_aired = int(CONFIG[media_type][channelId]['last_video']['aired'])
            last_video_id = CONFIG[media_type][channelId]['last_video']['video_id']

    for enum, item in enumerate(VIDEOS):
        PARSER['steps'] += 1
        video_id = item['snippet']['resourceId']['videoId']
        item['snippet']['publishedAt'] = PUBLISHED_AT[video_id]
        aired = item['snippet']['publishedAt'].split('T')[0]
        ttime = item['snippet']['publishedAt'].split('T')[1]
        aired_datetime = datetime.datetime(int(aired.split('-')[0]), int(aired.split('-')[1]), int(aired.split('-')[2]),
                                           int(ttime.split(':')[0]), int(ttime.split(':')[1]), 0, 0)
        aired_timestamp = int((aired_datetime - datetime.datetime(1970, 1, 1)).total_seconds())
        aired_year = item['snippet']['publishedAt'].split('-')[0]
        try:
            if latest_aired > aired_timestamp or last_video_id == video_id:
                continue
        except NameError:
            pass

        '''get year from title or plot'''
        year = ''
        year_from_plot = ''
        if re.search(r'.*(\b(19|20)\d{2}\b)', item['snippet']['title']) is None:
            try:
                year_from_plot = re.search(r'.*(\b[(](19|20)\d{2}[)]\b)', item['snippet']['description']).group(1)[1:-1]
            except AttributeError:
                try:
                    year_from_plot = re.search(r'.*(\b(19|20)\d{2}\b)', item['snippet']['description']).group(1)
                except AttributeError:
                    pass
            #   this checks that the year found in the description is at least two years older than the aired date.
            #   in which case the year will be omitted. this prevents incorrect years being pulled from the description.
            #   it's not perfect, but it is necessary.
            if year_from_plot != '':
                if int(aired_year) - int(year_from_plot) < 2:
                    year_from_plot = ''
        else:
            year = re.search(r'.*(\b(19|20)\d{2}\b)', item['snippet']['title']).group(1)

        '''scrub title'''
        try:
            title = EN_TITLE[video_id]
        except KeyError:
            title = item['snippet']['title']

        title = re.sub(r'\b' + channelName + r'\b', '', title, flags=re.IGNORECASE)
        title = __scrub_text(title)
        title = __clean_char(title, 'B')

        for c in ('|', '(', '['):
            title = title.split(c, 1)[0]

        title = re.sub(r'\b' + movie_re + r'\b', '', title, flags=re.IGNORECASE)
        title = __clean_char(title, 'B')
        title = __clean_char(title, 'E')

        if len(title) > 0:
            if year_from_plot:
                title = title + ' (' + str(year_from_plot) + ')'
            else:
                if re.search(r'.*(\b(19|20)\d{2}\b)', title) is None and year != '':
                    title = title + ' (' + str(year) + ')'

            filename = "".join(i for i in title if i not in "\/:*?<>|")
            file_location = folder + '\\' + filename
            write_file = file_location + '.strm'
            if PY_V >= 3:
                with xbmcvfs.File(write_file, 'w') as f:    # Python 3
                    f.write(YOUTUBE_CLIENT + video_id)
            else:
                f = xbmcvfs.File(write_file, 'w')           # Python 2
                f.write(bytearray(YOUTUBE_CLIENT + video_id.encode('utf-8')))
                f.close()

        if HIDE['progress'] is False:
            if PY_V >= 3:
                message = channel_name + ':  Movie: ' + str(enum+1) + '/' + str(len(VIDEOS)) + \
                          '\n' + title
            else:
                message = channel_name + ':  Movie: ' + str(enum+1) + '/' + str(len(VIDEOS))
            if PARSER['refresh_type'] == 'multi':
                PARSER['percent'] = int(100 * PARSER['steps'] / PARSER['total_steps'])
            else:
                PARSER['percent'] = int(100 * (enum+1) / len(VIDEOS))
            PDIALOG.update(PARSER['percent'], message)

        if media_type == 'movies':
            CONFIG[media_type][channelId]['last_video'] = {'video_id': video_id,
                                                           'aired': aired_timestamp}
        __save()
        __save(data=INDEX, file=index_file)


def __get_playlists(channel_id):
    playlist_dict = {}
    channel_url = 'https://www.googleapis.com/youtube/v3/playlists?part=contentDetails,id,snippet&maxResults=50' \
                  '&channelId=' + channel_id + "&key=" + addon.getSetting('API_key')
    while True:
        reply = c_download(channel_url)
        if len(playlist_dict) == 0:
            playlist_dict = reply
        else:
            playlist_dict['items'].extend(reply['items'])
        if 'nextPageToken' not in reply:
            break
        else:
            page_token = reply['nextPageToken']
            channel_url = 'https://www.googleapis.com/youtube/v3/playlists?part=contentDetails,id,snippet&' \
                          'maxResults=50&channelId=' + channel_id + "&pageToken=" + page_token + "&key="\
                          + addon.getSetting('API_key')
    return playlist_dict


def __select_playlists(a, c_id=[]):
    menuItems = []
    _preselect = []
    # __logger(a)
    if c_id:
        for idx, i in enumerate(a['items']):
            menuItems.append(i['snippet']['title'])
            if i['id'] in CONFIG['playlists'][c_id]['playlist_id']:
                _preselect.append(idx)
        dialog = xbmcgui.Dialog()
        # Choose playlists
        ret = dialog.multiselect(AddonString(30049), menuItems, preselect=_preselect)
        if ret:
            # __logger(ret)
            playlist_ids = []
            for x in ret:
                playlist_ids.append(a['items'][x]['id'])
            return playlist_ids
        else:
            sys.exit("Nothing chosen")
    else:
        for i in a['items']:
            menuItems.append(i['snippet']['title'])
        # __logger(a['items'])
        dialog = xbmcgui.Dialog()
        # Choose playlist
        ret = dialog.multiselect(AddonString(30049), menuItems)
        if ret:
            # __logger(ret)
            playlist_ids = []
            title_suggestion = a['items'][min(ret)]['snippet']['title']
            for x in ret:
                playlist_ids.append(a['items'][x]['id'])
            # __logger(playlist_ids)
            # Name of playlist
            playlist_title = __ask(title_suggestion, AddonString(30050))
            return_object = {'title': playlist_title, 'items': playlist_ids}
            return return_object
        else:
            sys.exit("Nothing chosen")


def __mark_extinct_channel(reply, media_type, channel_id):
    if 'items' not in reply:
        __logger("no video in reply")
        cname = CONFIG[media_type][channel_id]['channel_name']
        __logger("adding '~' to " + cname)
        if cname[0] != '~':
            CONFIG[media_type][channel_id]['channel_name'] = '~' + cname
            __save()
        return True
    else:
        return False


def __populate_local_index(media_type, channel_id):
    if media_type == 'movies' or media_type == 'movies_playlists':
        local_index_file = MOVIES + '\\' + channel_id + '\\index.json'
    else:
        local_index_file = CHANNELS + '\\' + channel_id + '\\index.json'
    local_index = []
    if xbmcvfs.exists(local_index_file):
        if PY_V >= 3:
            with xbmcvfs.File(local_index_file) as f:   # PYTHON 3 v19+
                local_index = json.load(f)
        else:
            f = xbmcvfs.File(local_index_file)          # PYTHON 2 v18+
            local_index = json.loads(f.read())
            f.close()
    return [local_index, local_index_file]


def __get_video_details(array, vid_delete, media_type):
    x = [array[i:i + 50] for i in range(0, len(array), 50)]
    for stacks in x:
        get = ','.join(stacks)
        url = "https://www.googleapis.com/youtube/v3/videos?part=snippet,contentDetails,status,localizations&id="\
              + get + "&key=" + addon.getSetting('API_key')
        reply = c_download(url)
        for item in reply['items']:
            ignore = False
            duration = int(__yt_duration(item['contentDetails']['duration']))
            if media_type in ('movies', 'movies_playlists'):
                if duration < MIN_MINUTES:
                    ignore = True
                elif COUNTRY != '':
                    if item['status']['privacyStatus'] == 'private':
                        ignore = True
                    elif 'regionRestriction' in item['contentDetails']:
                        if 'blocked' in item['contentDetails']['regionRestriction']:
                            if COUNTRY in item['contentDetails']['regionRestriction']['blocked']:
                                ignore = True
                        elif 'allowed' in item['contentDetails']['regionRestriction']:
                            if item['contentDetails']['regionRestriction']['allowed'] == '':
                                ignore = True
                            elif COUNTRY not in item['contentDetails']['regionRestriction']['allowed']:
                                ignore = True
            if vid_delete and not ignore:
                for i, d in enumerate(VIDEOS_TO_DELETE):
                    if d['video_id'] == item['id']:
                        VIDEOS_TO_DELETE.pop(i)
                        break
            elif not vid_delete and ignore:
                for i, d in enumerate(VIDEOS):
                    if d['snippet']['resourceId']['videoId'] == item['id']:
                        VIDEOS.pop(i)
                        break
            else:
                PUBLISHED_AT[item['id']] = item['snippet']['publishedAt']
                VIDEO_DURATION[item['id']] = duration
                try:
                    EN_TITLE[item['id']] = item['localizations']['en']['title']
                except:
                    pass
