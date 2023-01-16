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


DP = xbmcgui.DialogProgress()
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
AddonString = xbmcaddon.Addon().getLocalizedString

YOUTUBE_DIR = HOME
SERIES = YOUTUBE_DIR+'series'
MOVIES = YOUTUBE_DIR+'movies'
LOCK_FILE = addon_path + '\\lock.txt'
CATEGORY = []
VIDEOS = []
USE_INVIDIOUS = []
HIDE = {'progress': False}
MIN_MINUTES = int(addon.getSetting('minimum_minutes'))
IGNORE_SHORTS = addon.getSetting('toggle_ignore_shorts')
REGEX_STRING = addon.getSetting('movie_re')
DISCOVERY_CHANNEL_LANGUAGE = addon.getSetting('discovery_channel_language')
DISCOVERY_MAX_CHANNELS = addon.getSetting('discovery_max_channels')
INVIDIOUS_CLIENT = 'plugin://plugin.video.invidious/?action=play_video&video_id='
DB_NAME = addon_path + "\\youtube.db"
PARSER = {'total_steps': 0, 'steps': 0, 'refresh_type': 'multi', 'update_type': 'refresh', 'percent': 0}


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
