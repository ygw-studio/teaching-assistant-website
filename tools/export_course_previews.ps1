$ErrorActionPreference = 'Stop'
$assetRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../backend/assets/data-structures'))
$existingPowerPoint = @(Get-Process POWERPNT -ErrorAction SilentlyContinue).Count -gt 0
$powerPoint = New-Object -ComObject PowerPoint.Application
try {
    for ($chapter = 1; $chapter -le 8; $chapter++) {
        $sourcePath = Join-Path $assetRoot "chapter-$chapter.pptx"
        $targetPath = Join-Path $assetRoot "chapter-$chapter.pdf"
        if (Test-Path -LiteralPath $targetPath) { continue }
        $presentation = $null
        try {
            $presentation = $powerPoint.Presentations.Open($sourcePath, -1, 0, 0)
            $presentation.SaveAs($targetPath, 32)
            Write-Output "Chapter $chapter preview exported ($($presentation.Slides.Count) pages)."
        } finally {
            if ($null -ne $presentation) {
                $presentation.Close()
                [void][Runtime.InteropServices.Marshal]::ReleaseComObject($presentation)
            }
        }
    }
} finally {
    if (-not $existingPowerPoint) { $powerPoint.Quit() }
    [void][Runtime.InteropServices.Marshal]::ReleaseComObject($powerPoint)
}
