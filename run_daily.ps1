$logPath = "C:\Users\sudhi\sp500-trader\run_daily.log"
Start-Transcript -Path $logPath -Append

try {
    $ErrorActionPreference = "Stop"
    $env:Path += ";C:\Program Files\Git\cmd"
    Set-Location "C:\Users\sudhi\sp500-trader"

    .\venv\Scripts\python.exe get_universe.py
    .\venv\Scripts\python.exe market_data.py 1y
    .\venv\Scripts\python.exe daily_report.py

    git add data/sp500_universe.csv reports
    $status = git status --porcelain
    if ($status) {
        git commit -m "Daily report $(Get-Date -Format yyyy-MM-dd)"
        git push
    }
}
catch {
    Write-Output "ERROR: $_"
}
finally {
    Stop-Transcript
}
