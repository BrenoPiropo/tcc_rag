[CmdletBinding()]
param(
    [string]$OutputRoot = 'D:\tcc_sic',
    [int[]]$Editions = @(1, 2, 3, 4, 5),
    [ValidateRange(1, 1000)]
    [int]$BatchSize = 100,
    [ValidateRange(0, 3600)]
    [int]$BatchPauseSeconds = 15,
    [ValidateRange(0, 10000)]
    [int]$RequestDelayMilliseconds = 350,
    [ValidateRange(1, 10)]
    [int]$MaxAttempts = 3,
    [ValidateRange(0, 100000)]
    [int]$MaxBatches = 0,
    [switch]$VerifyOnly
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$baseUrl = 'https://uescsic.com'
$logsDir = Join-Path $OutputRoot 'logs'
$stateDir = Join-Path $OutputRoot 'controle'
$runId = Get-Date -Format 'yyyyMMdd_HHmmss'
$logFile = Join-Path $logsDir "download_$runId.log"
$manifestFile = Join-Path $stateDir 'manifesto.csv'
$errorsFile = Join-Path $stateDir 'erros.csv'
$statusFile = Join-Path $OutputRoot 'STATUS.txt'
$summaryFile = Join-Path $stateDir 'resumo.json'
$lockFile = Join-Path $stateDir '.downloader.lock'

New-Item -ItemType Directory -Path $OutputRoot, $logsDir, $stateDir -Force | Out-Null

$lockStream = $null
try {
    $lockStream = [System.IO.File]::Open(
        $lockFile,
        [System.IO.FileMode]::OpenOrCreate,
        [System.IO.FileAccess]::ReadWrite,
        [System.IO.FileShare]::None
    )
}
catch {
    throw "Outro processo do downloader parece estar em execução. Arquivo de bloqueio: $lockFile"
}

function Write-Log {
    param(
        [Parameter(Mandatory)] [string]$Message,
        [ValidateSet('INFO', 'OK', 'AVISO', 'ERRO')] [string]$Level = 'INFO'
    )

    $line = '{0} [{1}] {2}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Level, $Message
    Add-Content -LiteralPath $logFile -Value $line -Encoding utf8
    Write-Host $line
}

function Set-Status {
    param([Parameter(Mandatory)] [AllowEmptyString()] [string[]]$Lines)
    $content = @(
        "Atualizado em: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
        "Log atual: $logFile"
        ''
    ) + $Lines
    Set-Content -LiteralPath $statusFile -Value $content -Encoding utf8
}

function Add-CsvRecord {
    param(
        [Parameter(Mandatory)] [string]$Path,
        [Parameter(Mandatory)] [pscustomobject]$Record
    )

    $exists = Test-Path -LiteralPath $Path
    $Record | Export-Csv -LiteralPath $Path -NoTypeInformation -Encoding utf8 -Append:$exists
}

function ConvertTo-SafeFileName {
    param([Parameter(Mandatory)] [string]$Value)

    $decoded = [System.Net.WebUtility]::HtmlDecode($Value).Trim()
    foreach ($char in [System.IO.Path]::GetInvalidFileNameChars()) {
        $decoded = $decoded.Replace([string]$char, '_')
    }
    $decoded = [regex]::Replace($decoded, '\s+', ' ').Trim(' ', '.')
    if ([string]::IsNullOrWhiteSpace($decoded)) { return 'sem_nome' }
    if ($decoded.Length -gt 140) { $decoded = $decoded.Substring(0, 140).Trim() }
    return $decoded
}

function Test-ValidPdf {
    param([Parameter(Mandatory)] [string]$Path)

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return $false }
    $item = Get-Item -LiteralPath $Path
    if ($item.Length -lt 5) { return $false }

    $stream = $null
    try {
        $stream = [System.IO.File]::OpenRead($Path)
        $buffer = New-Object byte[] 5
        if ($stream.Read($buffer, 0, 5) -ne 5) { return $false }
        return ([System.Text.Encoding]::ASCII.GetString($buffer) -eq '%PDF-')
    }
    catch {
        return $false
    }
    finally {
        if ($null -ne $stream) { $stream.Dispose() }
    }
}

