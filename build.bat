@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "APP=DraftexScreenRecorder"
set "FFMPEG_URL=https://github.com/BtbN/FFmpeg-Builds/releases/latest/download/ffmpeg-master-latest-win64-gpl.zip"

echo.
echo ===== [1/4] Python prostredie (.venv) =====
if not exist ".venv\Scripts\python.exe" (
    py -3.11 -m venv .venv 2>nul || python -m venv .venv || goto :fail
)
call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet || goto :fail

echo.
echo ===== [2/4] FFmpeg =====
if exist "ffmpeg\ffmpeg.exe" echo ffmpeg\ffmpeg.exe uz existuje - preskakujem stahovanie.
if exist "ffmpeg\ffmpeg.exe" goto :ffmpeg_ok
echo Stahujem FFmpeg (~170 MB) ...
if not exist ffmpeg mkdir ffmpeg
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ProgressPreference='SilentlyContinue';" ^
  "Invoke-WebRequest -Uri '%FFMPEG_URL%' -OutFile 'ffmpeg\ffmpeg.zip';" ^
  "Expand-Archive -Path 'ffmpeg\ffmpeg.zip' -DestinationPath 'ffmpeg\tmp' -Force;" ^
  "$exe = Get-ChildItem 'ffmpeg\tmp' -Recurse -Filter ffmpeg.exe | Select-Object -First 1;" ^
  "Copy-Item $exe.FullName 'ffmpeg\ffmpeg.exe' -Force;" ^
  "$lic = Get-ChildItem 'ffmpeg\tmp' -Recurse -Filter LICENSE.txt | Select-Object -First 1;" ^
  "if ($lic) { Copy-Item $lic.FullName 'ffmpeg\LICENSE-ffmpeg.txt' -Force };" ^
  "Remove-Item 'ffmpeg\tmp' -Recurse -Force; Remove-Item 'ffmpeg\ffmpeg.zip' -Force"
:ffmpeg_ok
if not exist "ffmpeg\ffmpeg.exe" (
    echo CHYBA: ffmpeg.exe sa nepodarilo stiahnut.
    echo Skopiruj ffmpeg.exe rucne do priecinka ffmpeg\ a spusti build.bat znova.
    goto :fail
)

echo.
echo ===== [3/4] PyInstaller =====
if exist build rmdir /s /q build
if exist dist  rmdir /s /q dist
pyinstaller --noconfirm --clean screen_recorder.spec || goto :fail
copy /y "ffmpeg\ffmpeg.exe" "dist\%APP%\ffmpeg.exe" >nul
if exist "ffmpeg\LICENSE-ffmpeg.txt" copy /y "ffmpeg\LICENSE-ffmpeg.txt" "dist\%APP%\LICENSE-ffmpeg.txt" >nul

rem --- volitelne podpisanie EXE (nastav SIGN_CMD, napr. signtool sign /tr http://ts.ssl.com /td sha256 /fd sha256 /a)
if defined SIGN_CMD (
    echo Podpisujem %APP%.exe ...
    %SIGN_CMD% "dist\%APP%\%APP%.exe" || goto :fail
)

echo.
echo ===== [4/4] Inno Setup =====
set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%LocalAppData%\Programs\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" (
    echo Inno Setup 6 sa nenasiel - instalator preskoceny.
    echo Prenositelna verzia je hotova v: dist\%APP%\
    goto :ok
)
"%ISCC%" /Q installer.iss || goto :fail

echo.
echo HOTOVO. Instalator: installer\%APP%-Setup-*.exe
echo Prenositelna verzia:  dist\%APP%\

:ok
endlocal
exit /b 0

:fail
echo.
echo BUILD ZLYHAL.
endlocal
exit /b 1
