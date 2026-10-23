# Starts Codex CLI on the GraphAcademy workshop model (gpt-4o-mini) using the key from .env.
# Usage: .\codex-workshop.ps1 [extra codex args]
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$line = Get-Content (Join-Path $PSScriptRoot '.env') | Where-Object { $_ -match '^\s*OPENAI_API_KEY\s*=' } | Select-Object -First 1
if (-not $line) { throw 'OPENAI_API_KEY is missing from .env' }
$env:GRAPHACADEMY_API_KEY = ($line -split '=', 2)[1].Trim().Trim('"').Trim("'").Trim('<', '>')
codex --profile workshop @args
