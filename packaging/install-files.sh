#!/bin/sh
# Copia los archivos de sistema de RGBEAST a un árbol de destino (paquetes de distro).
# Uso: install-files.sh DESTDIR LIBEXECDIR   (p. ej. /usr/lib/rgbeast o /usr/libexec/rgbeast)
set -eu
DEST=$1; LIBEXEC=$2
SRC=$(dirname "$(readlink -f "$0")")/..

install -Dm755 "$SRC/helper/rgbeast-helper" "$DEST$LIBEXEC/rgbeast-helper"
for m in lights.py fancurve.py fans.py; do
    install -Dm644 "$SRC/rgbeast/$m" "$DEST$LIBEXEC/$m"
done
sed "s|@LIBEXECDIR@|$LIBEXEC|g" "$SRC/helper/rgbeast-helper.service" \
    | install -Dm644 /dev/stdin "$DEST/usr/lib/systemd/system/rgbeast-helper.service"
# Política D-Bus: en Arch y Fedora los administradores son el grupo wheel.
awk '{ if ($0 ~ /@ADMIN_POLICIES@/) {
         print "  <policy group=\"wheel\">"
         print "    <allow send_destination=\"io.github.bernaljeanp.Rgbeast.Helper\" send_interface=\"io.github.bernaljeanp.Rgbeast.Helper1\"/>"
         print "    <allow send_destination=\"io.github.bernaljeanp.Rgbeast.Helper\" send_interface=\"org.freedesktop.DBus.Introspectable\"/>"
         print "    <allow send_destination=\"io.github.bernaljeanp.Rgbeast.Helper\" send_interface=\"org.freedesktop.DBus.Properties\"/>"
         print "    <allow send_destination=\"io.github.bernaljeanp.Rgbeast.Helper\" send_interface=\"org.freedesktop.DBus.Peer\"/>"
         print "  </policy>"
       } else print }' "$SRC/helper/io.github.bernaljeanp.Rgbeast.Helper.conf" \
    | install -Dm644 /dev/stdin "$DEST/usr/share/dbus-1/system.d/io.github.bernaljeanp.Rgbeast.Helper.conf"
install -Dm644 "$SRC/helper/70-rgbeast-alienware.hwdb" "$DEST/usr/lib/udev/hwdb.d/70-rgbeast-alienware.hwdb"
install -Dm644 "$SRC/packaging/data/rgbeast-agent.service" "$DEST/usr/lib/systemd/user/rgbeast-agent.service"
install -Dm644 "$SRC/packaging/data/rgbeast.desktop" "$DEST/usr/share/applications/rgbeast.desktop"
install -Dm644 "$SRC/rgbeast/qml/icon.svg" "$DEST/usr/share/icons/hicolor/scalable/apps/rgbeast.svg"
install -Dm644 "$SRC/rgbeast/qml/icon-symbolic.svg" "$DEST/usr/share/icons/hicolor/scalable/status/rgbeast-symbolic.svg"
