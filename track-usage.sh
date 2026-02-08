#!/usr/bin/env bash
#
# track-usage.sh — Track active window usage time on X11.
# Polls the focused window every second and accumulates time per application.
# Press Ctrl+C to stop and print a summary.

set -euo pipefail

POLL_INTERVAL=1  # seconds

declare -A usage_secs   # app_class -> total seconds
declare -A app_titles   # app_class -> last seen window title
start_time=$(date +%s)

format_duration() {
    local total=$1
    local h=$((total / 3600))
    local m=$(( (total % 3600) / 60 ))
    local s=$((total % 60))
    printf "%dh %02dm %02ds" "$h" "$m" "$s"
}

print_summary() {
    local now
    now=$(date +%s)
    local elapsed=$((now - start_time))

    echo ""
    echo "========================================"
    echo " Window Usage Summary"
    echo " Tracked for: $(format_duration $elapsed)"
    echo "========================================"
    printf "%-6s  %-24s  %s\n" "TIME" "APPLICATION" "LAST TITLE"
    echo "----------------------------------------"

    # Sort by usage time descending
    for app in "${!usage_secs[@]}"; do
        echo "${usage_secs[$app]} ${app}"
    done | sort -rn | while read -r secs app; do
        printf "%-6s  %-24s  %s\n" \
            "$(format_duration "$secs")" \
            "$app" \
            "${app_titles[$app]:-(unknown)}"
    done

    echo "========================================"
}

# Make app_titles available inside the sort pipe by using a temp approach
print_summary() {
    local now
    now=$(date +%s)
    local elapsed=$((now - start_time))

    echo ""
    echo "========================================"
    echo " Window Usage Summary"
    echo " Tracked for: $(format_duration $elapsed)"
    echo "========================================"
    printf "%-10s  %-24s  %s\n" "TIME" "APPLICATION" "LAST TITLE"
    printf "%-10s  %-24s  %s\n" "----" "-----------" "----------"

    # Build sorted output in the current shell
    local sorted_apps=()
    for app in "${!usage_secs[@]}"; do
        sorted_apps+=("${usage_secs[$app]}|${app}")
    done

    IFS=$'\n' sorted_apps=($(printf '%s\n' "${sorted_apps[@]}" | sort -t'|' -k1 -rn))
    unset IFS

    for entry in "${sorted_apps[@]}"; do
        local secs="${entry%%|*}"
        local app="${entry#*|}"
        local title="${app_titles[$app]:-(unknown)}"
        # Truncate title to 50 chars
        if [ ${#title} -gt 50 ]; then
            title="${title:0:47}..."
        fi
        printf "%-10s  %-24s  %s\n" \
            "$(format_duration "$secs")" \
            "$app" \
            "$title"
    done

    echo "========================================"
}

trap print_summary EXIT

echo "Tracking window usage... Press Ctrl+C to stop."
echo ""

prev_app=""
while true; do
    # Get active window id; skip if no window is focused
    win_id=$(xdotool getactivewindow 2>/dev/null) || { sleep "$POLL_INTERVAL"; continue; }

    # Get the WM_CLASS (application identifier)
    app_class=$(xprop -id "$win_id" WM_CLASS 2>/dev/null \
        | sed -n 's/.*= "[^"]*", "\([^"]*\)"/\1/p') || app_class="unknown"

    # Get the window title
    win_title=$(xdotool getwindowname "$win_id" 2>/dev/null) || win_title=""

    if [ -z "$app_class" ]; then
        app_class="unknown"
    fi

    # Accumulate time
    usage_secs[$app_class]=$(( ${usage_secs[$app_class]:-0} + POLL_INTERVAL ))
    app_titles[$app_class]="$win_title"

    # Print a live status line when the active app changes
    if [ "$app_class" != "$prev_app" ]; then
        local_title="$win_title"
        if [ ${#local_title} -gt 60 ]; then
            local_title="${local_title:0:57}..."
        fi
        printf "\r\033[K[%s] Active: %-20s  %s\n" \
            "$(date +%H:%M:%S)" "$app_class" "$local_title"
        prev_app="$app_class"
    fi

    sleep "$POLL_INTERVAL"
done
