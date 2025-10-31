# AWS Migration Workflow - Step by Step Guide

## 📋 Complete Migration Process

### Phase 1: Discovery & Planning

#### Step 1: Generate Migration Report
```bash
# Analyze all resources
docker run --rm \
  -v ~/.aws:/root/.aws:ro \
  -v $(pwd)/output:/output \
  aws-migration-tool:latest \
  python aws_migration.py --report
```

**Output:** `output/migration_report.json`

#### Step 2: Review the Report
```bash
# View summary
cat output/migration_report.json | jq '{
  ec2: (.ec2_instances | length),
  rds: (.rds_instances | length),
  vpcs: (.vpcs | length),
  kms_keys: (.kms_keys | length)
}'

# List all EC2 instances
cat output/migration_report.json | jq '.ec2_instances[] | {
  id: .instance_id,
  type: .instance_type,
  name: (.tags[] | select(.Key=="Name") | .Value),
  state: .state
}'

# List all RDS instances
cat output/migration_report.json | jq '.rds_instances[] | {
  id: .db_instance_identifier,
  engine: .engine,
  encrypted: .storage_encrypted,
  kms: .kms_key_id
}'
```

#### Step 3: Plan Your Migration
- [ ] Identify instances to migrate
- [ ] Schedule maintenance window
- [ ] Notify stakeholders (Insurance Pro, DWH teams)
- [ ] Create target VPC and subnets
- [ ] Create target DB subnet groups
- [ ] Create target security groups (or let tool create them)
- [ ] Create/import SSH keys in target account

---

### Phase 2: Pre-Migration Setup

#### Create Target Network Infrastructure

**Option A: Manual (AWS Console)**
1. Create VPC in target account
2. Create subnets (match source topology)
3. Create route tables
4. Create security groups

**Option B: Using Report as Reference**
```bash
# View source VPC structure
cat output/migration_report.json | jq '.vpcs[] | {
  vpc_id,
  cidr: .cidr_block,
  subnets: [.subnets[].cidr_block]
}'
```

#### Create SSH Keys
```bash
# Use generated script
chmod +x output/generate_ssh_keys.sh
./output/generate_ssh_keys.sh
```

#### Create KMS Keys (for encrypted RDS)
```bash
# If you have encrypted RDS instances, create KMS key in target
aws kms create-key \
  --description "RDS encryption key for migration" \
  --profile target_acc

# Create alias
aws kms create-alias \
  --alias-name alias/rds-encryption \
  --target-key-id <KEY_ID> \
  --profile target_acc
```

---

### Phase 3: Migration Execution

## 🖥️ EC2 Instance Migration

### Step-by-Step EC2 Migration

#### Step 1: Dry Run
```bash
# Always start with dry-run!
docker run --rm \
  -v ~/.aws:/root/.aws:ro \
  -v $(pwd)/output:/output \
  aws-migration-tool:latest \
  python aws_migration.py \
    --migrate-ec2 i-1234567890abcdef0 \
    --target-vpc vpc-xxxxx \
    --target-subnet subnet-xxxxx \
    --dry-run
```

**Review the dry-run output carefully!**

Expected steps shown:
1. ✅ Share and copy AMI
2. ✅ Create volume snapshots
3. ✅ Create/map security groups
4. ✅ Launch instance
5. ✅ Allocate Elastic IP (if needed)

#### Step 2: Execute Migration
```bash
# Remove --dry-run flag to execute
docker run --rm \
  -v ~/.aws:/root/.aws:ro \
  -v $(pwd)/output:/output \
  aws-migration-tool:latest \
  python aws_migration.py \
    --migrate-ec2 i-1234567890abcdef0 \
    --target-vpc vpc-xxxxx \
    --target-subnet subnet-xxxxx
```

**Timeline:** 15-30 minutes per instance

#### Step 3: Verify Migration
```bash
# Get instance details
aws ec2 describe-instances \
  --instance-ids <NEW_INSTANCE_ID> \
  --profile target_acc

# SSH into instance (use new key)
ssh -i output/<KEY_NAME>-migrated.pem ec2-user@<NEW_PRIVATE_IP>
```

**Verification Checklist:**
- [ ] Instance is running
- [ ] Can SSH into instance
- [ ] All volumes attached
- [ ] User data executed correctly
- [ ] Application is accessible
- [ ] Data is present

---

## 💾 RDS Instance Migration

### Step-by-Step RDS Migration

#### Step 1: Identify RDS Instance
```bash
# List RDS instances from report
cat output/migration_report.json | jq '.rds_instances[] | {
  id: .db_instance_identifier,
  engine: .engine,
  size: .allocated_storage,
  encrypted: .storage_encrypted,
  kms_key: .kms_key_id
}'
```

