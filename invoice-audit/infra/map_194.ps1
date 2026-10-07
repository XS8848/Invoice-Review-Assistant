# 端口映射：192.168.110.194（当前IP）为主，239 备用保留。需管理员。
$ErrorActionPreference = 'Continue'
$log = '$env:USERPROFILE\lan_expose.log'
"MAP START $(Get-Date)" | Out-File $log

foreach ($port in 8000, 9000, 9001) {
  netsh interface portproxy delete v4tov4 listenport=$port listenaddress=192.168.110.194 2>$null | Out-Null
  netsh interface portproxy add v4tov4 listenport=$port listenaddress=192.168.110.194 connectaddress=127.0.0.1 connectport=$port
  "portproxy 194:$port -> $LASTEXITCODE" | Out-File $log -Append

  netsh interface portproxy delete v4tov4 listenport=$port listenaddress=192.168.110.239 2>$null | Out-Null
  netsh interface portproxy add v4tov4 listenport=$port listenaddress=192.168.110.239 connectaddress=127.0.0.1 connectport=$port
  "portproxy 239:$port -> $LASTEXITCODE" | Out-File $log -Append

  netsh advfirewall firewall delete rule name="InvoiceAudit-$port" 2>$null | Out-Null
  netsh advfirewall firewall add rule name="InvoiceAudit-$port" dir=in action=allow protocol=TCP localport=$port
  "firewall $port -> $LASTEXITCODE" | Out-File $log -Append
}

netsh interface portproxy show all | Out-File $log -Append
"MAP END $(Get-Date)" | Out-File $log -Append
