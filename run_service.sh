#!/bin/bash

while true; do
    echo "[$(date)] Starting Python server..."

    # Start the server
    python -m src.agent_red.queue_server

    # Get the exit status code
    EXIT_CODE=$?

    echo "[$(date)] Server exited abnormally (exit code: $EXIT_CODE), preparing to restart..."

    # !!! Very important: clean up leftover Docker containers !!!
    # Find containers matching specific keywords and force-remove them,
    # to prevent zombie containers from consuming resources
    echo "Cleaning up leftover experiment containers..."
    ./refresh_state.sh

    # Wait 5 seconds to ensure ports (e.g. 8080) are fully released
    echo "Restarting service after 5 seconds..."
    sleep 5
done