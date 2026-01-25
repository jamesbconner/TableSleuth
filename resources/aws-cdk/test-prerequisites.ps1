# TableSleuth CDK Prerequisites Test
Write-Host "`n=== TableSleuth CDK Prerequisites Check ===" -ForegroundColor Cyan

# Test Python
Write-Host "`n1. Python:" -ForegroundColor Yellow
python --version

# Test Node.js
Write-Host "`n2. Node.js:" -ForegroundColor Yellow
node --version

# Test AWS CLI
Write-Host "`n3. AWS CLI:" -ForegroundColor Yellow
aws --version

# Test AWS Credentials
Write-Host "`n4. AWS Credentials:" -ForegroundColor Yellow
aws sts get-caller-identity

# Test CDK
Write-Host "`n5. CDK CLI:" -ForegroundColor Yellow
cdk --version

# Get IP
Write-Host "`n6. Your Public IP:" -ForegroundColor Yellow
$myIP = Invoke-RestMethod -Uri "https://ifconfig.me/ip"
Write-Host "   IP: $myIP"
Write-Host "   SSH CIDR: $myIP/32"

Write-Host "`n=== Next Steps ===" -ForegroundColor Cyan
Write-Host "Set environment variables:"
Write-Host "  `$env:SSH_ALLOWED_CIDR = `"$myIP/32`""
Write-Host "  `$env:GIZMOSQL_PASSWORD = `"your-secure-password`""
Write-Host ""
