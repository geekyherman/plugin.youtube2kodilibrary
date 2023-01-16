# -*- coding: utf-8 -*-
"""
YOUTUBE CHANNELS TO KODI
"""
import sqlite3
import os
import sys
import math
import requests
import xbmcgui
import re
import xbmcvfs
import time
import stat
from resources.lib.create_db import *
from resources.lib.variables import *
from resources.lib.helper_functions import __logger, __ask, c_download, convert, __get_token_reset, \
    recursive_delete_dir, table_select, sqlite_get_csv_list
from resources.lib.channels import create_channel, ChannelProcessor
from resources.lib.menu import __folders, __search
from resources.lib.refresh import __refresh


def __check_key_validity(key):
    req = requests.get("https://www.googleapis.com/youtube/v3/channels?part=snippet&id=UCS5tt2z_DFvG7-39J3aE-bQ&key="+key)
    if req.status_code == 200:
        return 'valid'
    return 'invalid'


def file_age_in_seconds(pathname):
    return time.time() - os.stat(pathname)[stat.ST_MTIME]


def __start_up():
    if xbmcvfs.exists(LOCK_FILE):
        if file_age_in_seconds(LOCK_FILE) > 600:
            xbmcvfs.delete(LOCK_FILE)
    API_KEY = addon.getSetting('API_key')
    if API_KEY == "":
        ciyapi = xbmcaddon.Addon('plugin.video.youtube').getSetting('youtube.api.key')
        if ciyapi:
            API_KEY = ciyapi
            if __check_key_validity(API_KEY) == 'valid':
                addon.setSetting('API_key', API_KEY)
                return 1

        # whine about the missing API key...
        __print(AddonString(30019))
        wrongkey=""
        while True:
            API_KEY = __ask(wrongkey, AddonString(30020))
            if API_KEY != "":
                if __check_key_validity(API_KEY) == 'valid':
                    addon.setSetting('API_key', API_KEY)
                    #Key is valid, ty....
                    __print(30021)
                    break
                # key isn't valid
                __print(30022)
                wrongkey = API_KEY
            else:
                # empty
                __print(30023)
                raise SystemExit
    newlimit = int(math.ceil(int(addon.getSetting('import_limit')) / 100.0)) * 100
    addon.setSetting('import_limit', str(newlimit))


def __CHANNELS(c_id, media_type, channel_type):
    #1: List files
    #2: Delete
    #3: Disable/Enable Update
    #4: Refresh
    #5: Rebuild (Remove and Re-add)

    cp = ChannelProcessor(media_type, c_id, channel_type)

    # Connect to the database
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    sql = f"select title, disable_update from {channel_type} where id = '{c_id}'"
    cursor.execute(sql)
    result = cursor.fetchone()

    sql = f"select title from videos where channel_id = '{c_id}'"
    file_list = sqlite_get_csv_list(sql)
    __logger(file_list)

    if media_type == 'movies':
        path = MOVIES
    else:
        path = SERIES

    cname = result[0]
    disabled = result[1]
    if disabled:
        menuItems = ['List files', AddonString(30039), 'Enable Updates', 'Rebuild (Remove and Re-add)']
    else:
        menuItems = ['List files', AddonString(30039), 'Disable Updates', 'Refresh', 'Rebuild (Remove and Re-add)']

    try:
        ret = xbmcgui.Dialog().select('Manage: ' + cname, menuItems)
        if ret == 0:
            xbmcgui.Dialog().select('Select a name', file_list, autoclose=0)
        if ret == 1:
            cp.delete()
        elif disabled and ret == 2:
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            sql = f"update {channel_type} set disable_update = NULL where id = '{c_id}'"
            cursor.execute(sql)
            conn.commit()
        elif not disabled and ret == 2:
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            sql = f"update {channel_type} set disable_update = 'USER' where id = '{c_id}'"
            cursor.execute(sql)
            conn.commit()
        elif (disabled and ret == 3) or (not disabled and ret == 4):
            cp.rebuild()
        elif not disabled and ret == 3:
            if HIDE['progress'] is False:
                PARSER['refresh_type'] = 'single'
                DP.create('Refreshing channel....')
            cp.refresh()
            if len(VIDEOS) > 0:
                xbmc.executebuiltin("UpdateLibrary(video," + path + ")")
        else:
            pass
    except KeyError:
        pass
    conn.close()


__start_up()
try:
    mode = sys.argv[2][1:].split(u'mode')[1][1:]
except IndexError:
    mode = None

try:
    foldername = sys.argv[2][1:].split(u'mode')[0].split(u'=')[1][:-1]
    __logger("foldername: " + foldername)
except IndexError:
    foldername = None

if not xbmcvfs.exists(DB_NAME):
    create_all()

if mode is None:
    __folders('menu')
elif mode == 'AddItem_tv':
    create_channel(foldername, 'series', 'channel')
elif mode == 'AddItem_tv_playlist':
    create_channel(foldername, 'series', 'playlist')
elif mode == 'AddItem_movies':
    create_channel(foldername, 'movies', 'channel')
elif mode == 'AddItem_movies_playlist':
    create_channel(foldername, 'movies', 'playlist')
elif mode == 'ManageItem':
    if foldername == 'Add_Channel_tv':
        query = __ask('', AddonString(30038))
        if query:
            HIDE['progress'] = False
            __search(query, 'tv')
    elif foldername == 'Add_Channel_tv_playlist':
        query = __ask('', AddonString(30038))
        if query:
            HIDE['progress'] = False
            __search(query, 'tv_playlist')
    elif foldername == 'Add_Channel_movies':
        query = __ask('', AddonString(30038))
        if query:
            HIDE['progress'] = False
            __search(query, 'movies')
    elif foldername == 'Add_Channel_movies_playlist':
        query = __ask('', AddonString(30038))
        if query:
            HIDE['progress'] = False
            __search(query, 'movies_playlist')
    elif foldername == 'Discover':
        channels = table_select("vwDiscoverMovies", "video_owner_channel_id, video_owner_channel_title",
                                f"video_owner_channel_id <> 'UCuVPpxrm2VAgpH3Ktln4HXg' limit {DISCOVERY_MAX_CHANNELS}")
        for channel in channels:
            if HIDE['progress'] is False:
                DP.create(f'Adding: {channel[1]}')
            cp = ChannelProcessor('movies', channel[0], 'channel', True)
            cp.insert()
    elif foldername == 'Manage':
        __folders('Manage')
    elif foldername == 'Refresh':
        HIDE['progress'] = False
        __refresh(True)
elif mode == 'C_MENU':
    __CHANNELS(foldername, 'series', 'channel')
elif mode == 'PLAYLIST_MENU':
    __CHANNELS(foldername, 'series', 'playlist')
elif mode == 'M_MENU':
    __CHANNELS(foldername, 'movies', 'channel')
elif mode == 'M_PLAYLIST_MENU':
    __CHANNELS(foldername, 'movies', 'playlist')
elif mode == 'Refresh':
    if not xbmcvfs.exists(LOCK_FILE):
        for cat in ('series', 'movies'):
            last_scan = 872835240
            try:
                last_scan = table_select('last_update', cat)[0][0]
            except KeyError:
                pass
            if (last_scan + int(xbmcaddon.Addon().getSetting(cat + '_update_interval')) * 3600) \
                    <= int(time.time()) and xbmcaddon.Addon().getSetting('API_key'):
                CATEGORY.append(cat)
        if len(CATEGORY) > 0:
            HIDE['progress'] = True
            __refresh(False)
elif mode == 'OpenSettings':
    xbmcaddon.Addon(addonID).openSettings()
else:
    __folders('menu')