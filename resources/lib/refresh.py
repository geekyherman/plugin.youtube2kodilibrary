import sqlite3
import re
import xbmcgui
import datetime
import time
import xbmc
from contextlib import closing
from xbmcvfs import File
from resources.lib.variables import *
from resources.lib.helper_functions import c_download, __logger, scan_files_for_deletion, table_update, table_select, \
    sqlite_get_csv_list
from resources.lib.menu import __folders, __search
from resources.lib.channels import ChannelProcessor


def __refresh(ask):
    __logger("Refresh ask = " + str(ask))
    __logger("Lock file = " + str(xbmcvfs.exists(LOCK_FILE)))

    # Ask what type of refresh to run
    if ask:
        # Check whether lock file already exists (which prevents concurrent updates on multi-seat configs)
        if xbmcvfs.exists(LOCK_FILE):
            xbmcgui.Dialog().notification(addonname, "Refresh currently in progress. Please try again later.",
                                          addon_resources + '/icon.png', 2500)
            return
        else:
            __logger("no lock file")
            menuItems = ['Refresh Series', 'Refresh Movies', 'Refresh Both']
            try:
                ret = xbmcgui.Dialog().select('Choose refresh type', menuItems)
                if ret == 0:
                    CATEGORY.append('series')
                elif ret == 1:
                    CATEGORY.append('movies')
                elif ret == 2:
                    CATEGORY.append('all')
            except KeyError:
                __logger("no refresh type selected")
                pass

    # Extract channels/playlists and counts from the database
    series_count = 0
    movies_count = 0
    if 'series' in CATEGORY or 'all' in CATEGORY:
        series_c_list = table_select("channel", "id, title", f"media_type = 'series' and disable_update is null",
                                     "title")
        series_p_list = table_select("playlist", "id, title", f"media_type = 'series' and disable_update is null",
                                     "title")
        series_count = len(series_c_list) + len(series_p_list)
    if 'movies' in CATEGORY or 'all' in CATEGORY:
        movies_c_list = table_select("channel", "id, title", f"media_type = 'movies' and removed = 0 and "
                                                             f"disable_update is null", "title")
        movies_p_list = table_select("playlist", "id, title", f"media_type = 'movies' and disable_update is null",
                                     "title")
        movies_count = len(movies_c_list) + len(movies_p_list)
    PARSER['total_steps'] = series_count + movies_count

    date_now = "substr(strftime('%s', 'now'), 1, 10)"

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
            if HIDE['progress'] is False:
                DP.create('Refreshing channel/playlist')
            if 'series' in CATEGORY or 'all' in CATEGORY:
                for c in series_c_list:
                    PARSER['steps'] += 1
                    __logger("about to parse: " + str(c[0]))
                    cp = ChannelProcessor('series', c[0], 'channel', title=c[1])
                    cp.refresh()
                for pl in series_p_list:
                    PARSER['steps'] += 1
                    __logger("about to parse: " + str(pl[0]))
                    cp = ChannelProcessor('series', pl[0], 'playlist', title=pl[1])
                    cp.refresh()
                # Store the last run time
                table_update("last_update", 'series', date_now)
            if 'movies' in CATEGORY or 'all' in CATEGORY:
                for c in movies_c_list:
                    PARSER['steps'] += 1
                    __logger("about to parse: " + str(c))
                    cp = ChannelProcessor('movies', c[0], 'channel', title=c[1])
                    cp.refresh()
                for pl in movies_p_list:
                    PARSER['steps'] += 1
                    __logger("about to parse: " + str(pl))
                    cp = ChannelProcessor('movies', pl[0], 'playlist', title=pl[1])
                    cp.refresh()
                # Store the last run time
                table_update("last_update", 'movies', date_now)

            # Delete the lock file
            if xbmcvfs.exists(LOCK_FILE):
                xbmcvfs.delete(LOCK_FILE)

            # Perform Kodi full library update
            if 'all' in CATEGORY or len(CATEGORY) > 1:
                xbmc.executebuiltin('UpdateLibrary(video)')
            # Perform kodi series library update
            elif 'series' in CATEGORY:
                xbmc.executebuiltin("UpdateLibrary(video,"+SERIES+")")
            # Perform kodi movies library update
            elif 'movies' in CATEGORY:
                xbmc.executebuiltin("UpdateLibrary(video,"+MOVIES+")")

            # Completion notification
            if addon.getSetting('display_notifications') == 'true' and not ask:
                xbmcgui.Dialog().notification(addonname, AddonString(30027), addon_resources+'/icon.png', 2500)
