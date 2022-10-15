# -*- coding: utf-8 -*-
import xbmcaddon
import xbmc
import xbmcvfs
import sys
import json
import urllib
import xbmcgui

addon = xbmcaddon.Addon()
addonname = addon.getAddonInfo('name')
addonID = addon.getAddonInfo('id')
addon_resources = addon.getAddonInfo("path") + '/resources/'
PDIALOG = xbmcgui.DialogProgress()

PY_V = sys.version_info[0]
if PY_V >= 3:
    addon_path = xbmcvfs.translatePath("special://profile/addon_data/" + addonID)
    args = urllib.parse.parse_qs(sys.argv[2][1:])
    HOME = xbmcvfs.translatePath("special://profile/library/YT/")
else:
    addon_path = xbmc.translatePath("special://profile/addon_data/" + addonID)
    args = str(sys.argv[2][1:])
    HOME = xbmc.translatePath("special://profile/library/YT/")

base_url = sys.argv[0]
addon_handle = int(sys.argv[1])


YOUTUBE_DIR = HOME
CHANNELS = YOUTUBE_DIR+'series'
MOVIES = YOUTUBE_DIR+'movies'
MUSIC_VIDEOS = YOUTUBE_DIR+'music_videos'
LOCK_FILE = addon_path + '\\lock.txt'
CATEGORY = []
VIDEOS = []
VIDEOS_TO_DELETE = []
VIDEO_DURATION = {}
PUBLISHED_AT = {}
EN_TITLE = {}
HIDE = {'progress': False}
AddonString = xbmcaddon.Addon().getLocalizedString

if addon.getSetting('toggle_ignore_restricted') == 'true':
    COUNTRY = addon.getSetting('YT_country')
else:
    COUNTRY = ''

if addon.getSetting('YT_client') == "0":
    YOUTUBE_CLIENT = 'plugin://plugin.video.youtube/play/?video_id='
elif addon.getSetting('YT_client') == "1":
    YOUTUBE_CLIENT = 'plugin://plugin.video.tubed/?mode=play&video_id='
else:
    sys.exit("YouTube Client is not specified in settings.")

config_file = addon_path + '\\config.json'
if xbmcvfs.exists(config_file):
    if PY_V >= 3:
        with xbmcvfs.File(config_file) as f:     # PYTHON 3 v19+
            CONFIG = json.load(f)
    else:
        f = xbmcvfs.File(config_file)            # PYTHON 2 v18+
        CONFIG = json.loads(f.read())
        f.close()
else:
    CONFIG = {'channels': {}, 'movies': {}, 'movies_playlists': {}, 'music_videos': {}, 'playlists': {}, 'scan_date': {}}

index_file = addon_path + '\\index.json'
if xbmcvfs.exists(index_file):
    if PY_V >= 3:
        with xbmcvfs.File(index_file) as f:     # PYTHON 3 v19+
            INDEX = json.load(f)
    else:
        f = xbmcvfs.File(index_file)            # PYTHON 2 v18+
        INDEX = json.loads(f.read())
        f.close()
else:
    INDEX = []

PARSER = {'total_steps': 0, 'steps': 0, 'refresh_type': 'multi', 'update_type': 'refresh', 'percent': 0}
