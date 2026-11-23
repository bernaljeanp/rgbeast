#!/bin/sh
# Instalador universal de RGBEAST (Bazzite, Silverblue, SteamOS y cualquier distro).
#
#   ./install.sh               instala la app en tu usuario (~/.local) y, si quieres,
#                              el servicio de hardware (pide la contraseña con pkexec)
#   ./install.sh --uninstall   lo quita todo
#
# No necesita rpm-ostree ni cambiar /usr: la app vive en ~/.local/share/rgbeast.
set -eu

SRC=$(dirname "$(readlink -f "$0")")
DATA=${XDG_DATA_HOME:-$HOME/.local/share}
APP=$DATA/rgbeast
BIN=$HOME/.local/bin
CONFIG=${XDG_CONFIG_HOME:-$HOME/.config}

say() { printf '\033[1m>> %s\033[0m\n' "$*"; }

if [ "$(id -u)" -eq 0 ]; then
    echo "Ejecuta el instalador con tu usuario normal, sin sudo." >&2
    exit 1
fi

if [ "${1:-}" = "--uninstall" ]; then
    systemctl --user disable --now rgbeast-agent.service 2>/dev/null || true
    rm -f "$CONFIG/systemd/user/rgbeast-agent.service" "$CONFIG/autostart/rgbeast.desktop"
    pkill -f "rgbeast.app --bandeja" 2>/dev/null || true
    rm -rf "$APP"
    rm -f "$BIN/rgbeast" "$BIN/rgbeast-agent"
    rm -f "$DATA/applications/rgbeast.desktop" "$DATA/applications/rgbeast-teclas.desktop"
    rm -f "$DATA/icons/hicolor/scalable/apps/rgbeast.svg" "$DATA/icons/hicolor/scalable/status/rgbeast-symbolic.svg"
    say "App desinstalada (tu configuración en $CONFIG/rgbeast se conserva)."
    if systemctl is-active --quiet rgbeast-helper.service 2>/dev/null; then
        say "Quitando el servicio de hardware (pedirá tu contraseña)..."
        pkexec "$SRC/helper/install.sh" --uninstall || true
    fi
    exit 0
fi

# La app se llamó Rigcore y antes Vórtice: quita los restos de las instalaciones con
# esos nombres. Se recuerda si el agente de juegos y el autoarranque estaban activos
# para dejarlos igual con el nombre nuevo; la configuración la migra la propia app.
KEEP_AGENT=0
KEEP_AUTOSTART=0
for old in rigcore vortice; do
    if systemctl --user is-enabled --quiet "$old-agent.service" 2>/dev/null; then KEEP_AGENT=1; fi
    if [ -f "$CONFIG/autostart/$old.desktop" ]; then KEEP_AUTOSTART=1; fi
    systemctl --user disable --now "$old-agent.service" 2>/dev/null || true
    pkill -f "$old.app --bandeja" 2>/dev/null || true
    # Atajos globales (F6/F7/F9) registrados con el nombre viejo: se liberan para
    # que el nuevo pueda usar las mismas teclas.
    for action in lights stealth boost; do
        busctl --user call org.kde.kglobalaccel /kglobalaccel org.kde.KGlobalAccel \
            unregister ss "$old-teclas.desktop" "$action" >/dev/null 2>&1 || true
    done
    rm -rf "${DATA:?}/$old"
    rm -f "$CONFIG/systemd/user/$old-agent.service" "$CONFIG/autostart/$old.desktop" \
          "$BIN/$old" "$BIN/$old-agent" \
          "$DATA/applications/$old.desktop" "$DATA/applications/$old-teclas.desktop" \
          "$DATA/icons/hicolor/scalable/apps/$old.svg" "$DATA/icons/hicolor/scalable/status/$old-symbolic.svg"
done
systemctl --user daemon-reload 2>/dev/null || true

command -v python3 >/dev/null || { echo "Falta python3." >&2; exit 1; }
python3 -c 'import sys; sys.exit(sys.version_info < (3, 10))' || { echo "Se necesita Python 3.10 o superior." >&2; exit 1; }

