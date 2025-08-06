# AWS Lambda Deployment Guide

## Wymagania wstępne

1. **AWS CLI** zainstalowane i skonfigurowane
2. **Docker** zainstalowany (z obsługą multi-platform builds)
3. **AWS credentials** z odpowiednimi uprawnieniami

## Szybkie uruchomienie

### Windows (PowerShell):
```powershell
# 1. Przejdź do katalogu projektu
cd d:\trialwatch

# 2. Uruchom deployment
.\deploy_lambda.ps1

# 3. Utwórz S3 bucket
aws s3 mb s3://ctis-raw --region eu-west-1
```

### Linux/macOS (Bash):
```bash
# 1. Przejdź do katalogu projektu
cd /path/to/trialwatch

# 2. Nadaj uprawnienia
chmod +x deploy_lambda.sh

# 3. Uruchom deployment
./deploy_lambda.sh

# 4. Utwórz S3 bucket
aws s3 mb s3://ctis-raw --region eu-west-1
```

## Szczegółowe kroki

### 1. Przygotowanie środowiska AWS

```bash
# Sprawdź konfigurację AWS
aws sts get-caller-identity

# Sprawdź czy Docker działa
docker --version

# Sprawdź czy obsługiwane są multi-platform builds
docker buildx version
```

### 2. Utworzenie S3 bucket

```bash
# Utwórz bucket w eu-west-1
aws s3 mb s3://ctis-raw --region eu-west-1

# Ustaw lifecycle policy (opcjonalnie)
cat > lifecycle.json << EOF
{
    "Rules": [
        {
            "ID": "DeleteOldFiles",
            "Status": "Enabled",
            "Transitions": [
                {
                    "Days": 30,
                    "StorageClass": "STANDARD_IA"
                },
                {
                    "Days": 90,
                    "StorageClass": "GLACIER"
                }
            ],
            "Expiration": {
                "Days": 365
            }
        }
    ]
}
EOF

aws s3api put-bucket-lifecycle-configuration \
    --bucket ctis-raw \
    --lifecycle-configuration file://lifecycle.json
```

### 3. Test deployment

```bash
# Test lokalny
python test_lambda_local.py

# Test Lambda w AWS
aws lambda invoke \
    --function-name ctis-harvester \
    --payload '{"test": true}' \
    output.json

# Sprawdź wynik
cat output.json
```

### 4. Monitoring

```bash
# Sprawdź logi
aws logs tail /aws/lambda/ctis-harvester --follow

# Sprawdź metryki
aws cloudwatch get-metric-statistics \
    --namespace AWS/Lambda \
    --metric-name Duration \
    --dimensions Name=FunctionName,Value=ctis-harvester \
    --statistics Average \
    --start-time 2025-08-05T00:00:00Z \
    --end-time 2025-08-06T00:00:00Z \
    --period 3600
```

## Konfiguracja

### Environment Variables
```bash
AWS_REGION=eu-west-1
S3_BUCKET=ctis-raw
DOWNLOAD_TIMEOUT=90
```

### Lambda Configuration
- **Runtime**: Container Image (Python 3.12)
- **Architecture**: ARM64 (Graviton)
- **Memory**: 512 MB
- **Timeout**: 3 minutes (180 seconds)
- **Storage**: 512 MB

### EventBridge Schedule
- **Cron**: `cron(0 4 ? * * *)` 
- **Time**: 04:00 UTC = 06:00 CET (latem)
- **Frequency**: Daily

## Troubleshooting

### Problem z Docker multi-platform
```bash
# Utwórz buildx builder
docker buildx create --name multiplatform --use
docker buildx inspect --bootstrap
```

### Problem z uprawnieniami IAM
Wymagane uprawnienia:
- `lambda:*`
- `iam:CreateRole`, `iam:AttachRolePolicy`
- `ecr:*`
- `events:*`
- `s3:*`

### Problem z ECR login
```bash
# Re-login do ECR
aws ecr get-login-password --region eu-west-1 | \
    docker login --username AWS --password-stdin <account-id>.dkr.ecr.eu-west-1.amazonaws.com
```

### Debug Lambda errors
```bash
# Sprawdź szczegółowe logi
aws logs describe-log-groups --log-group-name-prefix "/aws/lambda/ctis-harvester"

# Pobierz ostatnie logi
aws logs get-log-events \
    --log-group-name "/aws/lambda/ctis-harvester" \
    --log-stream-name "$(aws logs describe-log-streams \
        --log-group-name "/aws/lambda/ctis-harvester" \
        --order-by LastEventTime \
        --descending \
        --limit 1 \
        --query 'logStreams[0].logStreamName' \
        --output text)"
```

## Aktualizacja

```bash
# Aktualizuj tylko kod (bez zmiany konfiguracji)
docker build --platform linux/arm64 -t ctis-harvester:latest .
docker tag ctis-harvester:latest <account-id>.dkr.ecr.eu-west-1.amazonaws.com/ctis-harvester:latest
docker push <account-id>.dkr.ecr.eu-west-1.amazonaws.com/ctis-harvester:latest

aws lambda update-function-code \
    --function-name ctis-harvester \
    --image-uri <account-id>.dkr.ecr.eu-west-1.amazonaws.com/ctis-harvester:latest
```

## Cleanup

```bash
# Usuń funkcję Lambda
aws lambda delete-function --function-name ctis-harvester

# Usuń EventBridge rule
aws events remove-targets --rule ctis-harvester-daily --ids 1
aws events delete-rule --name ctis-harvester-daily

# Usuń ECR repository
aws ecr delete-repository --repository-name ctis-harvester --force

# Usuń IAM role
aws iam detach-role-policy --role-name ctis-harvester-role --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
aws iam detach-role-policy --role-name ctis-harvester-role --policy-arn arn:aws:iam::aws:policy/AmazonS3FullAccess
aws iam delete-role --role-name ctis-harvester-role
```
