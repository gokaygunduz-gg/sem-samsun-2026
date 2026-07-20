@echo off
chcp 65001 > nul
echo SEM Panel - Yerel calistirma

echo.
echo [1] Sadece giris listesiyle uret (simülasyon):
echo     python scripts/sem_generate.py
echo.
echo [2] Canli veri cek + uret:
echo     python scripts/sem_generate.py --live
echo.
echo [3] Canli döngü (her 60 saniyede bir):
echo     python scripts/sem_generate.py --live --loop 60
echo.

set /p choice="Seciminiz (1/2/3): "

if "%choice%"=="1" python scripts/sem_generate.py
if "%choice%"=="2" python scripts/sem_generate.py --live
if "%choice%"=="3" python scripts/sem_generate.py --live --loop 60

echo.
echo Panel: panel\index.html
pause
