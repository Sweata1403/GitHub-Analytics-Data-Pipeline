#!/usr/bin/env bash
# ============================================================
# Teardown script — stops billable AWS resources when you're
# done for the day. Does NOT delete anything (no data loss),
# it only stops compute so you're not charged for idle hours.
#
# Note: AWS auto-restarts a stopped RDS instance after 7 days,
# so re-run this script (or set a calendar reminder) weekly.
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
echo "  Stopping AWS resources (region: $AWS_REGION)"
echo "============================================================"

# --- RDS ---
RDS_STATUS=$(aws rds describe-db-instances \
  --db-instance-identifier "$RDS_INSTANCE_ID" \
  --region "$AWS_REGION" \
  --query 'DBInstances[0].DBInstanceStatus' --output text 2>/dev/null || echo "not-found")

if [[ "$RDS_STATUS" == "not-found" ]]; then
  echo "RDS instance '$RDS_INSTANCE_ID' not found — nothing to stop."
elif [[ "$RDS_STATUS" == "available" ]]; then
  echo "Stopping RDS instance '$RDS_INSTANCE_ID'..."
  aws rds stop-db-instance --db-instance-identifier "$RDS_INSTANCE_ID" --region "$AWS_REGION" >/dev/null
  echo "  Stop requested. Storage cost (a few cents/mo for small DBs) continues while stopped; compute cost stops."
else
  echo "RDS instance '$RDS_INSTANCE_ID' already in state: $RDS_STATUS (not 'available', skipping)"
fi

# --- EC2 (optional) ---
if [[ -n "$EC2_INSTANCE_ID" ]]; then
  EC2_STATE=$(aws ec2 describe-instances \
    --instance-ids "$EC2_INSTANCE_ID" \
    --region "$AWS_REGION" \
    --query 'Reservations[0].Instances[0].State.Name' --output text 2>/dev/null || echo "not-found")

  if [[ "$EC2_STATE" == "running" ]]; then
    echo "Stopping EC2 instance '$EC2_INSTANCE_ID'..."
    aws ec2 stop-instances --instance-ids "$EC2_INSTANCE_ID" --region "$AWS_REGION" >/dev/null
  else
    echo "EC2 instance '$EC2_INSTANCE_ID' state: $EC2_STATE (not 'running', skipping)"
  fi
else
  echo "EC2_INSTANCE_ID not set — skipping."
fi

echo "============================================================"
echo "  Done. S3 objects are NOT deleted (storage-only cost, ~cents/mo)."
echo "  To fully zero out costs, also see: docs/aws_setup_guide.md#full-cleanup"
echo "============================================================"
