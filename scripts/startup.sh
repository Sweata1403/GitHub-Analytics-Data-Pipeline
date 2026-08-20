#!/usr/bin/env bash
# ============================================================
# Startup script — brings AWS resources back online for a work session.
# Safe to re-run: skips anything already running.
# Requires: AWS CLI v2 configured (`aws configure`) with an IAM user
#           that has rds:*, ec2:* permissions.
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

echo "============================================================"
echo "  Starting AWS resources (region: $AWS_REGION)"
echo "============================================================"

# --- RDS ---
RDS_STATUS=$(aws rds describe-db-instances \
  --db-instance-identifier "$RDS_INSTANCE_ID" \
  --region "$AWS_REGION" \
  --query 'DBInstances[0].DBInstanceStatus' --output text 2>/dev/null || echo "not-found")

if [[ "$RDS_STATUS" == "not-found" ]]; then
  echo "RDS instance '$RDS_INSTANCE_ID' not found — create it first (see docs/aws_setup_guide.md)."
elif [[ "$RDS_STATUS" == "stopped" ]]; then
  echo "Starting RDS instance '$RDS_INSTANCE_ID'..."
  aws rds start-db-instance --db-instance-identifier "$RDS_INSTANCE_ID" --region "$AWS_REGION" >/dev/null
  echo "  Requested. This takes a few minutes — check with: aws rds describe-db-instances --db-instance-identifier $RDS_INSTANCE_ID"
else
  echo "RDS instance '$RDS_INSTANCE_ID' already in state: $RDS_STATUS"
fi

# --- EC2 (optional — only used if you run ingestion on EC2 instead of locally) ---
if [[ -n "$EC2_INSTANCE_ID" ]]; then
  EC2_STATE=$(aws ec2 describe-instances \
    --instance-ids "$EC2_INSTANCE_ID" \
    --region "$AWS_REGION" \
    --query 'Reservations[0].Instances[0].State.Name' --output text 2>/dev/null || echo "not-found")

  if [[ "$EC2_STATE" == "not-found" ]]; then
    echo "EC2 instance '$EC2_INSTANCE_ID' not found."
  elif [[ "$EC2_STATE" == "stopped" ]]; then
    echo "Starting EC2 instance '$EC2_INSTANCE_ID'..."
    aws ec2 start-instances --instance-ids "$EC2_INSTANCE_ID" --region "$AWS_REGION" >/dev/null
  else
    echo "EC2 instance '$EC2_INSTANCE_ID' already in state: $EC2_STATE"
  fi
else
  echo "EC2_INSTANCE_ID not set — skipping (fine if you ingest locally, not on EC2)."
fi

echo "============================================================"
echo "  Done. Run scripts/cost_check.sh anytime to see current spend."
echo "============================================================"
