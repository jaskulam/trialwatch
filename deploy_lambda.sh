#!/bin/bash
# deploy_lambda.sh - AWS Lambda deployment script

set -e

# Configuration
REGION="eu-west-1"
FUNCTION_NAME="ctis-harvester"
ECR_REPO_NAME="ctis-harvester"
IMAGE_TAG="latest"

# Get AWS account ID
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_URI="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"
FULL_IMAGE_URI="${ECR_URI}/${ECR_REPO_NAME}:${IMAGE_TAG}"

echo "🚀 Deploying CTIS Harvester to AWS Lambda"
echo "📍 Region: $REGION"
echo "🏷️  Function: $FUNCTION_NAME"
echo "📦 ECR: $FULL_IMAGE_URI"

# 1. Create ECR repository if it doesn't exist
echo "📦 Creating ECR repository..."
aws ecr create-repository \
    --repository-name $ECR_REPO_NAME \
    --region $REGION \
    --image-scanning-configuration scanOnPush=true \
    --encryption-configuration encryptionType=AES256 \
    2>/dev/null || echo "Repository already exists"

# 2. Get login token for ECR
echo "🔐 Logging into ECR..."
aws ecr get-login-password --region $REGION | \
    docker login --username AWS --password-stdin $ECR_URI

# 3. Build Docker image for ARM64 (Graviton)
echo "🏗️  Building Docker image for ARM64..."
docker build --platform linux/arm64 -t $ECR_REPO_NAME:$IMAGE_TAG .

# 4. Tag image for ECR
echo "🏷️  Tagging image..."
docker tag $ECR_REPO_NAME:$IMAGE_TAG $FULL_IMAGE_URI

# 5. Push image to ECR
echo "📤 Pushing image to ECR..."
docker push $FULL_IMAGE_URI

# 6. Create or update Lambda function
echo "⚡ Creating/updating Lambda function..."

# Check if function exists
if aws lambda get-function --function-name $FUNCTION_NAME --region $REGION >/dev/null 2>&1; then
    echo "🔄 Updating existing function..."
    aws lambda update-function-code \
        --function-name $FUNCTION_NAME \
        --image-uri $FULL_IMAGE_URI \
        --region $REGION \
        --architectures arm64
else
    echo "🆕 Creating new function..."
    
    # Create execution role if needed
    ROLE_NAME="ctis-harvester-role"
    ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${ROLE_NAME}"
    
    # Create role
    cat > trust-policy.json << EOF
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
EOF

    aws iam create-role \
        --role-name $ROLE_NAME \
        --assume-role-policy-document file://trust-policy.json \
        2>/dev/null || echo "Role already exists"
    
    # Attach policies
    aws iam attach-role-policy \
        --role-name $ROLE_NAME \
        --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
    
    aws iam attach-role-policy \
        --role-name $ROLE_NAME \
        --policy-arn arn:aws:iam::aws:policy/AmazonS3FullAccess
    
    # Wait for role propagation
    echo "⏳ Waiting for IAM role propagation..."
    sleep 10
    
    # Create function
    aws lambda create-function \
        --function-name $FUNCTION_NAME \
        --code ImageUri=$FULL_IMAGE_URI \
        --role $ROLE_ARN \
        --architectures arm64 \
        --memory-size 512 \
        --timeout 180 \
        --region $REGION \
        --package-type Image
fi

# 7. Set environment variables
echo "🔧 Setting environment variables..."
aws lambda update-function-configuration \
    --function-name $FUNCTION_NAME \
    --environment Variables="{
        AWS_REGION=eu-west-1,
        S3_BUCKET=ctis-raw,
        DOWNLOAD_TIMEOUT=90
    }" \
    --region $REGION

# 8. Create EventBridge rule for daily execution
echo "⏰ Setting up EventBridge cron..."
RULE_NAME="ctis-harvester-daily"

aws events put-rule \
    --name $RULE_NAME \
    --schedule-expression "cron(0 4 ? * * *)" \
    --description "Daily CTIS harvester execution at 06:00 CET" \
    --region $REGION

# Add permission for EventBridge to invoke Lambda
aws lambda add-permission \
    --function-name $FUNCTION_NAME \
    --statement-id "AllowEventBridge" \
    --action "lambda:InvokeFunction" \
    --principal events.amazonaws.com \
    --source-arn "arn:aws:events:${REGION}:${ACCOUNT_ID}:rule/${RULE_NAME}" \
    --region $REGION \
    2>/dev/null || echo "Permission already exists"

# Add Lambda target to EventBridge rule
aws events put-targets \
    --rule $RULE_NAME \
    --targets "Id"="1","Arn"="arn:aws:lambda:${REGION}:${ACCOUNT_ID}:function:${FUNCTION_NAME}" \
    --region $REGION

echo "✅ Deployment completed!"
echo "📊 Function details:"
aws lambda get-function \
    --function-name $FUNCTION_NAME \
    --region $REGION \
    --query 'Configuration.[FunctionName,Runtime,CodeSize,MemorySize,Timeout,LastModified]' \
    --output table

echo "⏰ Scheduled execution: Daily at 06:00 CET (04:00 UTC)"
echo "🎯 Next steps:"
echo "   1. Create S3 bucket: aws s3 mb s3://ctis-raw --region eu-west-1"
echo "   2. Test function: aws lambda invoke --function-name ctis-harvester /tmp/test-output.json"
echo "   3. Check logs: aws logs tail /aws/lambda/ctis-harvester --follow"

# Cleanup
rm -f trust-policy.json
