# AWS Setup Guide (Console)

Manual, one-time setup for the AWS resources this project uses. Do this once;
after that, use `scripts/startup.sh` / `scripts/teardown.sh` for day-to-day work.

This project no longer uses AWS Glue — ETL (`etl/bronze_to_silver.py`,
`etl/silver_to_gold.py`) runs as standalone PySpark on your own machine, which
is free and has no AWS footprint. AWS is only used for **S3** (data lake) and
**RDS PostgreSQL** (gold layer). EC2 is optional (only needed if you want
ingestion to run on a schedule in the cloud instead of on your laptop).

## 1. Create the free-tier account

1. Go to `aws.amazon.com/free` → **Create a Free Account**.
2. Enter email, password, account name.
3. Choose account type **Personal**, fill in address/contact info.
4. Enter a card for identity verification (won't be charged if you stay in
   free tier limits).
5. Verify your phone number (SMS or call).
6. Select the **Basic support plan** (free).

## 2. Lock in cost protection (do this before anything else)

1. Console → search **Budgets** → **Create budget**.
2. Choose **Zero spend budget** (alerts the instant *any* charge appears) or a
   small fixed budget (e.g. $5).
3. Add your email as an alert recipient.
4. Console → **Billing** → **Billing Preferences** → enable "Receive Free Tier
   Usage Alerts".
5. Console → **Cost Explorer** → **Enable Cost Explorer** (needed for
   `scripts/cost_check.sh`; free to use, data lags ~24h).

## 3. Create an IAM user (never use root credentials in code)

1. Console → **IAM** → **Users** → **Create user**, e.g. `github-analytics-cli`.
2. Attach permissions: `AmazonS3FullAccess`, `AmazonRDSFullAccess` (fine for a
   personal learning project; for production scope this down to the specific
   bucket/instance ARNs).
3. **Security credentials** tab → **Create access key** → choose "Command
   Line Interface (CLI)" → save the Access Key ID + Secret.
4. Put them in your local `.env` as `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`,
   and run `aws configure` locally so the `scripts/*.sh` helpers work too.

## 4. Create the S3 bucket (Bronze/Silver data lake)

1. Console → **S3** → **Create bucket**.
2. Name must be globally unique, e.g. `github-analytics-data-lake-<yourname>`.
3. Region: match `AWS_REGION` in your `.env` (default `us-east-1`).
4. Keep **Block all public access** ON (this is private data).
5. Create. Update `S3_BUCKET_NAME` in `.env` to match.

No folders need pre-creating — the ingestion/ETL scripts write
`bronze/`, `silver/` prefixes automatically.

## 5. Create the RDS PostgreSQL instance (Gold layer)

1. Console → **RDS** → **Create database**.
2. Engine: **PostgreSQL** (15.x).
3. Templates: **Free tier**.
4. Settings:
   - DB instance identifier: `github-analytics-db` (matches the scripts'
     default `RDS_INSTANCE_ID` — override in `.env` if you name it differently)
   - Master username: `admin` (or your choice — match `RDS_USERNAME`)
   - Master password: set and save it — this goes in `RDS_PASSWORD`
5. Instance class: `db.t3.micro` (free tier eligible).
6. Storage: 20 GB gp2 (free tier includes up to 20GB).
7. Connectivity:
   - Public access: **Yes** (simplest for a personal project connecting from
     your laptop/FastAPI locally — for production, keep this private and
     connect via VPN/bastion instead).
   - VPC security group: create new, e.g. `github-analytics-db-sg`.
8. Create database (takes ~5-10 minutes).
9. Once available, open the security group (**EC2 → Security Groups**) and
   add an inbound rule: Type `PostgreSQL`, Port `5432`, Source = **your IP**
   (use "My IP" — do not open to `0.0.0.0/0`).
10. Copy the endpoint hostname into `.env` as `RDS_HOST`.

## 6. Load the schema

```bash
psql "postgresql://admin:<password>@<RDS_HOST>:5432/github_analytics" -f database/schema.sql
psql "postgresql://admin:<password>@<RDS_HOST>:5432/github_analytics" -f database/seed_dim_date.sql
```

(If `github_analytics` database doesn't exist yet, connect to the default
`postgres` db first and run `CREATE DATABASE github_analytics;`.)

## 7. (Optional) EC2 for scheduled ingestion

Only do this if you want ingestion to run unattended in the cloud instead of
from your own machine:

1. Console → **EC2** → **Launch instance**.
2. AMI: Amazon Linux 2023. Instance type: `t2.micro` (free tier).
3. Create/reuse a key pair for SSH.
4. Security group: allow SSH (port 22) from **your IP** only.
5. Launch, SSH in, install Python 3.11 + git, clone the repo, set up `.env`,
   and use `cron` to run `python ingestion/ingest.py` on schedule.
6. Add the instance ID to `.env` as `EC2_INSTANCE_ID` so `scripts/startup.sh`
   / `teardown.sh` can start/stop it for you.

If you skip this, just run `python ingestion/ingest.py` locally whenever you
want fresh data — this is the recommended path while learning, since it's
$0 and one less thing to remember to turn off.

## Full cleanup

When you're completely done with the project and want to delete everything
(no ongoing cost at all, including the few cents/month for stopped-RDS
storage):

```bash
aws rds delete-db-instance --db-instance-identifier github-analytics-db --skip-final-snapshot
aws s3 rb s3://<your-bucket-name> --force
# If you created an EC2 instance:
aws ec2 terminate-instances --instance-ids <instance-id>
```

Then in the console, delete the IAM user's access key and, optionally, the
IAM user itself.
