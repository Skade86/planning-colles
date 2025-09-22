# Script PowerShell pour démarrer backend et frontend dans le même terminal
Write-Host "🚀 Démarrage du Planning Colles..." -ForegroundColor Green

# Fonction pour vérifier si un port est utilisé
function Test-Port {
    param([int]$Port)
    try {
        $listener = [System.Net.NetworkInformation.IPGlobalProperties]::GetIPGlobalProperties().GetActiveTcpListeners()
        return $listener | Where-Object { $_.Port -eq $Port }
    }
    catch {
        return $false
    }
}

# Vérifier les ports
if (Test-Port 8000) {
    Write-Host "⚠️  Le port 8000 est déjà utilisé (backend)" -ForegroundColor Yellow
}

if (Test-Port 3000) {
    Write-Host "⚠️  Le port 3000 est déjà utilisé (frontend)" -ForegroundColor Yellow
}

Write-Host "🎯 Démarrage des services..." -ForegroundColor Green

# Variables pour les jobs
$BackendJob = $null
$FrontendJob = $null

# Fonction de nettoyage
function Stop-Services {
    Write-Host "`n🛑 Arrêt des services..." -ForegroundColor Yellow
    if ($BackendJob) { 
        Stop-Job $BackendJob -ErrorAction SilentlyContinue
        Remove-Job $BackendJob -ErrorAction SilentlyContinue
    }
    if ($FrontendJob) { 
        Stop-Job $FrontendJob -ErrorAction SilentlyContinue
        Remove-Job $FrontendJob -ErrorAction SilentlyContinue
    }
    Write-Host "✅ Services arrêtés." -ForegroundColor Green
}

try {
    # Démarrer le backend en arrière-plan
    Write-Host "🔧 Démarrage du backend..." -ForegroundColor Blue
    $BackendJob = Start-Job -ScriptBlock {
        Set-Location "$using:PWD\backend"
        uvicorn main:app --reload
    }

    # Attendre un peu
    Start-Sleep -Seconds 3

    # Démarrer le frontend en arrière-plan
    Write-Host "📱 Démarrage du frontend..." -ForegroundColor Green
    $FrontendJob = Start-Job -ScriptBlock {
        Set-Location "$using:PWD\frontend"
        npm run dev
    }

    Write-Host ""
    Write-Host "✅ Services démarrés!" -ForegroundColor Green
    Write-Host "📱 Frontend: http://localhost:3000" -ForegroundColor Cyan
    Write-Host "🔧 Backend API: http://localhost:8000" -ForegroundColor Cyan
    Write-Host "📚 Documentation API: http://localhost:8000/docs" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Gray
    Write-Host "                        LOGS EN TEMPS RÉEL" -ForegroundColor White
    Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Gray
    Write-Host "Appuyez sur Ctrl+C pour arrêter tous les services" -ForegroundColor Yellow
    Write-Host ""

    # Boucle pour afficher les logs en temps réel
    while ($true) {
        # Vérifier l'état des jobs
        if ($BackendJob.State -eq "Failed" -or $BackendJob.State -eq "Stopped") {
            Write-Host "❌ [BACKEND] Service arrêté" -ForegroundColor Red
            $backendError = Receive-Job $BackendJob -ErrorAction SilentlyContinue
            if ($backendError) {
                foreach ($line in $backendError) {
                    Write-Host "[BACKEND ERROR] $line" -ForegroundColor Red
                }
            }
            break
        }

        if ($FrontendJob.State -eq "Failed" -or $FrontendJob.State -eq "Stopped") {
            Write-Host "❌ [FRONTEND] Service arrêté" -ForegroundColor Red
            $frontendError = Receive-Job $FrontendJob -ErrorAction SilentlyContinue
            if ($frontendError) {
                foreach ($line in $frontendError) {
                    Write-Host "[FRONTEND ERROR] $line" -ForegroundColor Red
                }
            }
            break
        }

        # Récupérer et afficher les logs du backend
        $backendOutput = Receive-Job $BackendJob -ErrorAction SilentlyContinue
        if ($backendOutput) {
            foreach ($line in $backendOutput) {
                if ($line.ToString().Trim() -ne "") {
                    Write-Host "[BACKEND] " -ForegroundColor Blue -NoNewline
                    Write-Host $line
                }
            }
        }

        # Récupérer et afficher les logs du frontend
        $frontendOutput = Receive-Job $FrontendJob -ErrorAction SilentlyContinue
        if ($frontendOutput) {
            foreach ($line in $frontendOutput) {
                if ($line.ToString().Trim() -ne "") {
                    Write-Host "[FRONTEND] " -ForegroundColor Green -NoNewline
                    Write-Host $line
                }
            }
        }

        Start-Sleep -Milliseconds 1000
    }
}
catch {
    Write-Host "❌ Erreur: $_" -ForegroundColor Red
}
finally {
    Stop-Services
}