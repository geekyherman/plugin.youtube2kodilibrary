import re
import sqlite3
import string
import os
import datetime
import xbmcgui
import time
import uuid
import requests
from resources.lib.variables import *
from resources.lib.helper_functions import c_download, sqlite_get_csv_list, table_update, table_select, \
    remove_restricted_videos_and_files, delete_movie_strm, recursive_delete_dir, __logger, __ask
from resources.lib.menu import __folders, __search


class ChannelProcessor:
    def __init__(self, media_type=None, c_or_pl_id=None, channel_type=None, discovered=False, sort_by=None, title=''):
        self.media_type = media_type
        self.discovered = discovered
        self.sort_by = sort_by
        self.channel_type = channel_type
        self.c_or_pl_id = c_or_pl_id
        self.title = title

    def insert(self):
        if not self.c_or_pl_id or not self.channel_type or not self.media_type:
            #__logger(f"ChannelProcessor.insert() requires a c_or_pl_id, channel_type and a media_type")
            return

        playlist_id = None

        # If the channel_type is a channel then run the channels insert
        if self.channel_type == 'channel':
            skip = _table_channels_insert(self.c_or_pl_id, self.media_type, self.discovered)
            # If the language of the discovered channel doesn't match the language setting then don't process.
            if skip:
                return

            # Get the upload_playlist_id for the channel as that is what the videos are linked to.
            playlist_id = _get_uploads_playlist_from_channel(self.c_or_pl_id)

        # If the channel_type is a playlist then run the playlist insert
        if self.channel_type == 'playlist':
            playlist_id = self.c_or_pl_id
            _table_playlist_insert(playlist_id, self.media_type, self.sort_by)

        # Insert the corresponding playlist items
        if HIDE['progress'] is False:
            DP.update(50, f'Inserting playlist items....')
        _table_playlistItems_insert(playlist_id, self.media_type)

        # Insert the videos that are required from the playlist.
        if HIDE['progress'] is False:
            DP.update(75, f'Determining required videos....')
        _table_videos_insert(VIDEOS, self.media_type)

        # Update the video_custom records for a series to have season (year) and episode numbers.
        if self.media_type == 'series':
            _update_season_episode(self.media_type, self.channel_type, self.c_or_pl_id)

        # generate the kodi strm and nfo files.
        if HIDE['progress'] is False:
            DP.update(100, f'Creating files....')
        _create_kodi_media(self.media_type, self.c_or_pl_id)

    def refresh(self):
        if self.channel_type == 'channel':
            playlist_id = _get_uploads_playlist_from_channel(self.c_or_pl_id)
        else:
            playlist_id = self.c_or_pl_id
        if HIDE['progress'] is False:
            if PARSER['refresh_type'] == 'multi':
                PARSER['percent'] = int(100 * PARSER['steps'] / PARSER['total_steps'])
                DP.update(PARSER['percent'], f"{PARSER['steps']}/{PARSER['total_steps']}: {self.title}")
            else:
                DP.update(50, 'Inserting new playlist items....')
        _table_playlistItems_insert(playlist_id, self.media_type)
        if len(VIDEOS) > 0:
            if HIDE['progress'] is False:
                if PARSER['refresh_type'] == 'multi':
                    pass
                else:
                    DP.update(75, 'Determining required videos....')
            _table_videos_insert(VIDEOS, self.media_type)
        if self.media_type == 'series':
            _update_season_episode(self.media_type, self.channel_type, self.c_or_pl_id)
        if HIDE['progress'] is False:
            if PARSER['refresh_type'] == 'multi':
                pass
            else:
                DP.update(100, 'Creating files....')
        _create_kodi_media(self.media_type, playlist_id)

    def rebuild(self):
        self.delete()
        self.insert()

    def delete(self):
        # delete the files associated with the playlist
        if self.media_type == 'series':
            if self.channel_type == 'playlist':
                sql = f"select sort_by from playlist where id = '{self.c_or_pl_id}'"
                self.sort_by = sqlite_get_csv_list(sql)[0]
            del_dir = SERIES + '\\' + self.c_or_pl_id
            recursive_delete_dir(del_dir)
        if self.media_type == 'movies':
            # retrieve a list of video_ids from the channel to be deleted (excludes any present on other sources)
            sql = f"select pi.video_id from playlistItems pi where pi.{self.channel_type}_id = '{self.c_or_pl_id}' and "\
                  f"pi.video_id in (select video_id from playlistItems group by video_id having count(video_id) = 1)"
            del_list = sqlite_get_csv_list(sql)
            delete_movie_strm(del_list)

        # Connect to the database
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        # Delete rows from videos_custom where they are only applicable to the c_or_pl_id
        sql = f"delete from videos_custom where video_id in (" \
              f"select pi.video_id from playlistItems pi where pi.{self.channel_type}_id = '{self.c_or_pl_id}' and " \
              f"pi.video_id in (select video_id from playlistItems group by video_id having count(video_id) = 1)" \
              f")"
        cursor.execute(sql)

        # Delete rows from videos where they are only applicable to the c_or_pl_id
        sql = f"delete from videos where id in (" \
              f"select pi.video_id from playlistItems pi where pi.{self.channel_type}_id = '{self.c_or_pl_id}' and " \
              f"pi.video_id in (select video_id from playlistItems group by video_id having count(video_id) = 1)" \
              f")"
        cursor.execute(sql)

        # Delete rows from playlistItems where they are only applicable to the c_or_pl_id
        sql = f"delete from playlistItems where {self.channel_type}_id = '{self.c_or_pl_id}'"
        cursor.execute(sql)

        # Delete the channel
        if self.channel_type == 'channel':
            sql = f"delete from channel where id = '{self.c_or_pl_id}' and discovered = 0"
            cursor.execute(sql)
            sql = f"update channel set removed = 1 where id = '{self.c_or_pl_id}' and discovered = 1"
            cursor.execute(sql)
        elif self.channel_type == 'playlist':
            sql = f"delete from playlist where id = '{self.c_or_pl_id}'"
            cursor.execute(sql)

        # Commit the transaction and close the connection
        conn.commit()
        conn.close()


