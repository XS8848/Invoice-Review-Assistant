$ErrorActionPreference = 'Continue'
$ip = '192.168.110.194'
Write-Output '--- 后端健康 ---'
try { (Invoke-WebRequest -Uri "http://$ip`:8000/api/health" -UseBasicParsing -TimeoutSec 10).Content } catch { "FAIL: $($_.Exception.Message)" }
Write-Output '--- MinIO健康 ---'
try { $r = Invoke-WebRequest -Uri "http://$ip`:9000/minio/health/live" -UseBasicParsing -TimeoutSec 10; "http=$($r.StatusCode)" } catch { "FAIL: $($_.Exception.Message)" }
Write-Output '--- SPA页面 ---'
try { (Invoke-WebRequest -Uri "http://$ip`:8000/login" -UseBasicParsing -TimeoutSec 10).StatusCode } catch { "FAIL: $($_.Exception.Message)" }
Write-Output '--- 登录+原图预签名链路 ---'
$login = Invoke-RestMethod -Method Post -Uri "http://$ip`:8000/api/auth/login" -ContentType 'application/json' -Body '{"emp_no":"admin","password":"admin"}' -TimeoutSec 15
$claims = Invoke-RestMethod -Uri "http://$ip`:8000/api/dashboard/claims?page_size=1" -Headers @{Authorization="Bearer $($login.token)"} -TimeoutSec 15
$cid = $claims.items[0].id
$loc = (curl.exe -s -o NUL -D - -H "Authorization: Bearer $($login.token)" "http://$ip`:8000/api/claims/$cid/file" | Select-String -Pattern '^location').Line -replace 'location: ',''
Write-Output "Location: $loc"
$code = curl.exe -s -o NUL -w '%{http_code} %{size_download}bytes' $loc
Write-Output "原图下载: HTTP $code"
if ($loc -like "*192.168.110.194:9000*") { Write-Output 'PRESIGNED_HOST_OK' } else { Write-Output 'PRESIGNED_HOST_MISMATCH' }
