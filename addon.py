# -*- coding: utf-8 -*-
"""
YOUTUBE CHANNELS TO KODI
"""
import os
import sys
import math
import requests
import xbmcgui
import re
import xbmcvfs
import time
import stat
from resources.lib.variables import *
from resources.lib.helper_functions import __logger, __ask, __save, __print, c_download, convert, __get_token_reset, \
    recursive_delete_dir, __upgrade_refresh
from resources.lib.music_videos import __add_music, __parse_music
from resources.lib.channels import __create_channel, __parse_videos, __get_playlists, __select_playlists
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
    if 'last_scan' in CONFIG:
        __upgrade_refresh()
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


def __Remove_from_index(a):
    global INDEX
    local_index_file = a
    if PY_V >= 3:
        with xbmcvfs.File(local_index_file) as f:     # PYTHON 3 v19+
            local_index = json.load(f)
    else:
        f = xbmcvfs.File(local_index_file)            # PYTHON 2 v18+
        local_index = f.read()
        f.close()
    res = list(filter(lambda i: i not in local_index, INDEX))
    INDEX = res
    __save(data=INDEX, file=index_file)


def __CHANNELS(c_id, media_type):
    #0: Refresh
    #1: Delete
    if media_type == 'movies':
        path = MOVIES
    else:
        path = CHANNELS
    cname = CONFIG[media_type][c_id]['channel_name']
    menuItems = [AddonString(30031), AddonString(30039)]
    try:
        ret = xbmcgui.Dialog().select('Manage: ' + cname, menuItems)
        if ret == 0:
            PARSER['refresh_type'] = 'single'
            pl_id = [CONFIG[media_type][c_id]['playlist_id']]
            __parse_videos(pl_id, c_id, media_type)
            xbmc.executebuiltin("UpdateLibrary(video," + path + ")")
        elif ret == 1:
            cdir = path + '\\' + c_id
            # Are you sure to remove X...
            ret = xbmcgui.Dialog().yesno(AddonString(30035).format(cname), AddonString(30036).format(cname))
            if ret:
                local_index_file = path + '\\' + c_id + '\\index.json'
                if xbmcvfs.exists(local_index_file):
                    __Remove_from_index(local_index_file)
                CONFIG[media_type].pop(c_id)
                __save()
                # Remove from library?
                ret = xbmcgui.Dialog().yesno(AddonString(30035).format(cname), AddonString(30037).format(cname))
                if ret:
                    success = recursive_delete_dir(cdir)
                    if success:
                        xbmc.executebuiltin("CleanLibrary(video)")
        else:
            pass
    except KeyError:
        pass


def __PLAYLISTS(c_id, media_type):
    #0: Refresh
    #1: Add/Remove
    #2: Delete
    if media_type == 'movies_playlists':
        path = MOVIES
    else:
        path = CHANNELS
    cname = CONFIG[media_type][c_id]['channel_name']
    menuItems = [AddonString(30031), 'Add/Remove a playlist', AddonString(30039)]
    try:
        ret = xbmcgui.Dialog().select('Manage: ' + cname, menuItems)
        if ret == 0:
            PARSER['refresh_type'] = 'single'
            pl_id = [CONFIG[media_type][c_id]['playlist_id']]
            __parse_videos(pl_id, c_id, media_type)
            xbmc.executebuiltin("UpdateLibrary(video," + path + ")")
        elif ret == 1:
            playlists = __get_playlists(CONFIG[media_type][c_id]['original_channel_id'])
            data_set = __select_playlists(playlists, c_id)
            if data_set:
                CONFIG[media_type][c_id].pop('playlist_id')
                CONFIG[media_type][c_id]['playlist_id'] = data_set
                __save()
        elif ret == 2:
            cdir = path + '\\' + c_id
            __logger(cdir)
            # Are you sure to remove X...
            ret = xbmcgui.Dialog().yesno(AddonString(30035).format(cname), AddonString(30036).format(cname))
            if ret:
                local_index_file = path + '\\' + c_id + '\\index.json'
                if xbmcvfs.exists(local_index_file):
                    __Remove_from_index(local_index_file)
                CONFIG[media_type].pop(c_id)
                __save()
                # Remove from library?
                ret = xbmcgui.Dialog().yesno(AddonString(30035).format(cname), AddonString(30037).format(cname))
                if ret:
                    success = recursive_delete_dir(cdir)
                    if success:
                        xbmc.executebuiltin("CleanLibrary(video)")
        else:
            pass
    except KeyError:
        pass


def __MUSIC_MENU(c_id):
    #0: Refresh
    #1: Delete
    menuItems = [AddonString(30031),AddonString(30039)]
    try:
        ret = xbmcgui.Dialog().select('Manage: '+CONFIG['music_videos'][c_id]['channel_name'], menuItems)
        if ret == 0:
            __parse_music(True, CONFIG['music_videos'][c_id]['playlist_id'])
        elif ret == 1:
            cname = CONFIG['music_videos'][c_id]['channel_name']
            cdir = MUSIC_VIDEOS+'\\'+c_id
            __logger(cdir)
            # Are you sure to remove X...
            ret = xbmcgui.Dialog().yesno(AddonString(30035).format(cname), AddonString(30036).format(cname))
            if ret:
                CONFIG['music_videos'].pop(c_id)
                __save()
                # Remove from library?
                ret = xbmcgui.Dialog().yesno(AddonString(30035).format(cname), AddonString(30037).format(cname))
                if ret:
                    success = recursive_delete_dir(cdir)
                    if success:
                        xbmc.executebuiltin("CleanLibrary(video)")
    except KeyError:
        pass


__start_up()
try:
    mode = sys.argv[2][1:].split(u'mode')[1][1:]
except IndexError:
    mode = None

try:
    foldername = sys.argv[2][1:].split(u'mode')[0].split(u'=')[1][:-1]
except IndexError:
    foldername = None

if mode is None:
    __folders('menu')
elif mode == 'AddItem_tv':
    __create_channel(foldername, 'channels')
elif mode == 'AddItem_tv_playlist':
    __create_channel(foldername, 'playlists')
elif mode == 'AddItem_movies_playlist':
    __create_channel(foldername, 'movies_playlists')
elif mode == 'AddItem_movies':
    __create_channel(foldername, 'movies')
elif mode == 'AddItem_music':
    __add_music(foldername)
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
    elif foldername == 'Add_Channel_music':
        query = __ask('', AddonString(30038))
        if query:
            HIDE['progress'] = False
            __search(query, 'music')
    elif foldername == 'Manage':
        __folders('Manage')
    elif foldername == 'Refresh':
        HIDE['progress'] = False
        __refresh(True)
elif mode == 'C_MENU':
    __CHANNELS(foldername, 'channels')
elif mode == 'PLAYLIST_MENU':
    __PLAYLISTS(foldername, 'playlists')
elif mode == 'M_MENU':
    __CHANNELS(foldername, 'movies')
elif mode == 'M_PLAYLIST_MENU':
    __PLAYLISTS(foldername, 'movies_playlists')
elif mode == 'MUSIC_MENU':
    __MUSIC_MENU(foldername)
elif mode == 'Refresh':
    for cat in ('series', 'movies', 'music'):
        last_scan = 872835240
        try:
            last_scan = int(CONFIG['scan_date'][cat])
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
elif 'SPLIT_EDITOR' in mode:
    params = dict(parse.parse_qsl(parse.urlsplit(sys.argv[2]).query))
    channel_id = params['playlist']
    action = params['action']
    __PLAYLIST_EDITOR(params)
else:
    __folders('menu')