def create_channel(channel_id, media_type, channel_type):
    # retrieve channel info
    channel_url = "https://www.googleapis.com/youtube/v3/channels?part=brandingSettings,contentDetails," \
                  "contentOwnerDetails,id,localizations,snippet,statistics,status,topicDetails&id=" \
                  + channel_id + "&key=" + addon.getSetting('API_key')
    reply = c_download(channel_url)

    if 'items' not in reply:
        __print(AddonString(30015))  # No Such channel
        return "no such channel"

    if channel_type == 'channel':
        if HIDE['progress'] is False:
            DP.create('Adding channel....')
        cp = ChannelProcessor(media_type, channel_id, channel_type)
        cp.insert()
    elif channel_type == 'playlist':
        if HIDE['progress'] is False:
            DP.create('Adding playlist....')
        playlists = get_playlists(channel_id)
        data_set = select_playlists(playlists)
        playlists = data_set['items']
        sort_by = None
        for pl in playlists:
            if media_type == 'series':
                dialog = xbmcgui.Dialog()
                ret = dialog.yesno('Specify playlist type',
                                   'Do you want to import chronologically (Normal) or using the playlist order? (Absolute)',
                                   'Normal', 'Absolute')
                if ret:
                    sort_by = 'abs'
            cp = ChannelProcessor(media_type, pl, channel_type, sort_by=sort_by)
            cp.insert()
    else:
        __logger("create_channel: invalid channel_type")

    # disable while testing.
    # if addon.getSetting('refresh_after_add') == 'true' and HIDE['progress'] is False:
    #     if media_type == 'series':
    #         xbmc.executebuiltin("UpdateLibrary(video,"+SERIES+")")
    #     else:
    #         xbmc.executebuiltin("UpdateLibrary(video,"+MOVIES+")")


def get_playlists(channel_id):
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


def select_playlists(a):
    menuItems = []
    _preselect = []
    for i in a['items']:
        menuItems.append(i['snippet']['title'])
    dialog = xbmcgui.Dialog()
    # Choose playlist
    ret = dialog.multiselect(AddonString(30049), menuItems)
    if ret:
        # __logger(ret)
        playlist_ids = []
        for x in ret:
            playlist_ids.append(a['items'][x]['id'])
        # __logger(playlist_ids)
        # Name of playlist
        return_object = {'title': '', 'items': playlist_ids}
        return return_object
    else:
        sys.exit("Nothing chosen")


def _get_season_and_episode(src_playlist):
    # Connect to the database
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # select video_ids from the playlist
    cursor.execute(f"select season, episode from vwVideosSeries where src_playlist = '{src_playlist}'"
                   f"order by season desc, episode desc LIMIT 1")

    # Fetch the rows and extract the values from the tuple
    row = cursor.fetchone()
    season, episode = row

    # Close the connection to the database
    conn.close()

    return season, episode


