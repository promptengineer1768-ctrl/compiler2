param(
    [string]$ToolsRoot = "C:\Users\me\Documents\Coding Projects\tools",
    [string]$OutDir = "build",
    [switch]$GeoramCompiler,
    [switch]$UseCompressor,
    [string]$CompressorRoot = "C:\Users\me\Documents\Coding Projects\compressor",
    # Dual-device both-present preference only (never drops a sidecar).
    [ValidateSet("GeoRam", "Reu")]
    [string]$ExpansionPreference = "GeoRam",
    [switch]$Validate
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Ca65 = Join-Path $ToolsRoot "ca65.exe"
$Ld65 = Join-Path $ToolsRoot "ld65.exe"
$Python = "C:\Users\me\AppData\Local\Programs\Python\Python313\python.exe"
$env:COMPILER2_CA65 = $Ca65
$env:COMPILER2_LD65 = $Ld65

# Validate tool paths
if (-not (Test-Path $Ca65)) { throw "ca65.exe not found at $Ca65" }
if (-not (Test-Path $Ld65)) { throw "ld65.exe not found at $Ld65" }

# 1. Validate manifests
Write-Host "=== Validating manifests ===" -ForegroundColor Green
& $Python tools/validate_build.py --manifests
& $Python tools/task_manifest.py validate
if ($LASTEXITCODE -ne 0) { throw "Manifest validation failed." }

if ($Validate) {
    Write-Host "Validation completed successfully." -ForegroundColor Green
    return
}

# A release build never consumes stale objects or generated reports.
& $Python tools/build_output.py --project-root $Root --output-dir $OutDir
if ($LASTEXITCODE -ne 0) { throw "Build output preparation failed." }

# 2. Run ZP allocation
Write-Host "`n=== Allocating Zero Page ===" -ForegroundColor Green
& $Python tools/zp_alloc.py
if ($LASTEXITCODE -ne 0) { throw "Zero page allocation failed." }

Write-Host "`n=== Allocating normal-RAM workareas ===" -ForegroundColor Green
& $Python tools/workarea_alloc.py
if ($LASTEXITCODE -ne 0) { throw "Workarea allocation failed." }

# 3. geoRAM page placement
Write-Host "`n=== Assigning geoRAM Page Placements ===" -ForegroundColor Green
& $Python tools/georam_pages.py
if ($LASTEXITCODE -ne 0) { throw "geoRAM page placement failed." }

# 4. Generate other contracts
Write-Host "`n=== Generating non-ZP contracts ===" -ForegroundColor Green
& $Python tools/generate_contracts.py
if ($LASTEXITCODE -ne 0) { throw "Contracts generation failed." }

# 5. Linker configuration
Write-Host "`n=== Generating Linker configuration ===" -ForegroundColor Green
& $Python tools/linker_config.py
if ($LASTEXITCODE -ne 0) { throw "Linker configuration generation failed." }

# 6. Assemble production sources
Write-Host "`n=== Building 6502 Units ===" -ForegroundColor Green
# Ensure build directories exist
New-Item -ItemType Directory -Force -Path (Join-Path $Root "$OutDir/obj") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $Root "$OutDir/listings") | Out-Null

$MainSource = Join-Path $Root "src/main.asm"
$Sources = @($MainSource) + @(
    Get-ChildItem -Path (Join-Path $Root "src") -Recurse -Filter "*.asm" |
        Where-Object {
            $_.FullName -ne $MainSource -and
            $_.FullName -notlike (Join-Path $Root "src/common/*") -and
            $_.FullName -notlike (Join-Path $Root "src/standalone/*")
        } |
        Sort-Object FullName |
        ForEach-Object { $_.FullName }
)

if (-not (Test-Path $MainSource)) {
    throw "src/main.asm not found; production assembly build cannot continue."
}

$Objects = @()
foreach ($Source in $Sources) {
    $Rel = Resolve-Path -Path $Source -Relative
    $Rel = $Rel -replace '^\.\\src\\', ''
    $ObjName = ($Rel -replace '[\\/]', '_') -replace '\.asm$', '.o'
    $ObjPath = Join-Path $Root "$OutDir/obj/$ObjName"
    Write-Host "Assembling $Rel" -ForegroundColor Green
    & $Ca65 $Source -o $ObjPath -I "$OutDir" -I "src"
    if ($LASTEXITCODE -ne 0) { throw "Assembly failed for $Rel." }
    $Objects += $ObjPath
}

