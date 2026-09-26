$ErrorActionPreference = 'SilentlyContinue'

$projectRoot = 'C:\Users\huzai\OneDrive\Documents\ChatGPT\Hospital Appointment Management System 2'
$python = 'C:\Users\huzai\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'

# Leave an existing instance alone if Flask is already listening on its port.
if (Get-NetTCPConnection -LocalPort 5000 -State Listen -ErrorAction SilentlyContinue) {
    exit
}

Start-Process `
    -FilePath $python `
    -ArgumentList 'app.py' `
    -WorkingDirectory $projectRoot `
    -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $env:TEMP 'hospital-flask.out.log') `
    -RedirectStandardError (Join-Path $env:TEMP 'hospital-flask.err.log')
