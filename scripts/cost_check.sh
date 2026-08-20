#!/usr/bin/env bash
# ============================================================
# Cost check — prints current month-to-date AWS spend and the
# live state of the resources this project uses, so you can
# see at a glance whether anything is running (and billing).
#
# Requires: AWS CLI v2, and an IAM identity with ce:GetCostAndUsage
#           (Cost Explorer must be enabled once in the Billing console —
#           it's free to enable and free to query at this volume).
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/../.env"

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

RDS_INSTANCE_ID="${RDS_INSTANCE_ID:-github-analytics-db}"
EC2_INSTANCE_ID="${EC2_INSTANCE_ID:-}"
AWS_REGION="${AWS_REGION:-us-east-1}"
S3_BUCKET_NAME="${S3_BUCKET_NAME:-github-analytics-data-lake}"

START_DATE=$(date -u +%Y-%m-01)
END_DATE=$(date -u -d tomorrow +%Y-%m-%d 2>/dev/null || date -u -v+1d +%Y-%m-%d)

echo "============================================================"
echo "  Resource status"
echo "============================================================"

RDS_STATUS=$(aws rds describe-db-instances \
  --db-instance-identifier "$RDS_INSTANCE_ID" \
  --region "$AWS_REGION" \
  --query 'DBInstances[0].DBInstanceStatus' --output text 2>/dev/null || echo "not-found")
echo "RDS ($RDS_INSTANCE_ID):  $RDS_STATUS"

if [[ -n "$EC2_INSTANCE_ID" ]]; then
  EC2_STATE=$(aws ec2 describe-instances \
    --instance-ids "$EC2_INSTANCE_ID" \
    --region "$AWS_REGION" \
    --query 'Reservations[0].Instances[0].State.Name' --output text 2>/dev/null || echo "not-found")
  echo "EC2 ($EC2_INSTANCE_ID):  $EC2_STATE"
else
  echo "EC2: not configured (EC2_INSTANCE_ID unset — assumed local ingestion)"
fi

BUCKET_SIZE=$(aws s3 ls "s3://$S3_BUCKET_NAME" --recursive --summarize 2>/dev/null \
  | grep "Total Size" || echo "  bucket not found or empty")
echo "S3 ($S3_BUCKET_NAME):  $BUCKET_SIZE"

echo
echo "============================================================"
echo "  Month-to-date cost ($START_DATE to $END_DATE)"
echo "============================================================"

aws ce get-cost-and-usage \
  --time-period "Start=$START_DATE,End=$END_DATE" \
  --granularity MONTHLY \
  --metrics "UnblendedCost" \
  --group-by Type=DIMENSION,Key=SERVICE \
  --region us-east-1 \
  --query 'ResultsByTime[0].Groups[?Metrics.UnblendedCost.Amount!=`0`].[Keys[0],Metrics.UnblendedCost.Amount]' \
  --output table 2>/dev/null || echo "Cost Explorer not enabled yet — enable it once in Billing > Cost Explorer (free), data appears ~24h later."

echo
echo "Tip: set a Budget alert in AWS Budgets so you get emailed before any real charge lands."