def _get_uploads_playlist_from_channel(channel_id):
    # Connect to the database
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # select video_ids from the playlist
    cursor.execute("SELECT uploads_playlist_id FROM channel where id = '" + channel_id + "'")

    # Fetch the rows from the result
    row = cursor.fetchone()

    if not row:
        __logger("No uploads playlist was found. Exiting.")

    return row[0]


def _table_channels_insert(channel_id, media_type, discovered=False):
    # Make a request to the YouTube API
    channel_url = "https://www.googleapis.com/youtube/v3/channels?part=snippet,contentDetails,statistics,topicDetails," \
                  "status,brandingSettings,contentOwnerDetails,localizations&id=" + channel_id + "&key=" + addon.getSetting('API_key')
    response = requests.get(channel_url)

    # Get the JSON data from the response
    data = response.json()

    # Extract the channel data from the response
    channel = data["items"][0]

    # Extract the relevant information from the channel data
    id = channel.get("id", None)
    snippet = channel.get("snippet", None)
    title = snippet.get("title", None)
    description = snippet.get("description", None)
    custom_url = snippet.get("customUrl", None)
    published_at = snippet.get("publishedAt", None)
    country = snippet.get("country", None)
    default_language = snippet.get("defaultLanguage", None)
    __logger(title)

    thumb_url = None
    thumbnails = snippet.get("thumbnails", None)
    if thumbnails:
        for thumbnail in ('maxres', 'standard', 'high', 'medium', 'default'):
            if thumbnail in thumbnails:
                thumb_url = channel["snippet"]["thumbnails"][thumbnail]["url"]
                break

    uploads_playlist_id = None
    content_details = channel.get("contentDetails", None)
    if content_details:
        related_playlists = content_details.get("relatedPlaylists", None)
        if related_playlists:
            uploads_playlist_id = related_playlists.get("uploads", None)

    video_count = None
    statistics = channel.get("statistics", None)
    if statistics:
        video_count = statistics.get("videoCount", None)

    topic_ids = None
    topic_categories = None
    topic_details = channel.get("topicDetails", {})
    if topic_details:
        topic_ids = ",".join(topic_details.get("topicIds", []))
        topic_categories = ",".join(topic_details.get("topicCategories", []))

    privacy_status = None
    status = channel.get("status", None)
    if status:
        privacy_status = status.get("privacyStatus", None)

    keywords = None
    unsubscribed_trailer = None
    branding_settings = channel.get("brandingSettings", None)
    if branding_settings:
        channel_1 = branding_settings.get("channel", None)
        if channel_1:
            if not title:
                title = channel_1.get("title", None)
            if not description:
                description = channel_1.get("description", None)
            keywords = channel_1.get("keywords", None)
            unsubscribed_trailer = channel_1.get("unsubscribedTrailer", None)
            if not country:
                country = channel_1.get("country", None)

    # Connect to the database and insert channel
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO channel VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (id, title, description, custom_url, published_at, thumb_url, country, default_language,
             uploads_playlist_id, video_count, topic_ids, topic_categories, privacy_status, keywords,
             unsubscribed_trailer, media_type, None, discovered, 0)
        )
    except sqlite3.IntegrityError:
        __logger("Channel exists - bypassed")
        pass

    # Only create channel nfo files for series
    if media_type == 'series':
        try:
            _create_series_nfo_files(title, description, published_at, thumb_url, id)
        except:
            pass

    # Commit the changes and close the connection
    conn.commit()
    conn.close()

    skip = False
    if discovered:
        if default_language and default_language[:len(DISCOVERY_CHANNEL_LANGUAGE)] != DISCOVERY_CHANNEL_LANGUAGE:
            skip = True

    return skip


