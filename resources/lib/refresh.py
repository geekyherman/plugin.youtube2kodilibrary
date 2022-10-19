import re
import xbmcgui
import datetime
import time
import xbmc
from contextlib import closing
from xbmcvfs import File
from resources.lib.variables import *
from resources.lib.helper_functions import c_download, __save, __logger, __upgrade_refresh
from resources.lib.menu import __folders, __search
from resources.lib.music_videos import __parse_music
from resources.lib.channels import __parse_videos, __get_video_details


def __refresh(ask):
    __logger("Refresh ask = " + str(ask))
    __logger("Lock file = " + str(xbmcvfs.exists(LOCK_FILE)))
    if ask:
        if xbmcvfs.exists(LOCK_FILE):
            xbmcgui.Dialog().notification(addonname, "Refresh currently in progress. Please try again later.",
                                          addon_resources + '/icon.png', 2500)
        else:
            __logger("no lock file")
            menuItems = ['Refresh Series', 'Refresh Movies', 'Refresh Music', 'Refresh All']
            try:
                ret = xbmcgui.Dialog().select('Choose refresh type', menuItems)
                if ret == 0:
                    CATEGORY.append('series')
                elif ret == 1:
                    CATEGORY.append('movies')
                elif ret == 2:
                    CATEGORY.append('music')
                elif ret == 3:
                    CATEGORY.append('all')
            except KeyError:
                __logger("no refresh type selected")
                pass
    series_count = len(CONFIG['channels']) + len(CONFIG['playlists'])
    movies_count = len(CONFIG['movies']) + len(CONFIG['movies_playlists'])
    music_count = len(CONFIG['music_videos'])
    if 'series' in CATEGORY:
        PARSER['total_steps'] = series_count
    elif 'movies' in CATEGORY:
        PARSER['total_steps'] = movies_count
    elif 'music' in CATEGORY:
        PARSER['total_steps'] = music_count
    elif 'all' in CATEGORY:
        PARSER['total_steps'] = series_count + movies_count + music_count
    if not xbmcvfs.exists(LOCK_FILE):
        if PY_V >= 3:
            with xbmcvfs.File(LOCK_FILE, 'w') as f:  # Python 3
                f.write('')
                __logger("created lock file")
        else:
            f = xbmcvfs.File(LOCK_FILE, 'w')  # Python 2
            f.write(bytearray(''))
            f.close()
            __logger("created lock file")
        if len(CATEGORY) > 0:
            __logger("categories to process")
            __logger(CATEGORY)
            if addon.getSetting('display_notifications') == 'true' and not ask:
                __logger("progress dialogs will be displayed")
                xbmcgui.Dialog().notification(addonname, AddonString(30026), addon_resources + '/icon.png', 2500)
            if 'series' in CATEGORY or 'all' in CATEGORY:
                for items in CONFIG['playlists']:
                    pl_ids = []
                    for pl in CONFIG['playlists'][items]['playlist_id']:
                        pl_ids.append(pl)
                        __logger("playlist appended " + pl)
                    __logger("about to parse: " + str(pl_ids))
                    PARSER['refresh_type'] = 'multi'
                    __parse_videos(pl_ids, items, 'playlists')
                for items in CONFIG['channels']:
                    pl_ids = [CONFIG['channels'][items]['playlist_id']]
                    __logger("about to parse: " + str(pl_ids))
                    PARSER['refresh_type'] = 'multi'
                    __parse_videos(pl_ids, items, 'channels')
                CONFIG['scan_date']['series'] = int(time.time())
            if 'movies' in CATEGORY or 'all' in CATEGORY:
                for items in CONFIG['movies_playlists']:
                    pl_ids = []
                    for pl in CONFIG['movies_playlists'][items]['playlist_id']:
                        pl_ids.append(pl)
                        __logger("movies playlist appended: " + pl)
                    __logger("about to parse: " + str(pl_ids))
                    PARSER['refresh_type'] = 'multi'
                    __parse_videos(pl_ids, items, 'movies_playlists')
                for items in CONFIG['movies']:
                    pl_ids = [CONFIG['movies'][items]['playlist_id']]
                    __logger("about to parse: " + str(pl_ids))
                    PARSER['refresh_type'] = 'multi'
                    __parse_videos(pl_ids, items, 'movies')
                __scan_files_for_deletion(MOVIES)
                CONFIG['scan_date']['movies'] = int(time.time())
            if 'music' in CATEGORY or 'all' in CATEGORY:
                for items in CONFIG['music_videos']:
                    __parse_music(True, CONFIG['music_videos'][items]['playlist_id'])
                CONFIG['scan_date']['music'] = int(time.time())
            __save()
            if xbmcvfs.exists(LOCK_FILE):
                xbmcvfs.delete(LOCK_FILE)
            if 'all' in CATEGORY or len(CATEGORY) > 1:
                xbmc.executebuiltin('UpdateLibrary(video)')
            elif 'series' in CATEGORY:
                xbmc.executebuiltin("UpdateLibrary(video,"+CHANNELS+")")
            elif 'movies' in CATEGORY:
                xbmc.executebuiltin("UpdateLibrary(video,"+MOVIES+")")
            elif 'music' in CATEGORY:
                xbmc.executebuiltin("UpdateLibrary(video,"+MUSIC_VIDEOS+")")
            if addon.getSetting('display_notifications') == 'true' and not ask:
                xbmcgui.Dialog().notification(addonname, AddonString(30027), addon_resources+'/icon.png', 2500)


def __scan_files_for_deletion(fullpath):
    last_scan = 872835240
    try:
        last_scan = int(CONFIG['scan_date']['movie_delete'])
    except KeyError:
        pass
    if (last_scan + int(xbmcaddon.Addon().getSetting('movies_delete_interval')) * 3600) \
            <= int(time.time()) and xbmcaddon.Addon().getSetting('API_key'):
        if HIDE['progress'] is False:
            try:
                PDIALOG.update(PARSER['percent'], 'Removing unavailable movies.')
            except:
                PDIALOG.create(AddonString(30016), 'Removing unavailable movies.')
        dirs = xbmcvfs.listdir(fullpath)
        vid = []
        for directory in dirs[0]:
            folder = fullpath + '/' + directory
            files = xbmcvfs.listdir(folder)
            for file in files[1]:
                if '.strm' in file:
                    with closing(File(folder + '/' + file)) as fo:
                        videoId = fo.read()[-11:]
                    if len(VIDEOS_TO_DELETE) > 0:
                        for v in VIDEOS_TO_DELETE:
                            if videoId == v['video_id']:
                                xbmcvfs.delete(folder + '/' + file)
                                continue
                    add = {'video_id': videoId, 'path': folder + '/' + file}
                    VIDEOS_TO_DELETE.append(add)
                    vid.append(videoId)
        __get_video_details(vid, True, 'movies')
        for v in VIDEOS_TO_DELETE:
            xbmcvfs.delete(v['path'])
        CONFIG['scan_date']['movie_delete'] = int(time.time())

