$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $ProjectRoot

& '.\.venv\Scripts\python.exe' -m uvicorn src.rag_anais.web_app:app `
    --host 127.0.0.1 `
    --port 8765

