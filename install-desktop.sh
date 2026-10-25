#!/bin/sh
set -eu
cd "$(dirname "$0")"
project_dir=$PWD
launcher_dir=${XDG_DATA_HOME:-"$HOME/.local/share"}/applications
mkdir -p "$launcher_dir"
cat > "$launcher_dir/habit-garden.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Сад привычек
Comment=Ежедневные задания и напоминания
Exec=$project_dir/run.sh
Icon=$project_dir/src/habit_garden/static/icon.svg
Terminal=false
Categories=Utility;Office;
StartupNotify=true
StartupWMClass=habit-garden
EOF
echo "Ярлык приложения создан: $launcher_dir/habit-garden.desktop"
if [ "${1:-}" = "--autostart" ]; then
  autostart_dir=${XDG_CONFIG_HOME:-"$HOME/.config"}/autostart
  mkdir -p "$autostart_dir"
  cat > "$autostart_dir/habit-garden.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Сад привычек — напоминания
Comment=Фоновые напоминания о привычках
Exec=$project_dir/run.sh background
Icon=$project_dir/src/habit_garden/static/icon.svg
Terminal=false
X-GNOME-Autostart-enabled=true
EOF
  echo "Автозапуск напоминаний включён: $autostart_dir/habit-garden.desktop"
fi
