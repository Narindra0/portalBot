@echo off
echo ==========================================
echo   PortalJob Scraper - Launcher
echo ==========================================
echo.
echo Choisis le mode de lancement :
echo.
echo 1. Scraper uniquement (recherche offres)
echo 2. Telegram uniquement (callbacks)
echo 3. Complet (scraper + telegram)
echo.
set /p choice="Choix (1-3) : "

if "%choice%"=="1" goto scraper
if "%choice%"=="2" goto telegram
if "%choice%"=="3" goto all

echo Choix invalide.
goto end

:scraper
echo.
echo Lancement du scraper...
python -m src.main scraper
goto end

:telegram
echo.
echo Lancement du gestionnaire Telegram...
python -m src.main telegram
goto end

:all
echo.
echo Lancement complet...
python -m src.main all
goto end

:end
pause
