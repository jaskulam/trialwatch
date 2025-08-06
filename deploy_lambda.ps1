# deploy_lambda.ps1 - AWS Lambda deployment script for Windows

param(
    [string]$Region = "eu-west-1",
    [string]$FunctionName = "ctis-harvester",
    [string]$ECRRepoName = "ctis-harvester",
    [string]$ImageTag = "latest"
)

$ErrorActionPreference = "Stop"

Write-Host "🚀 Deploying CTIS Harvester to AWS Lambda" -ForegroundColor Green
Write-Host "📍 Region: $Region" -ForegroundColor Yellow
Write-Host "🏷️  Function: $FunctionName" -ForegroundColor Yellow

# Get AWS account ID
$AccountId = (aws sts get-caller-identity --query Account --output text)
$ECRUri = "$AccountId.dkr.ecr.$Region.amazonaws.com"
$FullImageUri = "$ECRUri/${ECRRepoName}:$ImageTag"

Write-Host "📦 ECR: $FullImageUri" -ForegroundColor Yellow

# 1. Create ECR repository
Write-Host "📦 Creating ECR repository..." -ForegroundColor Cyan
try {
    aws ecr create-repository `
        --repository-name $ECRRepoName `
        --region $Region `
        --image-scanning-configuration scanOnPush=true `
        --encryption-configuration encryptionType=AES256 2>$null
} catch {
    Write-Host "Repository already exists" -ForegroundColor Yellow
}

# 2. Login to ECR
Write-Host "🔐 Logging into ECR..." -ForegroundColor Cyan
aws ecr get-login-password --region $Region | docker login --username AWS --password-stdin $ECRUri

# 3. Build Docker image
Write-Host "🏗️  Building Docker image for ARM64..." -ForegroundColor Cyan
docker build --platform linux/arm64 -t "${ECRRepoName}:$ImageTag" .

# 4. Tag image
Write-Host "🏷️  Tagging image..." -ForegroundColor Cyan
docker tag "${ECRRepoName}:$ImageTag" $FullImageUri

# 5. Push image
Write-Host "📤 Pushing image to ECR..." -ForegroundColor Cyan
docker push $FullImageUri

# 6. Check if function exists
Write-Host "⚡ Creating/updating Lambda function..." -ForegroundColor Cyan
$FunctionExists = $false
try {
    aws lambda get-function --function-name $FunctionName --region $Region >$null 2>&1
    $FunctionExists = $true
} catch {
    $FunctionExists = $false
}

if ($FunctionExists) {
    Write-Host "🔄 Updating existing function..." -ForegroundColor Yellow
    aws lambda update-function-code `
        --function-name $FunctionName `
        --image-uri $FullImageUri `
        --region $Region `
        --architectures arm64
} else {
    Write-Host "🆕 Creating new function..." -ForegroundColor Yellow
    
    # Create execution role
    $RoleName = "ctis-harvester-role"
    $RoleArn = "arn:aws:iam::${AccountId}:role/${RoleName}"
    
    # Trust policy
    $TrustPolicy = @"
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
"@
    
    $TrustPolicy | Out-File -FilePath "trust-policy.json" -Encoding utf8
    
    try {
        aws iam create-role `
            --role-name $RoleName `
            --assume-role-policy-document file://trust-policy.json 2>$null
    } catch {
        Write-Host "Role already exists" -ForegroundColor Yellow
    }
    
    # Attach policies
    aws iam attach-role-policy `
        --role-name $RoleName `
        --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
    
    aws iam attach-role-policy `
        --role-name $RoleName `
        --policy-arn arn:aws:iam::aws:policy/AmazonS3FullAccess
    
    # Wait for role propagation
    Write-Host "⏳ Waiting for IAM role propagation..." -ForegroundColor Yellow
    Start-Sleep -Seconds 10
    
    # Create function
    aws lambda create-function `
        --function-name $FunctionName `
        --code ImageUri=$FullImageUri `
        --role $RoleArn `
        --architectures arm64 `
        --memory-size 512 `
        --timeout 180 `
        --region $Region `
        --package-type Image
}

# 7. Set environment variables
Write-Host "🔧 Setting environment variables..." -ForegroundColor Cyan
$EnvVars = @{
    "AWS_REGION" = "eu-west-1"
    "S3_BUCKET" = "ctis-raw"
    "DOWNLOAD_TIMEOUT" = "90"
}

$EnvVarsJson = $EnvVars | ConvertTo-Json -Compress
aws lambda update-function-configuration `
    --function-name $FunctionName `
    --environment "Variables=$EnvVarsJson" `
    --region $Region

# 8. Create EventBridge rule
Write-Host "⏰ Setting up EventBridge cron..." -ForegroundColor Cyan
$RuleName = "ctis-harvester-daily"

aws events put-rule `
    --name $RuleName `
    --schedule-expression "cron(0 4 ? * * *)" `
    --description "Daily CTIS harvester execution at 06:00 CET" `
    --region $Region

# Add permission for EventBridge
try {
    aws lambda add-permission `
        --function-name $FunctionName `
        --statement-id "AllowEventBridge" `
        --action "lambda:InvokeFunction" `
        --principal events.amazonaws.com `
        --source-arn "arn:aws:events:${Region}:${AccountId}:rule/${RuleName}" `
        --region $Region 2>$null
} catch {
    Write-Host "Permission already exists" -ForegroundColor Yellow
}

# Add target to EventBridge rule
aws events put-targets `
    --rule $RuleName `
    --targets "Id=1,Arn=arn:aws:lambda:${Region}:${AccountId}:function:${FunctionName}" `
    --region $Region

Write-Host "✅ Deployment completed!" -ForegroundColor Green

# Show function details
Write-Host "📊 Function details:" -ForegroundColor Cyan
aws lambda get-function `
    --function-name $FunctionName `
    --region $Region `
    --query 'Configuration.[FunctionName,Runtime,CodeSize,MemorySize,Timeout,LastModified]' `
    --output table

Write-Host "⏰ Scheduled execution: Daily at 06:00 CET (04:00 UTC)" -ForegroundColor Green
Write-Host "🎯 Next steps:" -ForegroundColor Yellow
Write-Host "   1. Create S3 bucket: aws s3 mb s3://ctis-raw --region eu-west-1" -ForegroundColor White
Write-Host "   2. Test function: aws lambda invoke --function-name ctis-harvester output.json" -ForegroundColor White
Write-Host "   3. Check logs: aws logs tail /aws/lambda/ctis-harvester --follow" -ForegroundColor White

# Cleanup
Remove-Item -Path "trust-policy.json" -Force -ErrorAction SilentlyContinue