function Get-InputValue {
    param(
        [Parameter(Mandatory)] [string]$FormHtml,
        [Parameter(Mandatory)] [string]$Name
    )

    $escaped = [regex]::Escape($Name)
    $patterns = @(
        ('name\s*=\s*["'']{0}["''][^>]*value\s*=\s*["'']([^"'']*)["'']' -f $escaped),
        ('value\s*=\s*["'']([^"'']*)["''][^>]*name\s*=\s*["'']{0}["'']' -f $escaped)
    )

    foreach ($pattern in $patterns) {
        $match = [regex]::Match($FormHtml, $pattern, [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
        if ($match.Success) {
            return [System.Net.WebUtility]::HtmlDecode($match.Groups[1].Value)
        }
    }
    return ''
}

function Get-EditionRecords {
    param(
        [Parameter(Mandatory)] [int]$Edition,
        [Parameter(Mandatory)] [Microsoft.PowerShell.Commands.WebRequestSession]$Session
    )

    $url = "$baseUrl/anais/$Edition"
    Write-Log "Lendo índice da edição ${Edition}: $url"
    $response = Invoke-WebRequest -Uri $url -WebSession $Session -UseBasicParsing -TimeoutSec 120
    $forms = [regex]::Matches(
        $response.Content,
        '(?is)<form\b[^>]*method\s*=\s*["'']post["''][^>]*action\s*=\s*["''][^"'']*/pdf-anais["''][^>]*>(.*?)</form>'
    )

    $records = [System.Collections.Generic.List[object]]::new()
    foreach ($form in $forms) {
        $html = $form.Groups[1].Value
        $userId = Get-InputValue -FormHtml $html -Name 'user_id'
        $name = Get-InputValue -FormHtml $html -Name 'nome'
        $email = Get-InputValue -FormHtml $html -Name 'email'
        $editionId = Get-InputValue -FormHtml $html -Name 'edition_id'
        $token = Get-InputValue -FormHtml $html -Name '_token'

        if ([string]::IsNullOrWhiteSpace($userId) -or [string]::IsNullOrWhiteSpace($token)) {
            continue
        }
        if ([string]::IsNullOrWhiteSpace($editionId)) { $editionId = [string]$Edition }

        $safeName = ConvertTo-SafeFileName -Value $name
        $fileName = '{0} - {1}.pdf' -f $userId, $safeName
        $editionDir = Join-Path $OutputRoot ("anais_{0}" -f $Edition)
        $records.Add([pscustomobject]@{
            Edition = $Edition
            EditionId = $editionId
            UserId = $userId
            Name = $name
            Email = $email
            Token = $token
            Directory = $editionDir
            FileName = $fileName
            FilePath = Join-Path $editionDir $fileName
        })
    }

    Write-Log "Edição ${Edition}: $($records.Count) trabalhos encontrados." 'OK'
    return $records
}

function Save-RunSummary {
    param(
        [int]$Expected,
        [int]$Valid,
        [int]$Downloaded,
        [int]$Skipped,
        [int]$Failed,
        [int]$UnavailableEditions,
        [string]$State
    )

    $summary = [ordered]@{
        updated_at = (Get-Date).ToString('o')
        state = $State
        expected = $Expected
        valid_pdfs = $Valid
        downloaded_this_run = $Downloaded
        skipped_existing = $Skipped
        failed_this_run = $Failed
        unavailable_editions = $UnavailableEditions
        output_root = $OutputRoot
        current_log = $logFile
    }
    $summary | ConvertTo-Json | Set-Content -LiteralPath $summaryFile -Encoding utf8
}

$session = New-Object Microsoft.PowerShell.Commands.WebRequestSession
$allRecords = [System.Collections.Generic.List[object]]::new()
$unavailable = [System.Collections.Generic.List[int]]::new()
$downloaded = 0
$skipped = 0
$failed = 0
$batchNumber = 0

try {
    Write-Log "Início. Destino=$OutputRoot; edições=$($Editions -join ','); lote=$BatchSize; máximo de lotes=$MaxBatches"
    Set-Status -Lines @('Mapeando os índices do site...')

    foreach ($edition in $Editions) {
        try {
            $records = @(Get-EditionRecords -Edition $edition -Session $session)
            foreach ($record in $records) { $allRecords.Add($record) }
        }
        catch {
            $unavailable.Add($edition)
            Write-Log "Edição ${Edition} indisponível: $($_.Exception.Message)" 'ERRO'
            Add-CsvRecord -Path $errorsFile -Record ([pscustomobject]@{
                timestamp = (Get-Date).ToString('o')
                edition = $edition
                user_id = ''
                file = ''
                error = $_.Exception.Message
            })
        }
    }

    $expected = $allRecords.Count
    $validBefore = @($allRecords | Where-Object { Test-ValidPdf -Path $_.FilePath }).Count
    Write-Log "Mapeamento concluído: $expected trabalhos; $validBefore PDFs já válidos; edições indisponíveis: $($unavailable -join ',')."

    if ($VerifyOnly) {
        $missing = $expected - $validBefore
        Write-Log "Verificação concluída: válidos=$validBefore; ausentes/inválidos=$missing." 'OK'
        Save-RunSummary -Expected $expected -Valid $validBefore -Downloaded 0 -Skipped $validBefore -Failed 0 -UnavailableEditions $unavailable.Count -State 'VERIFICADO'
        Set-Status -Lines @(
            'Estado: VERIFICAÇÃO CONCLUÍDA'
            "PDFs esperados nas edições acessíveis: $expected"
            "PDFs válidos: $validBefore"
            "Ausentes ou inválidos: $missing"
            "Edições indisponíveis: $($unavailable -join ', ')"
        )
        return
    }

    $pending = @($allRecords | Where-Object { -not (Test-ValidPdf -Path $_.FilePath) })
    if ($pending.Count -eq 0) {
        Write-Log 'Todos os PDFs das edições acessíveis já estão presentes e válidos.' 'OK'
    }

    for ($offset = 0; $offset -lt $pending.Count; $offset += $BatchSize) {
        if ($MaxBatches -gt 0 -and $batchNumber -ge $MaxBatches) { break }
        $batchNumber++
        $end = [Math]::Min($offset + $BatchSize - 1, $pending.Count - 1)
        $batch = @($pending[$offset..$end])
        Write-Log "Iniciando lote ${batchNumber}: itens $($offset + 1) a $($end + 1) de $($pending.Count)."

        foreach ($record in $batch) {
            New-Item -ItemType Directory -Path $record.Directory -Force | Out-Null

            if (Test-ValidPdf -Path $record.FilePath) {
                $skipped++
                continue
            }

            $success = $false
            $lastError = ''
            for ($attempt = 1; $attempt -le $MaxAttempts -and -not $success; $attempt++) {
                $tempFile = "$($record.FilePath).parcial"
                try {
                    if (Test-Path -LiteralPath $tempFile) { Remove-Item -LiteralPath $tempFile -Force }
                    $body = @{
                        _token = $record.Token
                        user_id = $record.UserId
                        nome = $record.Name
                        email = $record.Email
                        edition_id = $record.EditionId
                    }

                    $response = Invoke-WebRequest -Uri "$baseUrl/pdf-anais" -Method Post -WebSession $session -Body $body -UseBasicParsing -TimeoutSec 180 -OutFile $tempFile -PassThru
                    $contentType = [string]$response.Headers['Content-Type']
                    if ($contentType -notmatch 'application/pdf' -or -not (Test-ValidPdf -Path $tempFile)) {
                        throw "Resposta inválida (Content-Type=$contentType)."
                    }

                    Move-Item -LiteralPath $tempFile -Destination $record.FilePath -Force
                    $bytes = (Get-Item -LiteralPath $record.FilePath).Length
                    $downloaded++
                    $success = $true
                    Write-Log "[$downloaded baixados] Edição $($record.Edition), ID $($record.UserId): $($record.FileName) ($bytes bytes)" 'OK'
                    Add-CsvRecord -Path $manifestFile -Record ([pscustomobject]@{
                        timestamp = (Get-Date).ToString('o')
                        edition = $record.Edition
                        user_id = $record.UserId
                        name = $record.Name
                        file = $record.FilePath
                        bytes = $bytes
                        status = 'OK'
                    })
                }
                catch {
                    $lastError = $_.Exception.Message
                    if (Test-Path -LiteralPath $tempFile) { Remove-Item -LiteralPath $tempFile -Force -ErrorAction SilentlyContinue }
                    Write-Log "Tentativa $attempt/$MaxAttempts falhou: edição $($record.Edition), ID $($record.UserId): $lastError" 'AVISO'
                    if ($attempt -lt $MaxAttempts) {
                        Start-Sleep -Seconds ([Math]::Min(30, [Math]::Pow(2, $attempt)))
                    }
                }
            }

            if (-not $success) {
                $failed++
                Write-Log "Falha definitiva nesta execução: edição $($record.Edition), ID $($record.UserId)." 'ERRO'
                Add-CsvRecord -Path $errorsFile -Record ([pscustomobject]@{
                    timestamp = (Get-Date).ToString('o')
                    edition = $record.Edition
                    user_id = $record.UserId
                    file = $record.FilePath
                    error = $lastError
                })
            }

            $processed = [Math]::Min($offset + [Array]::IndexOf($batch, $record) + 1, $pending.Count)
            $validNowEstimate = $validBefore + $downloaded
            Set-Status -Lines @(
                'Estado: BAIXANDO'
                "Lote atual: $batchNumber"
                "Pendentes processados nesta execução: $processed de $($pending.Count)"
                "Baixados nesta execução: $downloaded"
                "Falhas nesta execução: $failed"
                "PDFs válidos estimados: $validNowEstimate de $expected"
                "Edições indisponíveis: $($unavailable -join ', ')"
            )
            Start-Sleep -Milliseconds $RequestDelayMilliseconds
        }

        Write-Log "Lote ${batchNumber} concluído. Baixados=$downloaded; falhas=$failed." 'OK'
        if (($offset + $BatchSize) -lt $pending.Count -and ($MaxBatches -eq 0 -or $batchNumber -lt $MaxBatches)) {
            Write-Log "Pausa de $BatchPauseSeconds segundos antes do próximo lote."
            Start-Sleep -Seconds $BatchPauseSeconds
        }
    }

    $validAfter = @($allRecords | Where-Object { Test-ValidPdf -Path $_.FilePath }).Count
    $missingAfter = $expected - $validAfter
    $state = if ($missingAfter -eq 0 -and $unavailable.Count -eq 0) { 'CONCLUIDO' } elseif ($missingAfter -eq 0) { 'PARCIAL_EDICAO_INDISPONIVEL' } else { 'INCOMPLETO_RETOMAVEL' }
    Save-RunSummary -Expected $expected -Valid $validAfter -Downloaded $downloaded -Skipped $skipped -Failed $failed -UnavailableEditions $unavailable.Count -State $state
    Set-Status -Lines @(
        "Estado: $state"
        "PDFs esperados nas edições acessíveis: $expected"
        "PDFs válidos: $validAfter"
        "Ausentes ou inválidos: $missingAfter"
        "Baixados nesta execução: $downloaded"
        "Falhas nesta execução: $failed"
        "Edições indisponíveis: $($unavailable -join ', ')"
        ''
        'Execute o mesmo script novamente para retomar qualquer item faltante.'
    )
    Write-Log "Fim: estado=$state; válidos=$validAfter/$expected; baixados=$downloaded; falhas=$failed; edições indisponíveis=$($unavailable -join ',')." 'OK'
}
finally {
    if ($null -ne $lockStream) { $lockStream.Dispose() }
}
