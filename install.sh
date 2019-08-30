#/bin/sh
# do NOT use this script from XBMC addons directory, it is intented for development only
DESTDIR=`realpath ~/Library/Application\ Support/Kodi/addons/plugin.video.stream-cinema`

rm -rf "${DESTDIR}"
mkdir -p "${DESTDIR}"
cp -vfa * "${DESTDIR}"
