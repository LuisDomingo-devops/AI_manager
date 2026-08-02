@echo off
echo Configuring Git and pushing to GitHub...

REM 1. Initialize git
if not exist .git (
    echo Initializing new Git repository...
    git init
) else (
    echo Git repository already initialized.
)

REM 2. Configure remote
git remote remove origin 2>nul
git remote add origin https://github.com/LuisDomingo-devops/AI_manager.git

REM 3. Rename branch to main
git branch -M main

REM 4. Add and commit
echo Adding files...
git add .
echo Committing changes...
git commit -m "Initial commit from Antigravity"

REM 5. Push
echo Pushing to GitHub...
git push -u origin main

echo Process completed!
pause
