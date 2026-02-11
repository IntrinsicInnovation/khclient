@echo off

for /L %%i in (1,1,50) do (
    start "" wsl bash -lc "cd /mnt/d/Development/Bitcoin/1000btcchallenge/DistributedKeyHunt/client/khclient/khclient && ./khclient"
    timeout /t 1 >nul
)

echo Done.
