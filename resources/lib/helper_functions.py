import sqlite3
import xbmcgui
import requests
import datetime
import os
import time
import re
from resources.lib.variables import *

AddonString = xbmcaddon.Addon().getLocalizedString


def convert(n,*args):
    timediff = str(datetime.timedelta(seconds=max(n, 0))).split(':')
    if 'day' in timediff[0]:
        days = timediff[0].split(',')[0][:2].strip()
        hours = timediff[0].split(',')[1].strip()
        mins = timediff[1]
        return days + 'D' + hours + 'H' + mins + 'M'
    else:
        return timediff[0] + 'H' + timediff[1] + 'M'


def __get_token_reset():
    now = datetime.datetime.utcnow() - datetime.timedelta(hours=7)
    reset = now.replace(hour=0, minute=0, second=0, microsecond=0) + datetime.timedelta(days=1)
    seconds = (reset - now).seconds
    return seconds


def table_update(table, attributes, values, condition=None):
    # If the attributes parameter is a string then make it a list
    if isinstance(attributes, str):
        attributes = [attributes]

    # If the values parameter is a string then make it a list
    if isinstance(values, str):
        values = [values]

    # Connect to the database
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Construct the UPDATE statement
    update_stmt = f"UPDATE {table} SET "
    for i in range(len(attributes)):
        update_stmt += f"{attributes[i]} = {values[i]}"
        if i < len(attributes) - 1:
            update_stmt += ", "
    if condition:
        update_stmt += f" WHERE {condition}"
    __logger(update_stmt)

    # Execute the UPDATE statement
    cursor.execute(update_stmt)
    conn.commit()

    # Close the cursor and connection
    cursor.close()
    conn.close()


def sqlite_get_csv_list(sql):
    __logger(sql)
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(sql)
    result = cursor.fetchall()
    cursor.close()
    conn.close()

    result = [row[0] for row in result]

    return result


def table_select(table, attributes, condition=None, order_by=None, group_by=None):
    # Connect to the database
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Construct the SELECT statement
    select_stmt = f"SELECT {attributes} FROM {table}"
    if condition:
        select_stmt += f" WHERE {condition}"
    if group_by:
        select_stmt += f" GROUP BY {group_by}"
    if order_by:
        select_stmt += f" ORDER BY {order_by}"
    __logger(select_stmt)

    # Execute the SELECT statement and fetch the rows
    cursor.execute(select_stmt)
    rows = cursor.fetchall()

    # Close the cursor and connection
    cursor.close()
    conn.close()

    return rows


def remove_restricted_videos_and_files(delete='N'):

    # Construct SQL to determine restricted YouTube videos
    sql = f"select video_id from vwVideosMovies " \
          f"where (region_blocked like '%{COUNTRY}%' " \
          f"or (region_allowed not like '%{COUNTRY}%' and region_allowed <> '')) " \
          f"and kodi_files <> 'D'"

    # Update the kodi_files field to 'D' for the matching video_ids
    table_update("videos_custom", "kodi_files", "'D'", f"video_id in ({sql})")

    # Update the kodi_files field to 'D' for the matching video_ids
    restricted_videos = sqlite_get_csv_list(sql)

    # Delete the corresponding files
    if delete == 'Y':
        delete_movie_strm(restricted_videos)


def delete_movie_strm(del_list):
    # Compile the regular expression pattern
    pattern = re.compile(r"\[(.+?)\]\.[a-zA-Z0-9]{3,4}$")

    # Scan through the files
    for filename in os.listdir(MOVIES):
        # Use the regular expression to extract the string from the square brackets
        match = pattern.search(filename)
        if match:
            value = match.group(1)
            # Check if the value is in the list of known values
            if value in del_list:
                # Delete the file
                try:
                    os.remove(os.path.join(MOVIES, filename))
                    __logger(filename + " deleted successfully")
                except:
                    __logger(filename + " deletion failed")


