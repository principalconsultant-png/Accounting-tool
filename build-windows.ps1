$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
py -3 -m venv .venv
if ($LASTEXITCODE -ne 0) { throw 'Python 3.12+ is required to build.' }
& .\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
if ($LASTEXITCODE -ne 0) { throw 'Build dependencies failed.' }
& .\.venv\Scripts\python.exe -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { throw 'Tests failed.' }
& .\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --onefile --windowed --name RijuBooks run_riju.py
if ($LASTEXITCODE -ne 0) { throw 'Packaging failed.' }
Remove-Item packaged-selftest.json -ErrorAction SilentlyContinue
$p = Start-Process -FilePath .\dist\RijuBooks.exe -ArgumentList '--self-test-output packaged-selftest.json' -Wait -PassThru
if ($p.ExitCode -ne 0) { throw 'Packaged self-test failed.' }
if (-not (Test-Path packaged-selftest.json)) { throw 'Packaged self-test did not complete.' }
$result = Get-Content packaged-selftest.json -Raw | ConvertFrom-Json
if (-not $result.passed) { throw 'Packaged self-test failed.' }
Write-Host 'Built dist\RijuBooks.exe. This development build is unsigned.'