def _table_playlist_insert(playlist_id, media_type, sort_by=None):
    # Make a request to the YouTube API
    playlist_url = "https://www.googleapis.com/youtube/v3/playlists?part=snippet,status,contentDetails," \
                   "localizations&id=" + playlist_id + "&key=" + addon.getSetting('API_key')
    __logger(playlist_url)
    response = requests.get(playlist_url)

    # Get the JSON data from the response
    data = response.json()
    __logger(data)
    # Extract the channel data from the response
    playlist = data["items"][0]

    # Extract the relevant information from the channel data
    id = playlist.get("id", None)
    snippet = playlist.get("snippet", None)
    published_at = snippet.get("publishedAt", None)
    channel_id = snippet.get("channelId", None)
    title = scrub_text(snippet.get("title", None))
    description = scrub_text(snippet.get("description", None))
    channel_title = snippet.get("channelTitle", None)
    default_language = snippet.get("defaultLanguage", None)
    __logger(title)

    thumb_url = None
    thumb_width = None
    thumb_height = None
    thumbnails = snippet.get("thumbnails", None)
    if thumbnails:
        for thumbnail in ('maxres', 'standard', 'high', 'medium', 'default'):
            if thumbnail in thumbnails:
                thumb_url = playlist["snippet"]["thumbnails"][thumbnail]["url"]
                thumb_width = playlist["snippet"]["thumbnails"][thumbnail]["width"]
                thumb_height = playlist["snippet"]["thumbnails"][thumbnail]["height"]
                break

    local_title = None
    local_description = None
    localized = snippet.get("localized", {})
    if localized:
        local_title = scrub_text(localized.get("title", None))
        local_description = scrub_text(localized.get("description", None))

    privacy_status = None
    status = playlist.get("status", None)
    if status:
        privacy_status = status.get("privacyStatus", None)

    item_count = None
    content_details = playlist.get("contentDetails", None)
    if content_details:
        item_count = content_details.get("itemCount", None)

    # Connect to the database
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    try:
        cursor.execute(
            "INSERT INTO playlist VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (id, published_at, channel_id, title, description, channel_title, default_language,
             thumb_url, thumb_width, thumb_height, privacy_status, item_count, local_title, local_description,
             media_type, sort_by, None)
        )
    except sqlite3.IntegrityError:
        __logger("Playlist already exists. Skipping")
        pass

    try:
        _create_series_nfo_files(title, description, published_at, thumb_url, id)
    except:
        pass

    # Commit the changes and close the connection
    conn.commit()
    conn.close()


def _table_videoCategories_insert(channel_id):
    # Connect to the database
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Make a request to the YouTube API
    categories_url = "https://www.googleapis.com/youtube/v3/videoCategories?part=snippet&regionCode=GB&channelId=" + channel_id + \
                     "&key=" + addon.getSetting('API_key')
    __logger(categories_url)
    response = requests.get(categories_url)

    # Get the JSON data from the response
    data = response.json()

    # Extract the channel data from the response
    categories = data["items"]

    for item in categories:
        # Extract the relevant information from the channel data
        id = item.get("id", None)
        snippet = item.get("snippet", None)
        title = snippet.get("title", None)
        assignable = snippet.get("assignable", None)
        try:
            cursor.execute("INSERT INTO videoCategories VALUES (?,?,?,?)", (id, channel_id, title, assignable))
        except sqlite3.IntegrityError:
            pass

    # Commit the changes and close the connection
    conn.commit()
    conn.close()


def _table_playlistItems_insert(playlist_id, media_type):
    # Connect to the database
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    vids_exist = sqlite_get_csv_list(f"SELECT video_id FROM playlistItems where playlist_id = '{playlist_id}'")
    VIDEOS.clear()

    # Set flags to control the loop
    has_next_page = True
    page_token = ""

    # Iterate through the pages of results
    while has_next_page:
        # Make a request to the YouTube API

        channel_url = "https://www.googleapis.com/youtube/v3/playlistItems?maxResults=50&part=snippet,contentDetails," \
                      "status&playlistId=" + playlist_id + "&key=" + addon.getSetting('API_key') + "&pageToken=" + page_token
        __logger(channel_url)
        response = requests.get(channel_url)

        # Get the JSON data from the response
        data = response.json()

        # if no items are returned then disable the channel and quit
        if 'items' not in data:
            __logger("no video in reply, setting to auto disabled")
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            sql = f"update channel set disable_update = 'AUTO' where uploads_playlist_id = '{playlist_id}'"
            cursor.execute(sql)
            sql = f"update playlist set disable_update = 'AUTO' where id = '{playlist_id}'"
            cursor.execute(sql)
            conn.commit()
            return

        # Get the playlist item data from the response
        playlist_items = data['items']

        # Extract the relevant information from the channel data
        for enum, item in enumerate(playlist_items, start=1):
            id = item.get("id", None)
            snippet = item.get("snippet", None)
            playlistId = snippet.get("playlistId", None)
            position = snippet.get("position", None)
            publishedAt = snippet.get("publishedAt", None)
            channelId = snippet.get("channelId", None)
            title = snippet.get("title", None)
            description = snippet.get("description", None)

            thumb_url = ""
            thumb_width = ""
            thumb_height = ""
            thumbnails = snippet.get("thumbnails", None)
            if thumbnails:
                for thumbnail in ('maxres', 'standard', 'high', 'medium', 'default'):
                    if thumbnail in thumbnails:
                        thumb_url = item["snippet"]["thumbnails"][thumbnail]["url"]
                        thumb_width = item["snippet"]["thumbnails"][thumbnail]["width"]
                        thumb_height = item["snippet"]["thumbnails"][thumbnail]["height"]
                        break

            channelTitle = snippet.get("channelTitle", None)
            videoOwnerChannelTitle = snippet.get("videoOwnerChannelTitle", None)
            videoOwnerChannelId = snippet.get("videoOwnerChannelId", None)

            resourceId = snippet.get("resourceId", None)

            videoId = ""
            if resourceId:
                videoId = resourceId.get("videoId", None)

            if not videoId:
                videoId = item.get("contentDetails", None)

            videoPublishedAt = ""
            contentDetails = item.get("contentDetails", None)
            if contentDetails:
                videoPublishedAt = contentDetails.get("videoPublishedAt", None)

            privacyStatus = ""
            status = item.get("status", None)
            if status:
                privacyStatus = status.get("privacyStatus", None)

            if videoId in vids_exist:
                has_next_page = False
                __logger("Reached the first existing videoId for this playlist/channel. Stopping channel import here.")
                break
            __logger(f"NEW: VideoId: {videoId}  Title: {title}")

            # Insert the playlist item data into the database
            VIDEOS.append(videoId)
            try:
                cursor.execute(
                    "INSERT INTO playlistItems VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (id, playlistId, position, publishedAt, channelId, channelTitle, title, description, thumb_url,
                     thumb_width, thumb_height, videoOwnerChannelTitle, videoOwnerChannelId, videoId,
                     videoPublishedAt, privacyStatus)
                )
            except sqlite3.IntegrityError:
                pass

        if 'nextPageToken' in data:
            page_token = data['nextPageToken']
        else:
            has_next_page = False

    # Commit the changes and close the connection
    conn.commit()
    conn.close()

    #dialog.close()

