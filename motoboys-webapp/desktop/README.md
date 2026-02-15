# Desktop packaging (Windows)

## Arquivos
- `launcher.py`: inicializador local da aplicação.
- `build.ps1`: build do executável com PyInstaller.
- `requirements-build.txt`: dependências para build.

## O que o build inclui
- `app/web/templates/`
- `app/web/static/`
- `data/entregadores_semanais.json`

## Build
```powershell
cd motoboys-webapp\desktop
./build.ps1 -Version "1.0.0" -AppName "MotoboysWebApp"
```

Saída: `motoboys-webapp/dist/MotoboysWebApp.exe`

## Atualização
Substitua o `.exe` antigo pelo novo. Os dados em `%LOCALAPPDATA%\MotoboysWebApp` são preservados.

## Instalador (opcional)
Use o arquivo `installer.iss` com Inno Setup para gerar `dist/MotoboysWebApp-Setup.exe`.