#### Step 2: Prepare Target Environment
```bash
# Create DB subnet group in target account
aws rds create-db-subnet-group \
  --db-subnet-group-name my-subnet-group \
  --db-subnet-group-description "Migration subnet group" \
  --subnet-ids subnet-xxx subnet-yyy \
  --profile target_acc

# Create security group for RDS
aws ec2 create-security-group \
  --group-name rds-migration-sg \
  --description "RDS security group" \
  --vpc-id vpc-xxxxx \
  --profile target_acc

# Add ingress rule (example: allow MySQL from app subnet)
aws ec2 authorize-security-group-ingress \
  --group-id sg-xxxxx \
  --protocol tcp \
  --port 3306 \
  --cidr 10.0.1.0/24 \
  --profile target_acc
```

#### Step 3: Dry Run RDS Migration
```bash
# For unencrypted RDS
docker run --rm \
  -v ~/.aws:/root/.aws:ro \
  -v $(pwd)/output:/output \
  aws-migration-tool:latest \
  python aws_migration.py \
    --migrate-rds mydb-instance \
    --target-subnet-group my-subnet-group \
    --target-security-groups sg-xxxxx \
    --dry-run

# For encrypted RDS (must specify KMS key)
docker run --rm \
  -v ~/.aws:/root/.aws:ro \
  -v $(pwd)/output:/output \
  aws-migration-tool:latest \
  python aws_migration.py \
    --migrate-rds mydb-instance \
    --target-subnet-group my-subnet-group \
    --target-security-groups sg-xxxxx \
    --target-kms-key arn:aws:kms:us-east-1:xxx:key/xxx \
    --dry-run
```

**Review the dry-run output:**
- Snapshot creation time estimate
- Re-encryption details (if encrypted)
- Restore configuration

#### Step 4: Execute RDS Migration

⚠️ **IMPORTANT:** This will take 30+ minutes!

```bash
# Execute migration
docker run --rm \
  -v ~/.aws:/root/.aws:ro \
  -v $(pwd)/output:/output \
  aws-migration-tool:latest \
  python aws_migration.py \
    --migrate-rds mydb-instance \
    --target-subnet-group my-subnet-group \
    --target-security-groups sg-xxxxx \
    --target-kms-key arn:aws:kms:us-east-1:xxx:key/xxx
```

**Timeline:**
- Snapshot creation: 10-30 minutes (depends on DB size)
- Snapshot copy: 5-15 minutes
- Database restore: 10-20 minutes
- **Total: 30-60+ minutes**

#### Step 5: Verify RDS Migration
```bash
# Get endpoint
aws rds describe-db-instances \
  --db-instance-identifier mydb-instance-migrated \
  --profile target_acc \
  --query 'DBInstances[0].Endpoint'

# Test connection
mysql -h <ENDPOINT> -u <USERNAME> -p

# Verify data
mysql -h <ENDPOINT> -u <USERNAME> -p -e "SELECT COUNT(*) FROM <TABLE>;"
```

**Verification Checklist:**
- [ ] Database is available
- [ ] Can connect to database
- [ ] All tables present
- [ ] Row counts match
- [ ] Application can query database
- [ ] Performance is acceptable

---

## 🔄 Migrate Multiple Instances

### Batch Migration Script

Create a script to migrate multiple instances:

```bash
#!/bin/bash
# migrate_batch.sh

# EC2 instances
EC2_INSTANCES=(
  "i-abc123:subnet-xxx"
  "i-def456:subnet-yyy"
)

TARGET_VPC="vpc-xxxxx"

for item in "${EC2_INSTANCES[@]}"; do
  IFS=':' read -r instance subnet <<< "$item"
  echo "Migrating EC2 instance: $instance"
  
  # Dry run first
  docker run --rm \
    -v ~/.aws:/root/.aws:ro \
    -v $(pwd)/output:/output \
    aws-migration-tool:latest \
    python aws_migration.py \
      --migrate-ec2 "$instance" \
      --target-vpc "$TARGET_VPC" \
      --target-subnet "$subnet" \
      --dry-run
  
  read -p "Proceed with migration? (y/n): " proceed
  if [ "$proceed" = "y" ]; then
    docker run --rm \
      -v ~/.aws:/root/.aws:ro \
      -v $(pwd)/output:/output \
      aws-migration-tool:latest \
      python aws_migration.py \
        --migrate-ec2 "$instance" \
        --target-vpc "$TARGET_VPC" \
        --target-subnet "$subnet"
  fi
  
  echo "Waiting 2 minutes before next migration..."
  sleep 120
done
```

---

## 📊 Post-Migration Tasks

### EC2 Post-Migration