def _table_videos_insert(vid_ids, media_type):
    # If the vid_ids parameter is a string then make it a list
    if isinstance(vid_ids, str):
        vid_ids = [vid_ids]

    # if vid_ids is empty then exit
    if len(vid_ids) < 1:
        __logger("No new videos found for this playlist/channel.")
        return

    # Connect to the database
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    vids_custom = []

    for i in range(0, len(vid_ids), 50):
        chunk = vid_ids[i:i + 50]
        get = ','.join(chunk)
        video_url = "https://www.googleapis.com/youtube/v3/videos?maxResults=500&part=snippet,contentDetails,status," \
                    "localizations&id=" + get + "&key=" + addon.getSetting('API_key')
        response = requests.get(video_url)

        # Get the JSON data from the response
        data = response.json()

        # Get the video data from the response
        for video in data['items']:
            id = video.get("id", None)
            snippet = video.get("snippet", None)
            published_at = snippet.get('publishedAt', None)
            channel_id = snippet.get('channelId', None)
            title = scrub_text(snippet.get('title', None))
            description = scrub_text(snippet.get('description', None))

            thumb_url = ""
            thumb_width = ""
            thumb_height = ""
            thumbnails = snippet.get("thumbnails", None)
            if thumbnails:
                for thumbnail in ('maxres', 'standard', 'high', 'medium', 'default'):
                    if thumbnail in thumbnails:
                        thumb_url = video["snippet"]["thumbnails"][thumbnail]["url"]
                        thumb_width = video["snippet"]["thumbnails"][thumbnail]["width"]
                        thumb_height = video["snippet"]["thumbnails"][thumbnail]["height"]
                        break

            channel_title = scrub_text(snippet.get('channelTitle', None))
            tags = str(snippet.get('tags', ''))
            category_id = snippet.get('categoryId', None)
            default_audio_language = snippet.get('defaultAudioLanguage', None)

            contentDetails = video.get("contentDetails", None)
            duration = int(iso_duration_to_minutes(contentDetails.get("duration", None)))
            definition = contentDetails.get("definition", None)
            caption = contentDetails.get("caption", None)
            licensed_content = contentDetails.get("licensedContent", None)

            region_allowed = None
            region_blocked = None
            region_restriction = contentDetails.get("regionRestriction", None)
            if region_restriction:
                region_allowed = str(region_restriction.get("allowed", ""))
                region_blocked = str(region_restriction.get("blocked", ""))

            # if the video is a movie type and the duration is less than minimum required then skip the video.
            if media_type == 'movies' and duration < MIN_MINUTES:
                continue
            # if the video is a series type and is less than a minute the ignore shorts setting is active.
            elif media_type == 'series' and duration <= 1 and IGNORE_SHORTS:
                continue
            else:
                vids_custom.append(id)
                # For any other video, insert it into the videos tables.
                try:
                    cursor.execute(
                        "INSERT INTO videos VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (id, published_at, channel_id, title, description, thumb_url, thumb_width, thumb_height,
                         channel_title, tags, category_id, default_audio_language, duration, definition, caption,
                         licensed_content, region_allowed, region_blocked))
                except sqlite3.IntegrityError:
                    pass
        conn.commit()

    # Insert videos_custom records with clean title for movies.
    # Separate from main loop because commit needs to be complete on videos before _clean_title can be run.
    if media_type == 'movies':
        for id in vids_custom:
            clean_title = _clean_title(id, channel_title)
            try:
                cursor.execute("INSERT INTO videos_custom VALUES (?,?,?,?,?)",
                               (id, clean_title, 'N', '', ''))
            except sqlite3.IntegrityError:
                pass
        conn.commit()
    conn.close()

    # Remove any restricted videos before creating the files.
    remove_restricted_videos_and_files()


