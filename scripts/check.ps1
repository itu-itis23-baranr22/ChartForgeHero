# Runs everything that must pass before a commit: the test suite and the song folder validator.
# The pre-commit hook in .githooks runs this. Exit code 0 means everything passed.
#
# Enable the hook once per clone with:  git config core.hooksPath .githooks

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$python = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) {
    Write-Output "check: no virtual environment at $python"
    exit 1
}

Write-Output 'check: running tests ...'
& $python -X utf8 -m pytest -q -x --tb=short -p no:cacheprovider -W ignore
if ($LASTEXITCODE -ne 0) {
    Write-Output 'check: FAILED, the tests did not pass'
    exit 1
}

$failed = $false
$folders = @(Get-ChildItem (Join-Path $root 'outputs') -Directory -ErrorAction SilentlyContinue)
Write-Output "check: validating $($folders.Count) song folder(s) in outputs ..."
foreach ($folder in $folders) {
    & $python -X utf8 -m chartgen validate $folder.FullName
    if ($LASTEXITCODE -ne 0) {
        $failed = $true
    }
}
if ($failed) {
    Write-Output 'check: FAILED, a song folder did not validate'
    exit 1
}

Write-Output 'check: all passed'
exit 0
