# 局域网端口映射（需管理员权限，UAC 弹出时请点“是”）
# 自动探测本机当前局域网 IPv4，把 8000/9000/9001 转发到 WSL2（经 127.0.0.1 回环，不受 WSL IP 变化影响）
# 幂等：清理历史失效地址规则；额外地址可传 -ExtraIps "192.168.110.239"
param([string]$ExtraIps = "")

$ErrorActionPreference = 'Continue'
$log = '$env:USERPROFILE\lan_expose.log'

# 1. 探测本机当前局域网 IPv4（排除 WSL/虚拟网卡）
$current = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
  Where-Object { $_.IPAddress -like '192.168.*' -and $_.InterfaceAlias -notmatch 'WSL|vEthernet' } |
  Sort-Object { if ($_.PrefixOrigin -eq 'Manual') { 0 } else { 1 } } |
  Select-Object -First 1 -ExpandProperty IPAddress

if (-not $current) { throw '未找到局域网 IPv4，请手动传入 -ExtraIps' }

$ensure = @($current)
foreach ($ip in ($ExtraIps -split '[;, ]')) {
  if ($ip -and $ip -notin $ensure) { $ensure += $ip }
}

"LAN EXPOSE current=$current ensure=$($ensure -join ',') $(Get-Date)" | Out-File $log

# 2. 清理历史失效地址（本项目端口）
foreach ($port in 8000, 9000, 9001) {
  foreach ($old in @('192.168.110.121', '0.0.0.0')) {
    netsh interface portproxy delete v4tov4 listenport=$port listenaddress=$old 2>$null | Out-Null
  }
}

# 3. 为目标地址建立/刷新映射
foreach ($port in 8000, 9000, 9001) {
  foreach ($ip in $ensure) {
    netsh interface portproxy delete v4tov4 listenport=$port listenaddress=$ip 2>$null | Out-Null
    netsh interface portproxy add v4tov4 listenport=$port listenaddress=$ip connectaddress=127.0.0.1 connectport=$port
    "portproxy $ip`:$port : $LASTEXITCODE" | Out-File $log -Append
  }
  netsh advfirewall firewall delete rule name="InvoiceAudit-$port" 2>$null | Out-Null
  netsh advfirewall firewall add rule name="InvoiceAudit-$port" dir=in action=allow protocol=TCP localport=$port
  "firewall  $port : $LASTEXITCODE" | Out-File $log -Append
}

"---- portproxy show all ----" | Out-File $log -Append
netsh interface portproxy show all | Out-File $log -Append
"LAN EXPOSE END $(Get-Date)" | Out-File $log -Append
Write-Output "DONE -> http://$current`:8000"
