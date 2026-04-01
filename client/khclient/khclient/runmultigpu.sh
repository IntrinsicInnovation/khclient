#!/bin/bash

APP="./khclientimproved"
LOGDIR="./logs"
mkdir -p $LOGDIR

PARAMS=(
"--range 0x0:0x1ffffffff"
"--range 0x200000000:0x3ffffffff"
"--range 0x400000000:0x5ffffffff"
"--range 0x600000000:0x7ffffffff"
"--range 0x800000000:0x9ffffffff"
"--range 0xa00000000:0xbffffffff"
"--range 0xc00000000:0xdffffffff"
"--range 0xe00000000:0xfffffffff"
)

for GPU in {0..7}
do
    echo "Starting GPU $GPU"

    CUDA_VISIBLE_DEVICES=$GPU \
    $APP -gpu $GPU \
    > $LOGDIR/keyhunt_gpu${GPU}.log 2>&1 &
done

echo "All instances running."