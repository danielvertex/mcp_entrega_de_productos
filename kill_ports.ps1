$ports = @(8081, 8086)

foreach ($port in $ports) {
    $pid_matches = netstat -ano | Select-String ":$port\s" | Select-String "LISTENING"
    if ($pid_matches) {
        foreach ($match in $pid_matches) {
            $parts = $match.ToString().Trim() -split '\s+'
            $process_id = $parts[-1]
            Write-Host "Encontrado proceso $process_id en puerto $port. Terminando..."
            taskkill /PID $process_id /F 2>&1
            if ($LASTEXITCODE -eq 0) {
                Write-Host "Correcto: proceso $process_id terminado."
            } else {
                Write-Host "Advertencia: no se pudo terminar el proceso $process_id."
            }
        }
    } else {
        Write-Host "Puerto $port libre."
    }
}

Write-Host ""
Write-Host "Verificacion final:"
netstat -ano | Select-String ":8081|:8086" | Select-String "LISTENING"
if (-not $?) { Write-Host "Puertos 8081 y 8086 libres. Listo para iniciar servidor." }
