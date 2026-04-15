# PortalJob Scraper - Launcher PowerShell

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "   PortalJob Scraper - Launcher" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "Choisis le mode de lancement :" -ForegroundColor Yellow
Write-Host ""
Write-Host "1. Scraper uniquement (recherche offres)" -ForegroundColor White
Write-Host "2. Telegram uniquement (callbacks)" -ForegroundColor White
Write-Host "3. Complet (scraper + telegram)" -ForegroundColor White
Write-Host ""

$choice = Read-Host "Choix (1-3)"

switch ($choice) {
    "1" { 
        Write-Host "`nLancement du scraper..." -ForegroundColor Green
        python -m src.main scraper 
    }
    "2" { 
        Write-Host "`nLancement du gestionnaire Telegram..." -ForegroundColor Green
        python -m src.main telegram 
    }
    "3" { 
        Write-Host "`nLancement complet..." -ForegroundColor Green
        python -m src.main all 
    }
    default { 
        Write-Host "`nChoix invalide." -ForegroundColor Red 
    }
}

Write-Host "`nAppuie sur une touche pour fermer..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
