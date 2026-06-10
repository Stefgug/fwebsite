$branch = "demo/break-login-link"
$navbarPath = "frontend/components/layout/Navbar.tsx"

Write-Host "Switching to main and pulling latest..."
git checkout main 2>&1 | Out-Null
git pull origin main

Write-Host "Creating demo branch '$branch'..."
git branch -D $branch 2>&1 | Out-Null
git checkout -b $branch 2>&1 | Out-Null
Write-Host "On branch $branch"

Write-Host "Applying demo change (Login -> Sign In)..."
$content = Get-Content $navbarPath -Raw
$updated = $content -replace '>(\s*)Login(\s*)<', '>$1Sign In$2<'
if ($content -eq $updated) {
    Write-Host "No 'Login' text found in Navbar — already changed or wrong file."
    git checkout main 2>&1 | Out-Null
    exit 1
}
$updated | Set-Content $navbarPath -NoNewline

git add $navbarPath
git commit -m "demo: rename auth link Login -> Sign In to trigger code-change analysis"

Write-Host "Pushing '$branch' to origin..."
git push origin $branch --force 2>&1

git checkout main 2>&1 | Out-Null

Write-Host ""
Write-Host "Done. Workflow 'Code Change Analysis' is now running on GitHub Actions."
Write-Host "https://github.com/Stefgug/fwebsite/actions"
