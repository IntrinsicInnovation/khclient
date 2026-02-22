
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
        > "$LOGDIR/client_$i.log" 2>&1 &

    sleep 0.05
done

echo "All clients launched."