say "Creando el entorno de RGBEAST en $APP"
python3 -m venv "$APP/venv"
"$APP/venv/bin/pip" install -q --upgrade pip
say "Instalando RGBEAST y PySide6 (puede tardar unos minutos la primera vez)..."
"$APP/venv/bin/pip" install -q "$SRC"

mkdir -p "$BIN" "$DATA/applications" "$DATA/icons/hicolor/scalable/apps" "$DATA/icons/hicolor/scalable/status"
cat > "$BIN/rgbeast" <<EOF
#!/bin/sh
# -P: no cargar código de la carpeta actual (p. ej. abrir rgbeast desde el repo)
exec "$APP/venv/bin/python" -P -m rgbeast.app "\$@"
EOF
cat > "$BIN/rgbeast-agent" <<EOF
#!/bin/sh
exec /usr/bin/python3 -I "$APP/venv/lib/python$(python3 -c 'import sys;print(f"{sys.version_info[0]}.{sys.version_info[1]}")')/site-packages/rgbeast/agent.py" "\$@"
EOF
chmod +x "$BIN/rgbeast" "$BIN/rgbeast-agent"

sed "s|^Exec=rgbeast|Exec=$BIN/rgbeast|" "$SRC/packaging/data/rgbeast.desktop" > "$DATA/applications/rgbeast.desktop"
cp "$SRC/rgbeast/qml/icon.svg" "$DATA/icons/hicolor/scalable/apps/rgbeast.svg"
cp "$SRC/rgbeast/qml/icon-symbolic.svg" "$DATA/icons/hicolor/scalable/status/rgbeast-symbolic.svg"
command -v update-desktop-database >/dev/null && update-desktop-database "$DATA/applications" 2>/dev/null || true
command -v kbuildsycoca6 >/dev/null && kbuildsycoca6 >/dev/null 2>&1 || true
say "App instalada: búscala como «RGBEAST» en el menú, o ejecuta: rgbeast"

if [ "$KEEP_AUTOSTART" = 1 ]; then
    mkdir -p "$CONFIG/autostart"
    cat > "$CONFIG/autostart/rgbeast.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=RGBEAST
Comment=Centro de control del portátil (bandeja)
Exec=$BIN/rgbeast --bandeja
Icon=rgbeast
X-GNOME-Autostart-enabled=true
X-KDE-autostart-after=panel
EOF
fi
if [ "$KEEP_AGENT" = 1 ]; then
    mkdir -p "$CONFIG/systemd/user"
    cat > "$CONFIG/systemd/user/rgbeast-agent.service" <<EOF
[Unit]
Description=RGBEAST - perfiles por juego
After=graphical-session.target

[Service]
ExecStart=$BIN/rgbeast-agent
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
EOF
    systemctl --user daemon-reload
    systemctl --user enable --now rgbeast-agent.service && say "Agente de juegos activo con el nombre nuevo."
fi

if systemctl is-active --quiet rgbeast-helper.service 2>/dev/null \
   || systemctl is-active --quiet rigcore-helper.service 2>/dev/null \
   || systemctl is-active --quiet vortice-helper.service 2>/dev/null; then
    say "El servicio de hardware ya está instalado. Actualizándolo (pedirá tu contraseña)..."
    pkexec "$SRC/helper/install.sh" >/dev/null && say "Servicio actualizado."
else
    printf '\n¿Instalar el servicio de hardware (ventiladores, batería, luces persistentes)?\n'
    printf 'Necesita tu contraseña de administrador. [S/n] '
    read -r answer || answer=n
    case "$answer" in
        [nN]*) say "Sin servicio: podrás ver temperaturas y cambiar modos; instálalo luego con: pkexec $SRC/helper/install.sh" ;;
        *) pkexec "$SRC/helper/install.sh" >/dev/null && say "Servicio instalado y activo." ;;
    esac
fi
