$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

if (-not (Get-Command hermes -ErrorAction SilentlyContinue)) {
    throw "hermes executable not found in PATH."
}

Write-Host "Installing/enabling Ponytail..."
hermes plugins enable ponytail --no-allow-tool-override
if ($LASTEXITCODE -ne 0) {
    hermes plugins install DietrichGebert/ponytail --enable
}

python (Join-Path $Root "scripts\install-hermes-skill.py")
python (Join-Path $Root "scripts\validate-context.py")
Write-Host "Hermes setup complete. Restart Hermes before using the plugin/skill."