1. **Update DNS Records**
```bash
# Update Route53 or your DNS
aws route53 change-resource-record-sets \
  --hosted-zone-id Z1234567890ABC \
  --change-batch file://dns-update.json \
  --profile target_acc
```

2. **Update Load Balancers**
```bash
# Register instance with target group
aws elbv2 register-targets \
  --target-group-arn <ARN> \
  --targets Id=<NEW_INSTANCE_ID> \
  --profile target_acc
```

3. **Test Application**
- Access application via new IP
- Test all functionality
- Check logs for errors
- Monitor performance

4. **Update Connection Strings**
- Update application configs
- Update monitoring tools
- Update backup scripts

### RDS Post-Migration

1. **Update Application Connection Strings**
```bash
# Example: Update environment variable
export DB_HOST=mydb-instance-migrated.xxx.rds.amazonaws.com
```

2. **Update External Integrations**
- Insurance Pro: Provide new endpoint
- DWH: Update ETL connection
- Monitoring tools: Update database URLs

3. **Verify Replication (if applicable)**
```bash
# Check replication lag
mysql -h <ENDPOINT> -u <USER> -p -e "SHOW SLAVE STATUS\G"
```

4. **Test Application Thoroughly**
- Run full regression tests
- Verify data writes
- Check query performance
- Test backup/restore

---

## 🛡️ Rollback Plan

### If Migration Fails

#### EC2 Rollback
```bash
# Terminate new instance
aws ec2 terminate-instances \
  --instance-ids <NEW_INSTANCE_ID> \
  --profile target_acc

# Start source instance (if stopped)
aws ec2 start-instances \
  --instance-ids <SOURCE_INSTANCE_ID> \
  --profile source_acc

# Revert DNS changes
# Revert load balancer changes
```

#### RDS Rollback
```bash
# Delete new RDS instance
aws rds delete-db-instance \
  --db-instance-identifier mydb-instance-migrated \
  --skip-final-snapshot \
  --profile target_acc

# Ensure source RDS is running
aws rds describe-db-instances \
  --db-instance-identifier mydb-instance \
  --profile source_acc
```

---

## 📝 Migration Tracking

### Create a Migration Log

```bash
# migration_log.md

## EC2 Migrations

| Source Instance | New Instance | Date | Status | Notes |
|----------------|--------------|------|--------|-------|
| i-abc123 | i-xyz789 | 2025-10-30 | ✅ Success | Web server |
| i-def456 | i-uvw012 | 2025-10-30 | ⏳ In Progress | App server |

## RDS Migrations

| Source DB | New DB | Date | Status | Notes |
|-----------|--------|------|--------|-------|
| prod-mysql | prod-mysql-migrated | 2025-10-30 | ✅ Success | 100GB DB |
```

---

## 🎯 Best Practices

1. **Always Dry Run First**
   - Never skip the dry-run step
   - Review output carefully
   - Verify all parameters

2. **Migrate During Maintenance Window**
   - Schedule after-hours
   - Notify all stakeholders
   - Have rollback plan ready

3. **One at a Time**
   - Migrate and verify each resource
   - Don't rush the process
   - Document each migration

4. **Keep Source Running**
   - Don't terminate source instances immediately
   - Wait 1-2 weeks for verification
   - Maintain backups

5. **Test Thoroughly**
   - Full application testing
   - Performance verification
   - Security validation

6. **Document Everything**
   - Keep migration logs
   - Note any issues
   - Document configuration changes

---

## 🆘 Troubleshooting

### Common Issues

**AMI Copy Fails**
```bash
# Check AMI sharing permissions
aws ec2 describe-image-attribute \
  --image-id ami-xxx \
  --attribute launchPermission \
  --profile source_acc
```

**KMS Re-encryption Fails**
```bash
# Verify KMS key exists and has correct permissions
aws kms describe-key \
  --key-id <KEY_ID> \
  --profile target_acc

# Check key policy allows RDS service
```

**RDS Snapshot Copy Timeout**
```bash
# Check snapshot status
aws rds describe-db-snapshots \
  --db-snapshot-identifier <SNAPSHOT_ID> \
  --profile target_acc
```

**Security Group Issues**
```bash
# Verify security group exists
aws ec2 describe-security-groups \
  --group-ids sg-xxx \
  --profile target_acc

# Check VPC association
```

---

## ✅ Final Checklist

Before declaring migration complete:

- [ ] All resources migrated
- [ ] All tests passed
- [ ] DNS updated
- [ ] Connection strings updated
- [ ] Monitoring configured
- [ ] Backups configured
- [ ] Documentation updated
- [ ] Stakeholders notified
- [ ] Source resources identified for decommission
- [ ] Post-migration review scheduled

---

**Need Help?** Review the full documentation in README.md and QUICK_REFERENCE.md
