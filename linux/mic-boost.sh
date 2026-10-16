#!/bin/sh

DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
STATE="$DIR/mic-boost.state"
PIDF="$DIR/mic-boost.pid"
CONF="$DIR/mic-boost-chain.conf"
LOCK="$DIR/mic-lock.target"
HERE="$(dirname "$(readlink -f "$0")")"
TEMPLATE="${MIC_BOOST_CHAIN:-$HERE/mic-boost-chain.conf}"
NODE=mic_boost

vol() {
    pactl get-source-volume "$1" 2>/dev/null | grep -o '[0-9]*%' | head -1 | tr -d %
}

note() {
    command -v notify-send >/dev/null 2>&1 &&
        notify-send -a mic-boost -t 1500 -i "$1" "Mic BOOST" "$2"
}

lock() {
    [ -f "$LOCK" ] && printf '%s' "$1" > "$LOCK"
}

has_node() {
    pactl list short sources | cut -f2 | grep -qx "$NODE"
}

stop_chain() {
    [ -f "$PIDF" ] && kill "$(cat "$PIDF")" 2>/dev/null
    rm -f "$PIDF"
}

if [ -f "$STATE" ]; then
    read -r src v < "$STATE"
    rm -f "$STATE"
    stop_chain
    case "$v" in ''|*[!0-9]*) v=100 ;; esac
    if [ -n "$src" ]; then
        lock "$v"
        pactl set-default-source "$src"
        pactl set-source-volume "$src" "${v}%"
    fi
    note audio-input-microphone "OFF · ${v}%"
    exit 0
fi

src=$(pactl get-default-source)
if [ -z "$src" ] || [ "$src" = "$NODE" ]; then
    note dialog-error "Нет микрофона по умолчанию"
    exit 1
fi
if [ ! -f "$TEMPLATE" ]; then
    note dialog-error "Нет $TEMPLATE"
    exit 1
fi

v=$(vol "$src")
printf '%s %s' "$src" "${v:-100}" > "$STATE"
sed "s|@SOURCE@|$src|" "$TEMPLATE" > "$CONF"

setsid -f sh -c 'echo $$ > "$1"; exec pipewire -c "$2"' _ "$PIDF" "$CONF" >/dev/null 2>&1
i=0
until has_node; do
    i=$((i + 1))
    [ "$i" -gt 30 ] && break
    sleep 0.1
done

if ! has_node; then
    stop_chain
    rm -f "$STATE"
    note dialog-error "Фильтр не запустился (установлен swh-plugins?)"
    exit 1
fi

lock 100
pactl set-source-mute "$src" 0
pactl set-source-volume "$src" 100%
pactl set-default-source "$NODE"
pactl set-source-volume "$NODE" 100%
note audio-input-microphone-high "ON"