Write-Host "Linking compiler binary" -ForegroundColor Green
$RawCompiler = "$OutDir/compiler.raw"
& $Ld65 -C "$OutDir/compiler.cfg" -o $RawCompiler -m "$OutDir/compiler.map" -Ln "$OutDir/compiler.lbl" @Objects
if ($LASTEXITCODE -ne 0) { throw "Linking failed." }

& $Python tools/update_routine_addresses.py "$OutDir/compiler.lbl" "$OutDir/routine_directory.json"
if ($LASTEXITCODE -ne 0) { throw "Routine address update failed." }

$RawBytes = [System.IO.File]::ReadAllBytes((Join-Path $Root $RawCompiler))
$PrgBytes = New-Object byte[] ($RawBytes.Length + 2)
$PrgBytes[0] = 0x01
$PrgBytes[1] = 0x08
[Array]::Copy($RawBytes, 0, $PrgBytes, 2, $RawBytes.Length)
[System.IO.File]::WriteAllBytes((Join-Path $Root "$OutDir/compiler.bin"), $PrgBytes)

# Materialize the linked GEOASM segment into the release geoRAM page image.
& $Python tools/populate_georam.py `
    "$OutDir/compiler.map" `
    "$OutDir/compiler.bin" `
    "$OutDir/georam.bin" `
    --labels "$OutDir/compiler.lbl" `
    --routine-directory "$OutDir/routine_directory.json" `
    --linked-georam "$OutDir/georam.bin"
if ($LASTEXITCODE -ne 0) { throw "geoRAM payload population failed." }

# Extract segments
& $Python tools/extract_segments.py "$OutDir/compiler.map" "$OutDir/compiler.bin" "$OutDir/compile.bin"
if ($LASTEXITCODE -ne 0) { throw "Segment extraction failed." }

# Package hibasic.bin as a PRG loadable at $E000 (program_lines / LET helpers).
$HibasicBin = Join-Path $Root "$OutDir/hibasic.bin"
$HibasicPrg = Join-Path $Root "$OutDir/hibasic.prg"
if (Test-Path $HibasicBin) {
    $Hb = [System.IO.File]::ReadAllBytes($HibasicBin)
    $HbPrg = New-Object byte[] ($Hb.Length + 2)
    $HbPrg[0] = 0x00
    $HbPrg[1] = 0xE0
    [Array]::Copy($Hb, 0, $HbPrg, 2, $Hb.Length)
    [System.IO.File]::WriteAllBytes($HibasicPrg, $HbPrg)
    Write-Host "Packaged hibasic.prg ($($Hb.Length) bytes -> `$E000)" -ForegroundColor Green
}

# The bounded RAM-under-I/O cold overlay is staged at $0200 then copied through
# the resident gate to $D000; it is never loaded directly over live I/O.
$IoBasicBin = Join-Path $Root "$OutDir/iobasic.bin"
$IoBasicPrg = Join-Path $Root "$OutDir/iobasic.prg"
if (Test-Path $IoBasicBin) {
    $Io = [System.IO.File]::ReadAllBytes($IoBasicBin)
    if ($Io.Length -gt 255) { throw "iobasic.bin exceeds the $0200 staging page." }
    $IoPrg = New-Object byte[] ($Io.Length + 2)
    $IoPrg[0] = 0x00
    $IoPrg[1] = 0x02
    [Array]::Copy($Io, 0, $IoPrg, 2, $Io.Length)
    [System.IO.File]::WriteAllBytes($IoBasicPrg, $IoPrg)
    Write-Host "Packaged iobasic.prg ($($Io.Length) bytes -> `$0200 staging)" -ForegroundColor Green
}

