#!/bin/bash
set -e

CLIENT="./khclientimproved"
INSTANCES=10
LOGDIR="logs"

# absolute path for found file
FOUND_FILE="$(pwd)/foundNEW.txt"

mkdir -p "$LOGDIR"

CORES=$(nproc)

echo "Detected $CORES CPU cores"
echo "Launching $INSTANCES khclient instances..."

for ((i=0; i<INSTANCES; i++))
do
    CORE=$((i % CORES))

    echo "Starting client $i on core $CORE"

    taskset -c $CORE \
        $CLIENT -o "$FOUND_FILE" \
        2>&1 | sed "s/^/[client-$i] /" | tee -a "$LOGDIR/client_$i.log"
        #> "$LOGDIR/client_$i.log" 2>&1 &

    sleep 0.15
done

echo "All clients launched."

wait