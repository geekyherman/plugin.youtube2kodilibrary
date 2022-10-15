""" 
SERVICE FILE
"""
import time
import json
import xbmc
import xbmcvfs
import xbmcaddon
import sys
import requests


addonID = xbmcaddon.Addon().getAddonInfo('id')
PY_V = sys.version_info[0]

if PY_V >= 3:
    addon_path = xbmcvfs.translatePath("special://profile/addon_data/"+addonID)
else:
    addon_path = xbmc.translatePath("special://profile/addon_data/"+addonID)

if xbmcvfs.exists(addon_path+'//config.json'):
    with open(addon_path+'//config.json', 'r') as f:
        CONFIG = json.load(f)

if __name__ == '__main__':
    monitor = xbmc.Monitor()
    while not monitor.abortRequested():
        # Sleep/wait for abort for 60 seconds
        if monitor.waitForAbort(60):
            # Abort was requested while waiting. We should exit
            break
        if xbmcaddon.Addon().getSetting('auto_refresh') == 'true':
            xbmc.executebuiltin('RunPlugin(plugin://'+addonID+'/?mode=Refresh)')
