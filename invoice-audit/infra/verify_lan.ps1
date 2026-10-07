$ErrorActionPreference = 'Stop'
$base = 'http://192.168.110.239:8000'
$login = Invoke-RestMethod -Method Post -Uri "$base/api/auth/login" -ContentType 'application/json' -Body '{"emp_no":"admin","password":"admin"}' -TimeoutSec 15
$token = $login.token
$headers = @{ Authorization = "Bearer $token" }
$claims = Invoke-RestMethod -Uri "$base/api/dashboard/claims?page_size=1" -Headers $headers -TimeoutSec 15
$cid = $claims.items[0].id
$location = ''
try {
  Invoke-WebRequest -Uri "$base/api/claims/$cid/file" -Headers $headers -MaximumRedirection 0 -TimeoutSec 15 | Out-Null
} catch {
  $location = $_.Exception.Response.Headers.Location.AbsoluteUri
}
Write-Output "file endpoint Location: $location"
if ($location -like '*192.168.110.239:9000*') { Write-Output 'PRESIGNED_URL_OK: 预签名URL指向局域网MinIO地址' } else { Write-Output "PRESIGNED_URL_WARN: $location" }
Write-Output '--- 防火墙 9000/9001 ---'
netsh advfirewall firewall show rule name='InvoiceAudit-9000' | Select-String -Pattern 'Rule Name|Enabled'
netsh advfirewall firewall show rule name='InvoiceAudit-9001' | Select-String -Pattern 'Rule Name|Enabled'
