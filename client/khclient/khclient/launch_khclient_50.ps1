for ($i=1; $i -le 50; $i++) {
    Start-Process wsl -ArgumentList "bash -lc 'cd /mnt/d/Development/Bitcoin/1000btcchallenge/DistributedKeyHunt/client/khclient/khclient && ./khclient'"
}

Write-Host "Launched 50 khclient instances."
