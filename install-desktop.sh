#!/bin/sh
set -eu
cd "$(dirname "$0")"
project_dir=$PWD
bin_dir="$HOME/.local/bin"
bin_launcher="$bin_dir/habit-garden"
mkdir -p "$bin_dir"
if [ -e "$bin_launcher" ] || [ -L "$bin_launcher" ]; then
  if [ "$(readlink -f "$bin_launcher")" != "$project_dir/run.sh" ]; then
    echo "Команда уже занята: $bin_launcher" >&2
    exit 1
  fi
fi
ln -sfn "$project_dir/run.sh" "$bin_launcher"
echo "Команда установлена: $bin_launcher"
if [ -f "$HOME/.bashrc" ] && ! grep -Fq '# habit-garden: user commands' "$HOME/.bashrc"; then
  cat >> "$HOME/.bashrc" <<'EOF'

# habit-garden: user commands
case ":$PATH:" in
  *":$HOME/.local/bin:"*) ;;
  *) export PATH="$HOME/.local/bin:$PATH" ;;
esac
EOF
  echo "Путь к команде добавлен в ~/.bashrc; откройте новый терминал."
fi
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
