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


def __save(data=CONFIG, file=config_file):
    dump = json.dumps(data, sort_keys=True, indent=4, separators=(',', ': '))
    if PY_V >= 3:                         #Python 3
        with xbmcvfs.File(file, 'w') as f:
            f.write(dump)
    else:
        f = xbmcvfs.File(file, 'w')       #Python 2
        f.write(dump)
        f.close()


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


def __get_playlists(channel_id):
    channel_url = 'https://www.googleapis.com/youtube/v3/playlists?part=contentDetails,id,snippet&maxResults=50&channelId='+ channel_id + "&key="+addon.getSetting('API_key')
    reply = c_download(channel_url)
    return reply


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


def __yt_duration(in_time):
    duration = 1
    if "PT" not in in_time:
        return str(0)
    time = in_time.split("PT")[1]
    if 'H' in time and 'M' in time and 'S' in time:
        duration = int(time.split("H")[0])*60 + int(time.split("H")[1].split("M")[0])
    elif 'H' in time and 'M' in time:
        duration = int(time.split("H")[0])*60 + int(time.split("H")[1].split("M")[0])
    elif 'H' in time and 'S' in time:
        duration = int(time.split("H")[0])*60
    elif 'M' in time and 'S' in time:
        duration = int(time.split("M")[0])
    return str(duration)


def __clean_char(title, trim_pos):
    if trim_pos == 'B':
        try:
            while title[0] in (' ', '-', '|', '(', ')', '[', ']') and len(title) > 1:
                title = title[1:]
        except IndexError:
            pass
    if trim_pos == 'E':
        try:
            while title[-1] in (' ', '-', '|', '(', ')', '[', ']') and len(title) > 1:
                title = title[:-1]
        except IndexError:
            pass
    return title


def __scrub_text(string):
    if PY_V >= 3:  # Python 3
        text = re.compile(u"[^\U00000000-\U0000d7ff\U0000e000-\U0000ffff]", flags=re.UNICODE)
        scrub_text = text.sub(u"", string)
    else:
        text = re.compile(u"[^\U00000000-\U0000d7ff\U0000e000-\U0000ffff]", flags=re.UNICODE)
        scrub_text = text.sub(u'', unicode(string, 'utf-8'))
    return scrub_text


def __upgrade_refresh():
    if 'scan_date' not in CONFIG:
        CONFIG['scan_date'] = {}
        CONFIG['scan_date']['series'] = CONFIG['last_scan']
        CONFIG['scan_date']['movies'] = CONFIG['last_scan']
        CONFIG['scan_date']['music'] = CONFIG['last_scan']
    CONFIG.pop('last_scan')
    __save()
