# 下线清理：删除端口映射与防火墙规则（需管理员，UAC 弹窗请点“是”）
$ErrorActionPreference = 'Continue'
$log = '$env:USERPROFILE\lan_offline.log'
"OFFLINE CLEANUP $(Get-Date)" | Out-File $log

foreach ($port in 8000, 9000, 9001) {
  foreach ($ip in '192.168.110.194', '192.168.110.239') {
    netsh interface portproxy delete v4tov4 listenport=$port listenaddress=$ip 2>$null | Out-Null
    "portproxy del $ip`:$port -> $LASTEXITCODE" | Out-File $log -Append
  }
  netsh advfirewall firewall delete rule name="InvoiceAudit-$port" 2>$null | Out-Null
  "firewall del $port -> $LASTEXITCODE" | Out-File $log -Append
}
netsh interface portproxy show all | Out-File $log -Append
"OFFLINE CLEANUP END $(Get-Date)" | Out-File $log -Append
