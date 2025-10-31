# AWS Migration Tool - Quick Reference

## 🚀 Quick Start Commands

### 1. First Time Setup (One-time)
```bash
# Setup AWS credentials
./setup_credentials.sh

# Build Docker image and run analysis
./run_migration.sh
```

### 2. Run Migration Analysis
```bash
# Using the automated script (recommended)
./run_migration.sh

# OR using Docker Compose
docker-compose up

# OR using Docker directly
docker run --rm \
  -v ~/.aws:/root/.aws:ro \
  -v $(pwd)/output:/output \
  aws-migration-tool:latest \
  python aws_migration.py --report
```

### 3. Migrate Individual Resources (NEW!)

#### VPC Migration
```bash
# DRY RUN first (shows what will be created)
docker run --rm \
  -v ~/.aws:/root/.aws:ro \
  -v $(pwd)/output:/output \
  aws-migration-tool:latest \
  python aws_migration.py \
    --migrate-vpc vpc-abc123def456 \
    --dry-run

# Actual VPC migration (uses source CIDR)
docker run --rm \
  -v ~/.aws:/root/.aws:ro \
  -v $(pwd)/output:/output \
  aws-migration-tool:latest \
  python aws_migration.py \
    --migrate-vpc vpc-abc123def456

# VPC migration with custom CIDR
docker run --rm \
  -v ~/.aws:/root/.aws:ro \
  -v $(pwd)/output:/output \
  aws-migration-tool:latest \
  python aws_migration.py \
    --migrate-vpc vpc-abc123def456 \
    --target-cidr 172.16.0.0/16
```

#### EC2 Instance Migration
```bash
# DRY RUN first (always recommended)
docker run --rm \
  -v ~/.aws:/root/.aws:ro \
  -v $(pwd)/output:/output \
  aws-migration-tool:latest \
  python aws_migration.py \
    --migrate-ec2 i-1234567890abcdef0 \
    --target-vpc vpc-xxxxx \
    --target-subnet subnet-xxxxx \
    --dry-run

# Actual migration (after reviewing dry-run)
docker run --rm \
  -v ~/.aws:/root/.aws:ro \
  -v $(pwd)/output:/output \
  aws-migration-tool:latest \
  python aws_migration.py \
    --migrate-ec2 i-1234567890abcdef0 \
    --target-vpc vpc-xxxxx \
    --target-subnet subnet-xxxxx

# With specific security groups
docker run --rm \
  -v ~/.aws:/root/.aws:ro \
  -v $(pwd)/output:/output \
  aws-migration-tool:latest \
  python aws_migration.py \
    --migrate-ec2 i-1234567890abcdef0 \
    --target-vpc vpc-xxxxx \
    --target-subnet subnet-xxxxx \
    --target-security-groups sg-xxx,sg-yyy
```

#### RDS Instance Migration
```bash
# DRY RUN first
docker run --rm \
  -v ~/.aws:/root/.aws:ro \
  -v $(pwd)/output:/output \
  aws-migration-tool:latest \
  python aws_migration.py \
    --migrate-rds mydb-instance \
    --target-subnet-group my-subnet-group \
    --dry-run

# Actual migration
docker run --rm \
  -v ~/.aws:/root/.aws:ro \
  -v $(pwd)/output:/output \
  aws-migration-tool:latest \
  python aws_migration.py \
    --migrate-rds mydb-instance \
    --target-subnet-group my-subnet-group

# With KMS encryption
docker run --rm \
  -v ~/.aws:/root/.aws:ro \
  -v $(pwd)/output:/output \
  aws-migration-tool:latest \
  python aws_migration.py \
    --migrate-rds mydb-instance \
    --target-subnet-group my-subnet-group \
    --target-kms-key arn:aws:kms:us-east-1:xxx:key/xxx \
    --target-security-groups sg-xxx,sg-yyy
```

## 📦 Docker Commands

### Build Image
```bash
docker build -t aws-migration-tool:latest .
```

### Run with All Resources
```bash
docker run --rm \
  -v ~/.aws:/root/.aws:ro \
  -v $(pwd)/output:/output \
  aws-migration-tool:latest \
  python aws_migration.py --report
```

### Run with Specific EC2 Instances
```bash
docker run --rm \
  -v ~/.aws:/root/.aws:ro \
  -v $(pwd)/output:/output \
  aws-migration-tool:latest \
  python aws_migration.py --report --ec2-instances i-abc123,i-def456
```

### Run with Specific RDS Instances
```bash
docker run --rm \
  -v ~/.aws:/root/.aws:ro \
  -v $(pwd)/output:/output \
  aws-migration-tool:latest \
  python aws_migration.py --report --rds-instances mydb1,mydb2
```

### Run with Custom Region
```bash
docker run --rm \
  -v ~/.aws:/root/.aws:ro \
  -v $(pwd)/output:/output \
  aws-migration-tool:latest \
  python aws_migration.py --report \
  --source-region us-west-2 \
  --target-region us-west-2
```

### Interactive Shell
```bash
docker run --rm -it \
  -v ~/.aws:/root/.aws:ro \
  -v $(pwd)/output:/output \
  aws-migration-tool:latest \
  /bin/bash
```

## 📊 View Reports