def _update_season_episode(media_type, channel_type, src_playlist, sort_by=None):
    # Connect to the database
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    if media_type == 'series' and (channel_type == 'channel' or (channel_type == 'playlist' and not sort_by)):
        vid_ids = table_select("vwVideosSeries", "video_id, strftime('%Y', published_at) AS year",
                               condition=f"ifnull(season,'') = '' and src_playlist = '{src_playlist}'"
                               , order_by="published_at asc")
        result = _get_season_and_episode(src_playlist)
        season = result[0] or 0
        episode = result[1] or 0
        for v in vid_ids:
            id = v[0]
            year = v[1]
            if season != year:
                season = year
                episode = 0
            episode += 1
            __logger(str(season) + ": " + str(episode))

            try:
                cursor.execute("INSERT INTO videos_custom VALUES (?,?,?,?,?)", (id, '', 'N', season, episode))
            except sqlite3.IntegrityError:
                pass
        conn.commit()
    elif media_type == 'series' and channel_type == 'playlist' and sort_by:
        vid_ids = table_select("vwVideosSeries", "video_id, strftime('%Y', published_at) AS year",
                               condition=f"ifnull(season,'') = '' and src_playlist = '{src_playlist}'"
                               , order_by="position asc")
        result = _get_season_and_episode(src_playlist)
        season = 1
        episode = result[1] or 0
        for v in vid_ids:
            id = v[0]
            episode += 1
            __logger(str(season) + ": " + str(episode))

            try:
                cursor.execute("INSERT INTO videos_custom VALUES (?,?,?,?,?)", (id, '', 'N', season, episode))
            except sqlite3.IntegrityError:
                pass
        conn.commit()
    conn.close()
    # _table_videoCategories_insert(channel_id)


def _clean_title(video_id, channel_title):
    # Connect to the database
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Execute a SELECT query
    cursor.execute(f"SELECT title, description, published_at FROM videos WHERE id = '{video_id}'")

    # Fetch the row
    row = cursor.fetchone()

    # Extract the values from the tuple
    title, description, published_at = row
    orig_title = title

    # Close the connection to the database
    conn.close()

    published_year = published_at.split('-')[0]
    year = None

    # If the title contains the channel name then remove it.
    if channel_title in title:
        title = title.replace(channel_title, "")

    # Try to find a date in the title in parentheses or square brackets
    year_pattern = r'\[(19|20)[0-9]{2}\]|\((19|20)[0-9]{2}\)'
    match = re.search(year_pattern, title)
    if match:
        # Get the date from the match and remove any parentheses or square brackets
        start = match.start()
        end = match.end()
        year = re.sub(r'[\[\]\(\)]', '', title[start:end])

        # Truncate the title up to where the date was found
        if start == 0:
            title = title[end:]
        else:
            title = title[:start]
    else:
        # If no date was found in parentheses or square brackets, try to find a date without brackets
        year_pattern = r'(19|20)[0-9]{2}'
        match = re.search(year_pattern, title)
        if match:
            # Get the date from the match
            start = match.start()
            end = match.end()
            year = title[start:end]

            # Truncate the title up to where the date was found
            if start == 0:
                title = title[end:]
            else:
                title = title[:start]
        else:
            # If no date was found in title, then going looking in the description
            year_pattern = r'\[(19|20)[0-9]{2}\]|\((19|20)[0-9]{2}\)'
            match = re.search(year_pattern, description)
            if match:
                # Get the date from the match and remove any parentheses or square brackets
                start = match.start()
                end = match.end()
                year = re.sub(r'[\[\]\(\)]', '', description[start:end])
            else:
                # If no date was found in parentheses or square brackets, try to find a date without brackets
                year_pattern = r'(19|20)[0-9]{2}'
                match = re.search(year_pattern, description)
                if match:
                    # Get the date from the match
                    start = match.start()
                    end = match.end()
                    year = description[start:end]

            #   this checks that the year found in the description is at least two years older than the aired date.
            #   in which case the year will be omitted. this prevents incorrect years being pulled from the description.
            #   it's not perfect, but it is necessary.
            if year:
                if int(published_year) - int(year) < 2:
                    year = None

    # Check if the title begins with any unusual characters and remove them.
    try:
        while title[0] in (' ', '-', '|', '(', ')', '[', ']') and len(title) > 1:
            title = title[1:]
    except IndexError:
        pass

    # Try to split the title on '|', '(', or '[' in that order
    for delimiter in ('|', '(', '[', '//', '   '):
        if delimiter in title:
            title = title.split(delimiter)[0]

    # Use a regex string variable to remove any matches
    title = re.sub(r'\b' + REGEX_STRING + r'\b', '', title, flags=re.IGNORECASE)

    # Check if the title ends with any unusual characters and remove them.
    try:
        while title[-1] in (' ', '-', '|', '(', ')', '[', ']', ',') and len(title) > 1:
            title = title[:-1]
    except IndexError:
        pass

    # Remove leading and trailing spaces from the title
    title = title.strip()

    # Concatenate the title and the date with a space in between
    if year:
        title = f"{title} ({year})"

    # Use str.title() to capitalize the first character of each word
    title = title.title()

    # Find all words that have an apostrophe as the penultimate character
    pattern = r"(\b\w+'\w\b)"
    words = re.findall(pattern, title)

    # Lowercase the final character of the effected words.
    ###!!! Revisit this, doesn't really work. must be a better way
    for word in words:
        lowercase_word = word[:-1] + word[-1].lower()
        title = title.replace(word, lowercase_word)

    __logger(f"{orig_title} -> {title}")
    return title


