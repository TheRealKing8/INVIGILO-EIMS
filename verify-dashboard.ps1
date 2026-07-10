$body = '{"email":"admininvigilo@gmail.com","password":"Invigilo@2026"}'
$login = Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/v1/auth/login/" -Method POST -ContentType "application/json" -Body $body -UseBasicParsing -TimeoutSec 5
Write-Host "LOGIN: HTTP $($login.StatusCode)"
$tok = ($login.Content | ConvertFrom-Json).access
$h = @{ Authorization = "Bearer $tok" }
foreach ($ep in @("exams/sessions","exams/periods","invigilators/profiles","allocations/allocations","incidents","reports/exports","allocations/runs","academic/faculties","rooms/buildings","audit")) {
    try {
        $x = Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/v1/$ep/" -Headers $h -UseBasicParsing -TimeoutSec 5
        $j = $x.Content | ConvertFrom-Json
        Write-Host ("{0,-28} HTTP {1}  count={2}" -f $ep, $x.StatusCode, $j.count)
    } catch {
        Write-Host ("{0,-28} HTTP {1}" -f $ep, $_.Exception.Response.StatusCode.value__)
    }
}
