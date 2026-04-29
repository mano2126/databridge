# 위저드에서 applyDecision 호출할 때 jobId 넘기는지 확인
Write-Host "`n🔬 위저드 컴포넌트에서 applyDecision 호출 방식 확인`n" -ForegroundColor Cyan

# applyDecision 을 호출하는 모든 파일 찾기
$files = Get-ChildItem -Path "D:\project\databridge_full\frontend\src" -Recurse -Include "*.vue","*.js" -ErrorAction SilentlyContinue
foreach ($f in $files) {
    $content = Get-Content $f.FullName -Raw -ErrorAction SilentlyContinue
    if ($content -and ($content -like "*applyDecision*") -and ($f.Name -ne "advisor.js")) {
        Write-Host "=== $($f.FullName) ===" -ForegroundColor Yellow
        $lines = Get-Content $f.FullName
        for ($i = 0; $i -lt $lines.Count; $i++) {
            if ($lines[$i] -match "applyDecision") {
                $start = [Math]::Max(0, $i - 3)
                $end = [Math]::Min($lines.Count - 1, $i + 12)
                for ($j = $start; $j -le $end; $j++) {
                    $prefix = if ($j -eq $i) { ">>> " } else { "    " }
                    Write-Host "${prefix}line $($j+1): $($lines[$j])" -ForegroundColor $(if ($j -eq $i) { "Green" } else { "Gray" })
                }
                Write-Host ""
            }
        }
    }
}

Write-Host "진단 완료." -ForegroundColor Cyan