def _create_series_nfo_files(title, description, published_at, thumb_url, id):
    output = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>
    <tvshow>
            <title>{title}</title>
            <showtitle>{title}</showtitle>
            <plot>{description}</plot>
            <genre>None</genre>
            <premiered>{published_at}</premiered>
            <aired>{published_at}</aired>
            <studio>{title}</studio>
            <thumb>{thumb_url}</thumb>
            <thumb aspect="poster">{thumb_url}</thumb>
            <thumb aspect="banner">{thumb_url}</thumb>
            <fanart>
                    <thumb>{thumb_url}</thumb>
            </fanart>
            <tag>Youtube</tag>
    </tvshow>"""

    # define the folder for the nfo output
    folder = SERIES + "\\" + id

    # Check if the folder exists
    if not os.path.exists(folder):
        # Create the folder
        os.makedirs(folder)

    tvshow_file = folder + '\\' + 'tvshow.nfo'

    # Open a new file with the .strm extension in write mode
    with open(tvshow_file, "w", encoding='utf-8') as f:
        # Write the tv show information to the file.
        f.write(output)


def _create_kodi_media(media_type, src_playlist=None):

    # Set processing folder and SQL to run
    if 'movies' in media_type:
        folder = MOVIES
        sql = "SELECT DISTINCT video_id, clean_title as title FROM vwVideosMovies where ifnull(kodi_files,'N') = 'N'"
    elif 'series' in media_type:
        folder = SERIES
        sql = "SELECT video_id, title, season, episode, description, published_at, thumbnail_url, " \
              "duration, src_playlist, channel_title FROM vwVideosSeries where ifnull(kodi_files,'N') = 'N'"
    else:
        __logger("Unexpected media_type. Exiting")
        sys.exit()

    # If a channel/playlist has been provided then include that in the SQL.
    if src_playlist:
        sql += f" and src_playlist = '{src_playlist}'"
    __logger(sql)

    # Check if the folder exists, if not create it.
    if not os.path.exists(folder):
        os.makedirs(folder)

    # Run the SQL
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(sql)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    # Iterate over the rows
    for row in rows:
        video_id = row[0]
        title = row[1]
        if media_type == 'movies' and len(title) < 1:
            continue
        if 'movies' in media_type:
            # Create strm files for movies
            _create_strm_file(title, folder, video_id, media_type)
        elif 'series' in media_type:
            # Create strm and nfo files for series
            video_id, title, season, episode, description, published_at, thumbnail_url, duration, src_playlist, \
                channel_title = row
            _create_strm_file(title, folder, video_id, media_type, src_playlist, season, episode)
            _create_episode_nfo_file(folder, src_playlist, channel_title, title, season, episode, description,
                                     published_at, thumbnail_url, duration)

    if 'movies' in media_type:
        sql = "UPDATE videos_custom SET kodi_files = 'Y' where video_id in (" \
              "SELECT DISTINCT video_id FROM vwVideosMovies where ifnull(kodi_files,'N') = 'N'"
    elif 'series' in media_type:
        sql = "UPDATE videos_custom SET kodi_files = 'Y' where video_id in (" \
              "SELECT video_id FROM vwVideosSeries where ifnull(kodi_files,'N') = 'N'"
    if src_playlist:
        sql += f" and src_playlist = '{src_playlist}')"
    else:
        sql += ")"
    __logger(sql)

    # Run the SQL
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(sql)
    conn.commit()
    cursor.close()
    conn.close()


def _create_strm_file(title, folder, video_id, media_type, src_playlist=None, season=None, episode=None):
    plugin = YOUTUBE_CLIENT
    # if video_id in USE_INVIDIOUS:
    #    plugin = INVIDIOUS_CLIENT

    filename = title
    if media_type == 'movies':
        # For movies, create a filename with the video_id in square brackets at the end.
        # This will make file interactions easier in future if the video_id can be searched for.
        # It shouldn't affect scraping.
        filename = create_valid_name(title) + f" [{video_id}]"
    elif media_type == 'series':
        folder += '\\' + src_playlist + '\\' + str(season)
        filename = 'S' + str(season) + 'E' + str(episode)
    write_file = folder + '\\' + filename + '.strm'
    __logger(write_file)

    # Check if the folder exists, if not create it.
    if not os.path.exists(folder):
        os.makedirs(folder)

    # Open a new file with the .strm extension in write mode
    with open(write_file, "w") as f:
        # Write the YouTube plugin string to the file
        f.write(plugin + video_id)


def _create_episode_nfo_file(folder, src_playlist, channel_title, title, season, episode, description, published_at,
                             thumbnail_url, duration):
    output = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>
            <episodedetails>
                <title>{title}</title>
                <season>{season}</season>
                <episode>{episode}</episode>
                <plot>{description}</plot>
                <aired>{published_at}</aired>
                <studio>{channel_title}</studio>
                <credits>{channel_title}</credits>
                <director>{channel_title}</director>
                <thumb>{thumbnail_url}</thumb>
                <runtime>{duration}</runtime>
                <fileinfo>
                    <streamdetails>
                        <durationinseconds>{duration}</durationinseconds>
                    </streamdetails>
                </fileinfo>
            </episodedetails>"""

    ## this function is temporary and might need to be adapted for Kodi ##
    folder += '\\' + src_playlist + '\\' + str(season)
    filename = 'S' + str(season) + 'E' + str(episode)
    write_file = folder + '\\' + filename + '.nfo'

    # Check if the folder exists
    if not os.path.exists(folder):
        # Create the folder
        os.makedirs(folder)

    with open(write_file, "w", encoding='utf-8') as f:
        # Write the YouTube plugin string to the file
        f.write(output)