def recursive_delete_dir(fullpath):
    # Thanks to <3
    # https://github.com/kodi-community-addons/script.skin.helper.skinbackup/blob/master/resources/lib/utils.py
    if PY_V >= 3:
        dirs, files = xbmcvfs.listdir(fullpath)
        for file in files:
            xbmcvfs.delete(os.path.join(fullpath, file))
        for directory in dirs:
            recursive_delete_dir(os.path.join(fullpath, directory))
        success = xbmcvfs.rmdir(fullpath)
        return success
    else:
        if not isinstance(fullpath, unicode):
            fullpath = fullpath.decode("utf-8")
        dirs, files = xbmcvfs.listdir(fullpath)
        for file in files:
            file = file.decode("utf-8")
            xbmcvfs.delete(os.path.join(fullpath, file))
        for directory in dirs:
            directory = directory.decode("utf-8")
            recursive_delete_dir(os.path.join(fullpath, directory))
        success = xbmcvfs.rmdir(fullpath)
        return success


def __logger(a):
    if addon.getSetting('logger') == 'true':
        xbmc.log("youtube2kodilibrary: " + str(a), level=xbmc.LOGINFO)


def __print(what):
    try:
        t = what + 1
        xbmcgui.Dialog().ok(addonname, AddonString(what))
    except TypeError:
        xbmcgui.Dialog().ok(addonname, what)


def __ask(name, *args):
    if args:
        header = args[0]
    else:
        header = ""
    kb = xbmc.Keyboard('default', header, True)
    kb.setDefault(name)
    kb.setHiddenInput(False)
    kb.doModal()
    if not kb.isConfirmed():
        return
    return kb.getText()


def scan_files_for_deletion(fullpath):
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


def c_download(req):
    url = req.replace("&key="+addon.getSetting('API_key'), '').split('?')
    url[1] = url[1]
    handle = url[0].split('/')[-1]
    cache_file = addon_path + '/cache/' + handle + '/' + url[1]
    if addon.getSetting('use_cache') == 'true':
        xbmcvfs.mkdirs(addon_path + '/cache/' + handle + '/')
        if xbmcvfs.exists(cache_file[:250]):
            time.sleep(0.2) #sleep timer for debugging
            if PY_V >= 3:                                # Python 3 v19+
                with open(cache_file[:250], 'r') as f:   # (READ)
                    return json.load(f)
            else:
                f = xbmcvfs.File(cache_file[:250])       # PYTHON 2 v18+
                ret_json = json.loads(f.read())          # (READ)
                f.close()
                return ret_json
        else:
            requrl = requests.get(req)
            reply = json.loads(requrl.content)
            try:
                if 'error' in reply:
                    e_reason = reply['error']['errors'][0]['reason']
                    __logger(e_reason)
                    if e_reason == 'quotaExceeded':
                        e_message = "The request cannot be completed because you have exceeded your quota."
                    elif e_reason == 'backendError':
                        e_message = "Problem at YouTube's end. Try again later"
                    else:
                        e_message = 'Undefined error.'
                    xbmcgui.Dialog().notification(addonname, e_reason + ': ' + e_message, addon_resources +
                                                  '/icon.png', 10000)
                    if xbmcvfs.exists(LOCK_FILE):
                        xbmcvfs.delete(LOCK_FILE)
                    raise SystemExit("error: " + e_reason)
            except NameError:
                pass

            if PY_V >= 3:                                # Python 3
                with open(cache_file[:250], mode='w', encoding='UTF-8', errors='strict', buffering=1) as file:
                    file.write(json.dumps(reply))
                    file.close()
                return reply
            else:
                f = xbmcvfs.File(cache_file[:250], 'w')  #Python 2
                f.write(json.dumps(reply))
                f.close()
                return reply
    else:
        requrl = requests.get(req)
        reply = json.loads(requrl.content)
    try:
        if 'error' in reply:
            e_reason = reply['error']['errors'][0]['reason']
            __logger(e_reason)
            if e_reason == 'quotaExceeded':
                e_message = "The request cannot be completed because you have exceeded your quota."
            elif e_reason == 'backendError':
                e_message = "Problem at YouTube's end. Try again later"
            else:
                e_message = 'Undefined error.'
            xbmcgui.Dialog().notification(addonname, e_reason + ': ' + e_message, addon_resources +
                                          '/icon.png', 10000)
            if xbmcvfs.exists(LOCK_FILE):
                xbmcvfs.delete(LOCK_FILE)
    except NameError:
        pass
    return reply

