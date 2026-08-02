# Script to initialize git repository and push to GitHub
# Run this script in PowerShell from the repository root directory

Write-Host "Configuring Git and pushing to GitHub..." -ForegroundColor Cyan

# 1. Initialize git repository if not already initialized
if (-not (Test-Path .git)) {
    Write-Host "Initializing new Git repository..." -ForegroundColor Yellow
    git init
} else {
    Write-Host "Git repository already initialized." -ForegroundColor Green
}

# 2. Add remote origin
$remoteUrl = "https://github.com/LuisDomingo-devops/AI_manager.git"
$existingRemote = git remote get-url origin 2>$null
if ($null -eq $existingRemote) {
    Write-Host "Adding remote origin: $remoteUrl" -ForegroundColor Yellow
    git remote add origin $remoteUrl
} else {
    Write-Host "Updating remote origin to: $remoteUrl" -ForegroundColor Yellow
    git remote set-url origin $remoteUrl
}

# 3. Rename branch to main
git branch -M main

# 4. Add files and commit
Write-Host "Adding files..." -ForegroundColor Yellow
git add .

Write-Host "Committing changes..." -ForegroundColor Yellow
git commit -m "Initial commit from Antigravity"

# 5. Push to GitHub
Write-Host "Pushing to GitHub..." -ForegroundColor Yellow
git push -u origin main

Write-Host "Process completed!" -ForegroundColor Green