# Stage & pack
& $Python tools/prepare_compressor_segments.py "$OutDir/compile.bin" "$OutDir/basicv3.prg"
if ($LASTEXITCODE -ne 0) { throw "Compressor segment staging failed." }
$GeoramPath = Join-Path $Root "$OutDir/georam.bin"
if (Test-Path $GeoramPath) {
    $GeoramBytes = [System.IO.File]::ReadAllBytes($GeoramPath)
    if ($GeoramBytes.Length -ge 2 -and $GeoramBytes[0] -eq 0x00 -and $GeoramBytes[1] -eq 0xDE) {
        $GeoramPayload = New-Object byte[] ($GeoramBytes.Length - 2)
        [Array]::Copy($GeoramBytes, 2, $GeoramPayload, 0, $GeoramPayload.Length)
    } else {
        $GeoramPayload = $GeoramBytes
    }
    if ($GeoramPayload.Length -lt 65536) {
        $PaddedGeoram = New-Object byte[] 65536
        [Array]::Copy($GeoramPayload, 0, $PaddedGeoram, 0, $GeoramPayload.Length)
        $GeoramPayload = $PaddedGeoram
    }
    $GeoramPrg = New-Object byte[] ($GeoramPayload.Length + 2)
    $GeoramPrg[0] = 0x00
    $GeoramPrg[1] = 0xDE
    [Array]::Copy($GeoramPayload, 0, $GeoramPrg, 2, $GeoramPayload.Length)
    [System.IO.File]::WriteAllBytes($GeoramPath, $GeoramPrg)
}
if ($UseCompressor) {
    Write-Host "Building compressed compiler and geoRAM sidecar" -ForegroundColor Green
    & $Python `
        tools/build_compressor_artifacts.py `
        --root $Root `
        --build-dir $OutDir `
        --compressor-root $CompressorRoot
    if ($LASTEXITCODE -ne 0) { throw "Compressor artifact build failed." }
}
# Stock COMPILE export baseline: source-free COMPILED.PRG (docs/COMPILE_EXPORT.md).
# Separate ca65/ld65 target — not linked into the development compiler image.
Write-Host "Packaging stock COMPILE export (COMPILED.PRG)" -ForegroundColor Green
$StandaloneSrc = Join-Path $Root "src/standalone/compiled_export.asm"
$StandaloneCfg = Join-Path $Root "src/standalone/compiled_export.cfg"
$StandaloneObj = Join-Path $Root "$OutDir/obj/standalone_compiled_export.o"
$StandaloneRaw = Join-Path $Root "$OutDir/compiled_export.raw"
$CompiledPrg = Join-Path $Root "$OutDir/COMPILED.PRG"
if (-not (Test-Path $StandaloneSrc)) {
    throw "src/standalone/compiled_export.asm not found; COMPILE export packaging cannot continue."
}
& $Ca65 $StandaloneSrc -o $StandaloneObj -I "$OutDir" -I "src"
if ($LASTEXITCODE -ne 0) { throw "Assembly failed for standalone/compiled_export.asm." }
& $Ld65 -C $StandaloneCfg -o $StandaloneRaw $StandaloneObj
if ($LASTEXITCODE -ne 0) { throw "Linking COMPILED.PRG failed." }
$StandaloneBytes = [System.IO.File]::ReadAllBytes($StandaloneRaw)
$CompiledBytes = New-Object byte[] ($StandaloneBytes.Length + 2)
$CompiledBytes[0] = 0x01
$CompiledBytes[1] = 0x08
[Array]::Copy($StandaloneBytes, 0, $CompiledBytes, 2, $StandaloneBytes.Length)
[System.IO.File]::WriteAllBytes($CompiledPrg, $CompiledBytes)
Write-Host ("  wrote {0} ({1} bytes)" -f $CompiledPrg, $CompiledBytes.Length)

# Dual-device release: always emit reu.bin (REU patch) + package BASICV3/GEORAM/REU.
# ExpansionPreference only records both-present selection policy; both sidecars ship.
Write-Host "Building REU patch (preference=$ExpansionPreference)" -ForegroundColor Green
$PackageGeoram = "$OutDir/georam.bin"
if ($UseCompressor) {
    $PackageGeoram = "$OutDir/GEORAM_compressed.prg"
}
$ReuPath = Join-Path $Root "$OutDir/reu.bin"
& $Python tools/package_d64.py --write-reu-patch $PackageGeoram $ReuPath
if ($LASTEXITCODE -ne 0) { throw "REU patch generation failed." }

# The overlay directory is derived from the linked geoRAM routine directory;
# the current REU sidecar is explicitly recorded as a patch-only layout.
& $Python tools/generate_expansion_contracts.py --build-dir $OutDir
if ($LASTEXITCODE -ne 0) { throw "Expansion contract generation failed." }
$PreferenceRecord = Join-Path $Root "$OutDir/expansion_preference.json"
@{
    schema_version = 1
    expansion_preference = $ExpansionPreference
    both_present_store = if ($ExpansionPreference -eq "Reu") { "reu" } else { "georam" }
    sidecars = @("georam.bin", "reu.bin")
    note = "Preference never removes detectors, gates, or D64 sidecars."
} | ConvertTo-Json | Set-Content -Path $PreferenceRecord -Encoding utf8

