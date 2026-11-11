# Runs what must pass before a commit: the tests and the song folder validator.
# Exit code 0 means everything passed.
#
#   scripts\check.ps1         the quick tests and the validator, under a minute: the pre-commit hook
#   scripts\check.ps1 -Mid    every test but the real songs and references: heavy synthetic tests and
#                             real Demucs on synthetic audio, about half of -Full
#   scripts\check.ps1 -Full   every test, with real Demucs and the reference songs: before a phase commit
#
# Enable the hook once per clone with:  git config core.hooksPath .githooks

param(
    [switch]$Full,
    [switch]$Mid
)

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$python = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) {
    Write-Output "check: no virtual environment at $python"
    exit 1
}

$watch = [System.Diagnostics.Stopwatch]::StartNew()

if ($Full) {
    Write-Output 'check: running every test, with real Demucs and the reference songs ...'
    $references = Join-Path $root 'references'
    if (Test-Path $references) {
        $env:CHARTGEN_REFERENCE_DIR = $references
    } else {
        Write-Output 'check: no references folder, so the reference test will be skipped'
    }
    $music = Join-Path $HOME 'Desktop\musica'
    if (Test-Path $music) {
        $env:CHARTGEN_MUSIC_DIR = $music
    } else {
        Write-Output 'check: no music folder, so the real song tests will be skipped'
    }
    # An empty -m overrides the "not slow and not real" default from pyproject.toml.
    & $python -X utf8 -m pytest -q -x --tb=short -p no:cacheprovider -W ignore -m '""'
} elseif ($Mid) {
    Write-Output 'check: running every test but the real songs and references ...'
    & $python -X utf8 -m pytest -q -x --tb=short -p no:cacheprovider -W ignore -m 'not real'
} else {
    Write-Output 'check: running the quick tests ...'
    & $python -X utf8 -m pytest -q -x --tb=short -p no:cacheprovider -W ignore -m 'not slow and not heavy and not real'
}
if ($LASTEXITCODE -ne 0) {
    Write-Output 'check: FAILED, the tests did not pass'
    exit 1
}

$folders = @(Get-ChildItem (Join-Path $root 'outputs') -Directory -ErrorAction SilentlyContinue)
Write-Output "check: validating $($folders.Count) song folder(s) in outputs ..."
if ($folders.Count -gt 0) {
    # One process for all of them: starting Python takes longer than checking a folder.
    & $python -X utf8 -m chartgen validate @($folders | ForEach-Object { $_.FullName })
    if ($LASTEXITCODE -ne 0) {
        Write-Output 'check: FAILED, a song folder did not validate'
        exit 1
    }
}

Write-Output ("check: all passed in {0:N0} s" -f $watch.Elapsed.TotalSeconds)
exit 0
