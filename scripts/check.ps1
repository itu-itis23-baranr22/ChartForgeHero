# Runs what must pass before a commit: the tests and the song folder validator.
# Exit code 0 means everything passed.
#
#   scripts\check.ps1         the quick tests, the editor's JavaScript tests and the validator, a few
#                             minutes: the pre-commit hook
#   scripts\check.ps1 -Mid    every test but the real songs and references: heavy synthetic tests and
#                             real Demucs on synthetic audio, about half of -Full
#   scripts\check.ps1 -Full   every test, with real Demucs and the reference songs: before a phase commit;
#                             fails, and lists the files, when a real song or reference is missing
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

# numpy and scipy each carry their own OpenBLAS, and each commits about 32 MB per thread at import:
# about 1 GB with 16 threads, before any test runs. Four threads commit about 0.26 GB for both.
# Only for the tests; the value the window had before is put back when the check ends.
$blasThreadsBefore = $env:OPENBLAS_NUM_THREADS
$env:OPENBLAS_NUM_THREADS = '4'

try {
    $watch = [System.Diagnostics.Stopwatch]::StartNew()
    $failure = 'check: FAILED, the tests did not pass'

    if ($Full) {
        Write-Output 'check: running every test, with real Demucs and the reference songs ...'
        # Both folders are passed even when missing: each test then names the file it could not find, and
        # --require-real-files fails the run on it. -Full never passes with a real song test skipped.
        $references = Join-Path $root 'references'
        $music = Join-Path $HOME 'Desktop\musica'
        foreach ($folder in @($references, $music)) {
            if (-not (Test-Path $folder)) {
                Write-Output "check: $folder is not here, so the tests that need it will fail"
            }
        }
        $env:CHARTGEN_REFERENCE_DIR = $references
        $env:CHARTGEN_MUSIC_DIR = $music
        # An empty -m overrides the "not slow and not real" default from pyproject.toml.
        & $python -X utf8 -m pytest -q -x --tb=short -p no:cacheprovider -W ignore -m '""' --require-real-files
        $failure = 'check: FAILED, a test did not pass or a real song file is missing (see "real files missing" above)'
    } elseif ($Mid) {
        Write-Output 'check: running every test but the real songs and references ...'
        & $python -X utf8 -m pytest -q -x --tb=short -p no:cacheprovider -W ignore -m 'not real'
    } else {
        Write-Output 'check: running the quick tests ...'
        & $python -X utf8 -m pytest -q -x --tb=short -p no:cacheprovider -W ignore -m 'not slow and not heavy and not real'
    }
    if ($LASTEXITCODE -ne 0) {
        Write-Output $failure
        exit 1
    }

    # The editor's JavaScript (SPEC 57): Node's own test runner, no packages. Skipped without Node except in -Full.
    $node = Get-Command node -ErrorAction SilentlyContinue
    $jsTests = @(Get-ChildItem (Join-Path $root 'tests\js') -Filter '*.test.mjs' -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName })
    if ($null -eq $node) {
        if ($Full) {
            Write-Output 'check: FAILED, -Full needs Node.js on PATH for the editor tests (tests\js)'
            exit 1
        }
        Write-Output 'check: no Node.js on PATH, so the editor JavaScript tests are skipped'
    } elseif ($jsTests.Count -gt 0) {
        Write-Output "check: running $($jsTests.Count) JavaScript test file(s) with Node ..."
        & $node.Source --test --test-reporter=dot @jsTests
        if ($LASTEXITCODE -ne 0) {
            Write-Output 'check: FAILED, the editor JavaScript tests did not pass'
            exit 1
        }
    }

    # A folder whose name starts with _ is not a song: outputs\_songs_backup holds old copies from the
    # game, outputs\_experiments and outputs\_drafts hold experiments and notes.
    $folders = @(Get-ChildItem (Join-Path $root 'outputs') -Directory -ErrorAction SilentlyContinue |
        Where-Object { -not $_.Name.StartsWith('_') })
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
} finally {
    if ($null -eq $blasThreadsBefore) {
        Remove-Item Env:OPENBLAS_NUM_THREADS -ErrorAction SilentlyContinue
    } else {
        $env:OPENBLAS_NUM_THREADS = $blasThreadsBefore
    }
}
