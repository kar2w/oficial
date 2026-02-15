param(
    [string]$Version = "1.0.0",
    [string]$AppName = "MotoboysWebApp",
    [string]$CompanyName = "Motoboys",
    [string]$Description = "Motoboys WebApp Desktop Launcher",
    [string]$IconPath = "desktop/app.ico"
)

$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $root

python -m pip install --upgrade pip | Out-Host
python -m pip install -r requirements.txt | Out-Host
python -m pip install pyinstaller | Out-Host

$versionInfoPath = Join-Path $root "desktop\version_info.txt"
@"
# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=($($Version.Replace('.', ',')), 0),
    prodvers=($($Version.Replace('.', ',')), 0),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        u'040904B0',
        [
          StringStruct(u'CompanyName', u'$CompanyName'),
          StringStruct(u'FileDescription', u'$Description'),
          StringStruct(u'FileVersion', u'$Version'),
          StringStruct(u'InternalName', u'$AppName'),
          StringStruct(u'OriginalFilename', u'$AppName.exe'),
          StringStruct(u'ProductName', u'$AppName'),
          StringStruct(u'ProductVersion', u'$Version')
        ]
      )
    ]),
    VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
  ]
)
"@ | Set-Content -Path $versionInfoPath -Encoding UTF8

$iconArg = @()
if (Test-Path $IconPath) {
    $iconArg = @("--icon", $IconPath)
}

$pyArgs = @(
    "-m", "PyInstaller",
    "--noconfirm",
    "--clean",
    "--windowed",
    "--onefile",
    "--name", $AppName,
    "--version-file", "desktop/version_info.txt",
    "--add-data", "app/web/templates;app/web/templates",
    "--add-data", "app/web/static;app/web/static",
    "--add-data", "data/entregadores_semanais.json;data",
    "desktop/launcher.py"
) + $iconArg

python @pyArgs | Out-Host

Write-Host "Build finalizado: dist/$AppName.exe"
Write-Host "Atualização: substitua o executável antigo por dist/$AppName.exe (mesmo diretório de dados em %LOCALAPPDATA%\MotoboysWebApp)."


Write-Host "Opcional (instalador): execute o Inno Setup com desktop/installer.iss para gerar dist/MotoboysWebApp-Setup.exe"