### View Migration Report
```bash
# Pretty print JSON
cat output/migration_report.json | jq .

# View metadata
cat output/migration_report.json | jq '.metadata'

# Count resources
cat output/migration_report.json | jq '.ec2_instances | length'
cat output/migration_report.json | jq '.rds_instances | length'
cat output/migration_report.json | jq '.vpcs | length'

# List EC2 instances
cat output/migration_report.json | jq '.ec2_instances[] | {id: .instance_id, type: .instance_type}'

# List RDS instances
cat output/migration_report.json | jq '.rds_instances[] | {id: .db_instance_identifier, engine: .engine}'

# Check for encrypted resources
cat output/migration_report.json | jq '.rds_instances[] | select(.storage_encrypted == true)'

# List KMS keys
cat output/migration_report.json | jq '.kms_keys'
```

## 🔧 Troubleshooting Commands

### Test AWS Credentials
```bash
# Test source account
docker run --rm \
  -v ~/.aws:/root/.aws:ro \
  aws-migration-tool:latest \
  aws sts get-caller-identity --profile source_acc

# Test target account
docker run --rm \
  -v ~/.aws:/root/.aws:ro \
  aws-migration-tool:latest \
  aws sts get-caller-identity --profile target_acc
```

### Check Docker Image
```bash
# List images
docker images | grep aws-migration

# Remove old image
docker rmi aws-migration-tool:latest

# Rebuild from scratch
docker build --no-cache -t aws-migration-tool:latest .
```

### View Container Logs
```bash
# If using docker-compose
docker-compose logs

# If running container in background
docker logs aws-migration
```

### Clean Up
```bash
# Remove output files
rm -rf output/*

# Remove containers
docker rm aws-migration

# Remove image
docker rmi aws-migration-tool:latest

# Full cleanup
docker-compose down
docker rmi aws-migration-tool:latest
rm -rf output/*
```

## 🔑 AWS Profile Setup

### Manual Profile Creation

Edit `~/.aws/credentials`:
```ini
[source_acc]
aws_access_key_id = YOUR_SOURCE_ACCESS_KEY
aws_secret_access_key = YOUR_SOURCE_SECRET_KEY
region = us-east-1

[target_acc]
aws_access_key_id = YOUR_TARGET_ACCESS_KEY
aws_secret_access_key = YOUR_TARGET_SECRET_KEY
region = us-east-1
```

### Using AWS CLI
```bash
# Configure source account
aws configure --profile source_acc

# Configure target account
aws configure --profile target_acc

# Test profiles
aws sts get-caller-identity --profile source_acc
aws sts get-caller-identity --profile target_acc
```

## 📝 Common Use Cases

### Use Case 1: Full Environment Migration
```bash
# 1. Analyze everything
./run_migration.sh

# 2. Review report
cat output/migration_report.json | jq .

# 3. Generate SSH keys
chmod +x output/generate_ssh_keys.sh
./output/generate_ssh_keys.sh
```

### Use Case 2: Single Instance Migration
```bash
# Analyze specific instance
docker run --rm \
  -v ~/.aws:/root/.aws:ro \
  -v $(pwd)/output:/output \
  aws-migration-tool:latest \
  python aws_migration.py --report --ec2-instances i-1234567890abcdef0

# Review
cat output/migration_report.json | jq '.ec2_instances[0]'
```

### Use Case 3: Database Only Migration
```bash
# Analyze RDS instances
docker run --rm \
  -v ~/.aws:/root/.aws:ro \
  -v $(pwd)/output:/output \
  aws-migration-tool:latest \
  python aws_migration.py --report --rds-instances mydb

# Check KMS keys
cat output/migration_report.json | jq '.kms_keys'
```

### Use Case 4: Multi-Region Migration
```bash
# Migrate from us-east-1 to us-west-2
docker run --rm \
  -v ~/.aws:/root/.aws:ro \
  -v $(pwd)/output:/output \
  aws-migration-tool:latest \
  python aws_migration.py --report \
  --source-region us-east-1 \
  --target-region us-west-2
```

## 🐛 Debugging

### Enable Verbose Output
```bash
# Add debug flag (if implemented)
docker run --rm \
  -v ~/.aws:/root/.aws:ro \
  -v $(pwd)/output:/output \
  aws-migration-tool:latest \
  python aws_migration.py --report --verbose
```

### Check AWS SDK Configuration
```bash
docker run --rm -it \
  -v ~/.aws:/root/.aws:ro \
  aws-migration-tool:latest \
  /bin/bash -c "cat /root/.aws/credentials"
```

### Test Network Connectivity
```bash
docker run --rm -it \
  -v ~/.aws:/root/.aws:ro \
  aws-migration-tool:latest \
  /bin/bash -c "ping -c 3 amazonaws.com"
```

## 📋 Pre-Migration Checklist

- [ ] AWS credentials configured for both accounts
- [ ] Appropriate IAM permissions granted
- [ ] Docker installed and running
- [ ] Maintenance window scheduled
- [ ] Stakeholders notified (Insurance Pro, DWH)
- [ ] Backup strategy confirmed
- [ ] Rollback plan prepared
- [ ] Output directory has write permissions

## 🔒 Security Notes

- **Never commit** AWS credentials to git
- Output files may contain **sensitive information** - handle carefully
- Use **IAM roles** with minimum required permissions
- **Rotate credentials** regularly
- Enable **CloudTrail** for audit logging

## 📞 Getting Help

```bash
# View help
docker run --rm aws-migration-tool:latest python aws_migration.py --help

# View version
docker run --rm aws-migration-tool:latest python --version

# Check AWS CLI version
docker run --rm aws-migration-tool:latest aws --version
```