# Resolve the VICE c1541 packaging tool. Search deterministic, known
# locations only (no PATH probing, per package_d64.resolve_c1541 policy):
#   1. explicit VICE_C1541 env override
#   2. this project's own tools/vice-mcp dist (if present)
#   3. the active vice-next runtime dir that ships the machine executables
#   4. a sibling project's tools/vice-mcp dist under the parent directory
#   5. any extracted vice-instrumentation runtime under builds/
# Fall back to "auto" (deterministic built-in D64 writer) when none exist.
function Find-C1541 {
    # Preferred: standard VICE distribution c1541 (the tools/vice-mcp/dist
    # build), which is a plain executable. Instrumented recorder/instrumentation
    # c1541 builds have crashed (access violation) and are only used as a last
    # resort. No PATH probing (per package_d64.resolve_c1541 policy).
    $primary = @()
    if ($env:VICE_C1541) { $primary += $env:VICE_C1541 }
    $primary += Join-Path $Root "tools/vice-mcp/dist/HeadlessVICE-windows-x86_64/c1541.exe"

    $parent = Split-Path -Path $Root -Parent
    $siblings = @()
    if ($parent -and (Test-Path -LiteralPath $parent)) {
        $siblings = Get-ChildItem -Path $parent -Recurse -Filter "c1541.exe" -ErrorAction SilentlyContinue |
            Where-Object { $_.FullName -notmatch 'vice-instrumentation' } |
            Select-Object -ExpandProperty FullName
    }

    $instrumented = @()
    if ($parent -and (Test-Path -LiteralPath $parent)) {
        $instrumented = Get-ChildItem -Path $parent -Recurse -Filter "c1541.exe" -ErrorAction SilentlyContinue |
            Where-Object { $_.FullName -match 'vice-instrumentation' } |
            Select-Object -ExpandProperty FullName
    }

    foreach ($candidate in ($primary + $siblings + $instrumented)) {
        if ($candidate -and (Test-Path -LiteralPath $candidate)) {
            return $candidate
        }
    }
    return $null
}
$C1541Path = Find-C1541
if ($C1541Path) {
    Write-Host "Using c1541: $C1541Path" -ForegroundColor Green
    & $Python tools/package_d64.py $C1541Path "$OutDir/basicv3.prg" $PackageGeoram "$OutDir/compiler.d64" $ReuPath
} else {
    & $Python tools/package_d64.py "auto" "$OutDir/basicv3.prg" $PackageGeoram "$OutDir/compiler.d64" $ReuPath
}
if ($LASTEXITCODE -ne 0) { throw "D64 packaging failed." }

& $Python tools/phase1_for_benchmark.py --measure-native-fixture --json-out "$OutDir/phase1_for_benchmark.json"
if ($LASTEXITCODE -ne 0) { throw "Phase 1 FOR benchmark measurement failed." }

& $Python `
    tools/generate_build_reports.py --build-dir $OutDir
if ($LASTEXITCODE -ne 0) { throw "Build report generation failed." }

# 7. Post-build validation & reference generation
Write-Host "`n=== Generating reference documents ===" -ForegroundColor Green
& $Python tools/generate_reference.py
if ($LASTEXITCODE -ne 0) { throw "Reference documents generation failed." }

& $Python tools/validate_build.py --write-manifest
if ($LASTEXITCODE -ne 0) { throw "Build manifest generation failed." }

& $Python tools/validate_build.py --all
if ($LASTEXITCODE -ne 0) { throw "Post-build validation failed." }

# 8. Callable coverage report (T10.4). Generates build/test_coverage.json from
#    the production/test entry manifests. Coverage completeness is asserted by
#    tests/system/test_test_harness.py::TestCallableCoverage, not by failing the
#    build, so the report artifact is always produced for downstream audit.
Write-Host "`n=== Generating callable coverage report ===" -ForegroundColor Green
& $Python tools/test_harness.py --validate-coverage
if ($LASTEXITCODE -ne 0) {
    Write-Warning "Callable coverage incomplete (see build/test_coverage.json); the TestCallableCoverage suite tracks the remaining entries."
}

Write-Host "`nBuild completed successfully!" -ForegroundColor Green
