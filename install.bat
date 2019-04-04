@echo off
set src=d:\Ringier\www\kodi\plugin.video.stream-cinema
set dest=c:\Users\bbaron\AppData\Roaming\Kodi\addons\plugin.video.stream-cinema
xcopy %src% %dest% /s /y /exclude:%src%\ex.txt
ping -n 5 127.0.0.1 > nul
