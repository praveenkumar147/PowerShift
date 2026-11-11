# Freezes the Python backend into backend/dist/powershift-backend/ (one folder, no Python install needed).
# Run from the project root:  powershell -File scripts/build-backend.ps1
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root 'backend\.venv\Scripts\python.exe'
Push-Location (Join-Path $root 'backend')
try {
    if (Test-Path dist\powershift-backend) { Remove-Item -Recurse -Force dist\powershift-backend }
    & $python -m PyInstaller --noconfirm --clean --onedir --console `
        --name powershift-backend `
        --distpath dist --workpath build --specpath build `
        --paths . `
        --collect-all ortools `
        --collect-submodules uvicorn `
        --collect-submodules alembic `
        --collect-submodules powershift `
        --hidden-import sqlalchemy.dialects.sqlite `
        --add-data "$((Join-Path $PWD 'powershift\db\migrations'));powershift/db/migrations" `
        powershift\__main__.py
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed with exit code $LASTEXITCODE" }
} finally { Pop-Location }
"Built backend\dist\powershift-backend\powershift-backend.exe"
