#!/bin/bash

# Define the expected IP address
EXPECTED_IP="192.168.44.104"

# Check if a sleep interval was provided as an argument, default to 5 seconds if not
SLEEP_INTERVAL=${1:-5}

echo "Starting DNS monitoring... Checking every $SLEEP_INTERVAL seconds."

# Infinite loop to check DNS resolution at the given interval
while true; do
    if dig -t a nextcloud.trygve.site | grep -q "$EXPECTED_IP"; then
        echo "$(date): DNS resolution is correct. No action needed."
    else
        echo "$(date): DNS resolution incorrect. Restarting NetworkManager..."
        sudo systemctl restart NetworkManager
    fi

    # Wait for the user-defined interval before checking again
    sleep "$SLEEP_INTERVAL"
done
