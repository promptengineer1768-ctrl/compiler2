param(
    [string]$ToolsRoot = "C:\Users\me\Documents\Coding Projects\tools",
    [string]$OutDir = "build",
    [switch]$GeoramCompiler,
    [switch]$UseCompressor,
    [string]$CompressorRoot = "C:\Users\me\Documents\Coding Projects\compressor",
    [switch]$Validate
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Ca65 = Join-Path $ToolsRoot "ca65.exe"
$Ld65 = Join-Path $ToolsRoot "ld65.exe"
$Python = "C:\Users\me\AppData\Local\Programs\Python\Python313\python.exe"

# Validate tool paths
if (-not (Test-Path $Ca65)) { throw "ca65.exe not found at $Ca65" }
if (-not (Test-Path $Ld65)) { throw "ld65.exe not found at $Ld65" }

# 1. Validate manifests
Write-Host "=== Validating manifests ===" -ForegroundColor Green
& $Python tools/validate_build.py --manifests
if ($LASTEXITCODE -ne 0) { throw "Manifest validation failed." }

if ($Validate) {
    Write-Host "Validation completed successfully." -ForegroundColor Green
    return
}

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
            $_.FullName -notlike (Join-Path $Root "src/common/*")
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
    --routine-directory "$OutDir/routine_directory.json"
if ($LASTEXITCODE -ne 0) { throw "geoRAM payload population failed." }

# Extract segments
& $Python tools/extract_segments.py "$OutDir/compiler.map" "$OutDir/compiler.bin" "$OutDir/compile.bin"
# Stage & pack
& $Python tools/prepare_compressor_segments.py "$OutDir/compile.bin" "$OutDir/basicv3.prg"
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
$PackageGeoram = "$OutDir/georam.bin"
if ($UseCompressor) {
    $PackageGeoram = "$OutDir/GEORAM_compressed.prg"
}
& $Python tools/package_d64.py "auto" "$OutDir/basicv3.prg" $PackageGeoram "$OutDir/compiler.d64"
if ($LASTEXITCODE -ne 0) { throw "D64 packaging failed." }

& $Python tools/phase1_for_benchmark.py --json-out "$OutDir/phase1_for_benchmark.json"
if ($LASTEXITCODE -ne 0) { throw "Phase 1 FOR benchmark report generation failed." }

& $Python `
    tools/generate_build_reports.py --build-dir $OutDir
if ($LASTEXITCODE -ne 0) { throw "Build report generation failed." }

# 7. Post-build validation & reference generation
Write-Host "`n=== Generating reference documents ===" -ForegroundColor Green
& $Python tools/generate_reference.py
if ($LASTEXITCODE -ne 0) { throw "Reference documents generation failed." }

& $Python tools/validate_build.py
if ($LASTEXITCODE -ne 0) { throw "Post-build validation failed." }

Write-Host "`nBuild completed successfully!" -ForegroundColor Green
