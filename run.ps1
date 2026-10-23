# Makefile replacement (no make on this machine). Usage: .\run.ps1 <target>
param([Parameter(Mandatory = $true)][string]$Target)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$py = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'

function Invoke-Py([string[]]$PyArgs) {
    & $py @PyArgs
    if ($LASTEXITCODE -ne 0) { throw "python $($PyArgs -join ' ') failed with exit code $LASTEXITCODE" }
}

switch ($Target) {
    'install'  { Invoke-Py @('-m', 'pip', 'install', '-r', 'requirements.txt') }
    'ping'     { Invoke-Py @('-m', 'graph.db') }
    'gen'      { Invoke-Py @('-m', 'datagen.generate') }
    'test'     { Invoke-Py @('-m', 'pytest', '-q') }
    'reset'    { Invoke-Py @('-m', 'graph.loader', '--reset', '--no-load') }
    'load'     { Invoke-Py @('-m', 'graph.loader') }
    'detect'   { Invoke-Py @('-m', 'forensics.engine') }
    'validate' { Invoke-Py @('validate.py') }
    'ui'       { Invoke-Py @('-m', 'streamlit', 'run', 'ui/app.py') }
    'all'      { foreach ($t in 'gen', 'reset', 'load', 'detect', 'validate') { & $PSCommandPath $t } }
    default    { throw "Unknown target '$Target'. Targets: install ping gen test reset load detect validate ui all" }
}
