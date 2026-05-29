$folder = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $folder
Write-Host "Working in: $(Get-Location)"

# Enable long file paths
git config --global core.longpaths true

# Kill old .git
if (Test-Path ".git") {
    Write-Host "Removing old .git..."
    Remove-Item -Recurse -Force ".git"
}

# Fresh init
git init -b main
git remote add origin "https://sharathtableau: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@github.com/sharathtableau/Tableau-Multi-Dashboard-Insights_-Working.git"

# Stage (gitignore will exclude uploads/, output/, __MACOSX/ etc)
Write-Host "Staging..."
git add .

# Check something got staged
$count = (git diff --cached --name-only).Count
Write-Host "Files staged: $count"

if ($count -eq 0) {
    Write-Host "ERROR: Nothing staged. Check .gitignore is not too aggressive."
    exit 1
}

# Commit
$ts = Get-Date -Format "yyyy-MM-dd HH:mm"
git commit -m "Deploy $ts"

# Push
Write-Host "Pushing..."
git push origin main --force

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "SUCCESS - Render redeploying now"
    Write-Host "https://dashboard.render.com"
} else {
    Write-Host "FAILED - exit code $LASTEXITCODE"
}
