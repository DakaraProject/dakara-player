mkdir ".\mpv"
cd ".\mpv"
$rss_link = "https://sourceforge.net/projects/mpv-player-windows/rss?path=/libmpv"
$result = [xml](New-Object System.Net.WebClient).DownloadString($rss_link)
$latest = $result.rss.channel.item.link[0]
$filename = [System.Uri]::UnescapeDataString($latest.split("/")[-2])
$download_link = "http://download.sourceforge.net/mpv-player-windows/" + $filename
Invoke-WebRequest -Uri $download_link -UserAgent [Microsoft.PowerShell.Commands.PSUserAgent]::FireFox -OutFile $filename
cmd /c 7z x -y $filename
$env:Path += ";" + (Get-Location).Path
cd ".."