def iso_duration_to_minutes(in_time):
    if "PT" not in in_time:
        return str(0)
    time = in_time.split("PT")[1]
    if 'H' in time and 'M' in time and 'S' in time:
        duration = int(time.split("H")[0]) * 60 + int(time.split("H")[1].split("M")[0])
    elif 'H' in time and 'M' in time:
        duration = int(time.split("H")[0]) * 60 + int(time.split("H")[1].split("M")[0])
    elif 'H' in time and 'S' in time:
        duration = int(time.split("H")[0]) * 60
    elif 'M' in time and 'S' in time:
        duration = int(time.split("M")[0])
    elif 'M' in time:
        duration = int(time.split("M")[0])
    else:
        duration = 1
    return str(duration)


def scrub_text(string):
    if PY_V >= 3:  # Python 3
        text = re.compile(u"[^\U00000000-\U0000d7ff\U0000e000-\U0000ffff]", flags=re.UNICODE)
        scrub_text = text.sub(u"", string)
    else:
        text = re.compile(u"[^\U00000000-\U0000d7ff\U0000e000-\U0000ffff]", flags=re.UNICODE)
        scrub_text = text.sub(u'', unicode(string, 'utf-8'))
    return scrub_text


def create_valid_name(name):
    return "".join(i for i in name if i not in '"\/:*?<>|')


# think about implementing
def use_invidious_if_age_restricted():
    if 'contentRating' in item['contentDetails']:
        if 'ytRating' in item['contentDetails']['contentRating']:
            if 'ytAgeRestricted' in item['contentDetails']['contentRating']['ytRating']:
                USE_INVIDIOUS.append(item['id'])


