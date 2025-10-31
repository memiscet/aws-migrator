# 🎯 AWS Migration Tool - Complete Features Overview

## 🌟 All Capabilities at a Glance

### 📊 Analysis & Reporting
- **Comprehensive Discovery** - Scans all EC2, RDS, VPC, and network resources
- **KMS Key Detection** - Identifies encryption keys and AWS vs customer-managed keys
- **JSON Export** - Complete migration report in machine-readable format
- **User Data Backup** - Extracts and saves instance user data scripts
- **SSH Key Documentation** - Lists all key pairs and generates creation scripts

### 🚀 Migration Operations

#### 1. VPC Migration (Full Infrastructure)
```bash
--migrate-vpc vpc-abc123 [--target-cidr 172.16.0.0/16] [--dry-run]
```

**Migrates:**
- ✅ VPC with CIDR block, DNS support, DNS hostnames
- ✅ All subnets with availability zone mapping
- ✅ Internet Gateway (created and attached)
- ✅ NAT Gateways (with new Elastic IPs)
- ✅ Security Groups (all ingress/egress rules)
- ✅ Inter-SG references (automatically mapped)
- ✅ Route Tables (all routes, IGW and NAT mapped)
- ✅ Subnet associations for route tables
- ✅ Network ACLs (all rules and associations)

**Output:** `vpc_migration_mapping.json` with all resource mappings

**Time:** 10-15 minutes

**Use Case:** Migrate entire network infrastructure before moving workloads

---

#### 2. EC2 Instance Migration (One-at-a-Time)
```bash
--migrate-ec2 i-abc123 --target-vpc vpc-xxx --target-subnet subnet-xxx [--target-security-groups sg1,sg2] [--dry-run]
```

**Process:**
1. Analyzes source instance configuration
2. Shares AMI with target account
3. Copies AMI to target region (if cross-region)
4. Creates snapshots of all EBS volumes
5. Waits for snapshots to complete
6. Creates/maps security groups in target
7. Launches new instance with all settings
8. Applies user data and tags
9. Allocates Elastic IP (if source had one)

**Time:** 15-30 minutes per instance

**Use Case:** Controlled, phased EC2 migration with verification between instances

---

#### 3. RDS Instance Migration (With KMS Re-encryption)
```bash
--migrate-rds mydb --target-subnet-group my-group [--target-kms-key arn:...] [--target-security-groups sg1,sg2] [--dry-run]
```

**Process:**
1. Analyzes source database configuration
2. Validates KMS key (if encrypted)
3. Creates DB snapshot in source account
4. Waits for snapshot completion (10-30 min)
5. Shares snapshot with target account
6. Copies snapshot to target with KMS re-encryption
7. Restores database in target account
8. Configures Multi-AZ, backups, maintenance windows
9. Waits for database to be available (10-20 min)
10. Returns new endpoint information

**Time:** 30-60+ minutes (depends on database size)

**Use Case:** Zero-downtime database migration with encryption key rotation

---

### 🧪 Dry-Run Mode

**Available for all operations:**
```bash
--dry-run  # Add to any command
```

**Shows:**
- Detailed step-by-step plan of what will happen
- Resources that will be created
- Time estimates
- Prerequisites and warnings
- No actual changes made to AWS

**Use Case:** Validate migration plans, get approvals, test configurations

---

### 🔐 KMS Encryption Handling

**Automatic Detection:**
- Identifies all KMS keys used by RDS and EBS volumes
- Distinguishes AWS-managed vs customer-managed keys
- Documents key aliases, descriptions, and tags

**Re-encryption Support:**
- RDS snapshot re-encryption during copy
- Target account KMS key validation
- Guidance for key recreation in target account

**Output:**
```json
{
  "kms_keys": [{
    "key_id": "arn:aws:kms:...",
    "aliases": ["alias/my-key"],
    "is_aws_managed": false,
    "key_state": "Enabled"
  }]
}
```

---

### 📝 Generated Outputs

| File | Purpose |
|------|---------|
| `migration_report.json` | Complete analysis of all resources |
| `user_data_backup.json` | All instance user data scripts |
| `generate_ssh_keys.sh` | Script to recreate SSH key pairs |
| `vpc_migration_mapping.json` | VPC resource ID mappings |

---

## 🎯 Migration Workflows

### Workflow 1: Full Account Migration

```bash
# Step 1: Analyze everything
docker run --rm -v ~/.aws:/root/.aws:ro -v $(pwd)/output:/output \
  aws-migration-tool:latest python aws_migration.py --report

# Step 2: Migrate VPC first (dry-run)
docker run --rm -v ~/.aws:/root/.aws:ro -v $(pwd)/output:/output \
  aws-migration-tool:latest python aws_migration.py \
  --migrate-vpc vpc-abc123 --dry-run

# Step 3: Execute VPC migration
docker run --rm -v ~/.aws:/root/.aws:ro -v $(pwd)/output:/output \
  aws-migration-tool:latest python aws_migration.py \
  --migrate-vpc vpc-abc123

# Step 4: Extract new VPC/subnet/SG IDs
NEW_VPC=$(cat output/vpc_migration_mapping.json | jq -r '.target_vpc_id')
NEW_SUBNET=$(cat output/vpc_migration_mapping.json | jq -r '.subnet_mapping | to_entries[0].value')
NEW_SGS=$(cat output/vpc_migration_mapping.json | jq -r '.sg_mapping | to_entries | map(.value) | join(",")')

# Step 5: Migrate EC2 instances (one at a time)
docker run --rm -v ~/.aws:/root/.aws:ro -v $(pwd)/output:/output \
  aws-migration-tool:latest python aws_migration.py \
  --migrate-ec2 i-instance1 --target-vpc $NEW_VPC --target-subnet $NEW_SUBNET --target-security-groups $NEW_SGS --dry-run

# Step 6: Create RDS subnet group in new VPC
aws rds create-db-subnet-group \
  --db-subnet-group-name migrated-subnet-group \
  --db-subnet-group-description "Migrated" \
  --subnet-ids subnet-xxx subnet-yyy \
  --profile target_acc

# Step 7: Migrate RDS instances
docker run --rm -v ~/.aws:/root/.aws:ro -v $(pwd)/output:/output \
  aws-migration-tool:latest python aws_migration.py \
  --migrate-rds mydb --target-subnet-group migrated-subnet-group --target-security-groups $NEW_SGS --dry-run
```

---

### Workflow 2: Single VPC Migration

```bash
# 1. Dry-run to validate
docker run --rm -v ~/.aws:/root/.aws:ro -v $(pwd)/output:/output \
  aws-migration-tool:latest python aws_migration.py \
  --migrate-vpc vpc-abc123 --dry-run

# 2. Review output

# 3. Execute
docker run --rm -v ~/.aws:/root/.aws:ro -v $(pwd)/output:/output \
  aws-migration-tool:latest python aws_migration.py \
  --migrate-vpc vpc-abc123

# 4. Verify
cat output/vpc_migration_mapping.json

# 5. Create VPC endpoints (manual)
aws ec2 create-vpc-endpoint \
  --vpc-id $NEW_VPC \
  --service-name com.amazonaws.us-east-1.s3 \
  --route-table-ids $NEW_RTB \
  --profile target_acc
```

---

### Workflow 3: EC2-Only Migration

```bash
# 1. Migrate single instance with dry-run
docker run --rm -v ~/.aws:/root/.aws:ro -v $(pwd)/output:/output \
  aws-migration-tool:latest python aws_migration.py \
  --migrate-ec2 i-abc123 --target-vpc vpc-existing --target-subnet subnet-existing --dry-run

# 2. Execute
docker run --rm -v ~/.aws:/root/.aws:ro -v $(pwd)/output:/output \
  aws-migration-tool:latest python aws_migration.py \
  --migrate-ec2 i-abc123 --target-vpc vpc-existing --target-subnet subnet-existing

# 3. Verify instance is running
aws ec2 describe-instances --instance-ids i-new123 --profile target_acc

# 4. Test connectivity

# 5. Repeat for next instance
```

---

## 🔧 Configuration Options

### Region Selection
```bash
--source-region us-east-1    # Source AWS region
--target-region us-west-2    # Target AWS region (supports cross-region)
```

### Profile Selection
```bash
--source-profile source_acc  # Source AWS CLI profile (default)
--target-profile target_acc  # Target AWS CLI profile (default)
```

### Filtering
```bash
--ec2-instances i-abc,i-def  # Analyze only specific EC2 instances
--rds-instances db1,db2      # Analyze only specific RDS instances
```

### VPC Options
```bash
--target-cidr 172.16.0.0/16  # Custom CIDR for VPC migration (optional)
```

### Security Options
```bash
--target-security-groups sg-xxx,sg-yyy  # Specific security groups for migration
```

### KMS Options
```bash
--target-kms-key arn:aws:kms:...  # Target KMS key for RDS re-encryption
```

---

## 📚 Documentation Files

| File | Description |
|------|-------------|
| **README.md** | Main documentation with setup and IAM policies |
| **QUICK_REFERENCE.md** | Command cheat sheet |
| **DOCKER_SETUP_GUIDE.md** | Complete Docker installation guide |
| **MIGRATION_WORKFLOW.md** | Step-by-step migration procedures |
| **NEW_FEATURES.md** | Dry-run and one-at-a-time migration details |
| **VPC_MIGRATION_GUIDE.md** | Comprehensive VPC migration guide |
| **VPC_MIGRATION_SUMMARY.md** | Quick VPC migration reference |
| **SUMMARY.md** | Overview of entire solution |
| **FEATURES_OVERVIEW.md** | This file - complete capabilities |

---

## ⏱️ Time Estimates

| Operation | Time | Notes |
|-----------|------|-------|
| Report Generation | 1-5 min | Depends on number of resources |
| VPC Migration | 10-15 min | NAT Gateways take longest |
| EC2 Migration | 15-30 min | AMI copy is slowest part |
| RDS Migration (Small) | 30-45 min | Snapshot and restore times |
| RDS Migration (Large) | 1-3 hours | Depends on database size |

---

## 💰 Cost Considerations

### One-Time Costs
- **Elastic IPs:** Free when associated, $0.005/hour unassociated
- **NAT Gateway:** $0.045/hour (starts immediately)
- **Data Transfer:** Cross-region transfer charges apply

### Ongoing Costs
- **NAT Gateway Data Processing:** $0.045/GB
- **EBS Snapshots:** $0.05/GB-month
- **AMI Storage:** Free (underlying snapshots charged)
- **VPC Endpoints:** $0.01/hour for interface endpoints

---

## ⚠️ Important Notes

### VPC Migration
- VPC Peering, VPN, Transit Gateway, and Direct Connect are NOT migrated
- VPC Endpoints must be recreated manually
- NAT Gateway Elastic IPs will be different
- Cross-region AZ mapping attempts to preserve suffix (e.g., -1a → -2a)

### EC2 Migration
- Source instance remains running (no downtime)
- New Elastic IP allocated if source had one
- User data is preserved
- IAM instance profiles must exist in target account

### RDS Migration
- Source database remains running (no downtime)
- Snapshot creation time varies by database size
- KMS re-encryption requires target account key
- Endpoint will be different - update application configs

### Cross-Account & Cross-Region
- IAM permissions required in both accounts
- Cross-region data transfer charges apply
- Some AWS services not available in all regions
- Availability Zone names may differ between regions

---

## 🛟 Support & Troubleshooting

### Common Issues

**Issue:** CIDR overlap
**Solution:** Use `--target-cidr` with different CIDR block

**Issue:** Security group dependencies
**Solution:** Script creates SGs in two passes automatically

**Issue:** NAT Gateway timeout
**Solution:** Wait 2-5 minutes (normal creation time)

**Issue:** AMI copy taking long
**Solution:** Large AMIs can take 10-20 minutes

**Issue:** Snapshot sharing denied
**Solution:** Verify target account ID is correct

---

## 🎓 Best Practices

1. **Always use --dry-run first**
2. **Test with non-production resources first**
3. **Migrate VPC before EC2/RDS**
4. **Migrate one resource at a time**
5. **Keep source resources running for 1-2 weeks**
6. **Save all mapping files**
7. **Document manual steps (VPC endpoints, etc.)**
8. **Update application configurations promptly**
9. **Verify functionality after each migration**
10. **Have rollback plan ready**

---

## 🚀 Quick Command Reference

```bash
# Analysis only
docker run --rm -v ~/.aws:/root/.aws:ro -v $(pwd)/output:/output \
  aws-migration-tool:latest python aws_migration.py --report

# VPC migration (dry-run)
docker run --rm -v ~/.aws:/root/.aws:ro -v $(pwd)/output:/output \
  aws-migration-tool:latest python aws_migration.py --migrate-vpc vpc-xxx --dry-run

# VPC migration (execute)
docker run --rm -v ~/.aws:/root/.aws:ro -v $(pwd)/output:/output \
  aws-migration-tool:latest python aws_migration.py --migrate-vpc vpc-xxx

# EC2 migration (dry-run)
docker run --rm -v ~/.aws:/root/.aws:ro -v $(pwd)/output:/output \
  aws-migration-tool:latest python aws_migration.py --migrate-ec2 i-xxx \
  --target-vpc vpc-yyy --target-subnet subnet-zzz --dry-run

# RDS migration (dry-run)
docker run --rm -v ~/.aws:/root/.aws:ro -v $(pwd)/output:/output \
  aws-migration-tool:latest python aws_migration.py --migrate-rds mydb \
  --target-subnet-group my-group --target-kms-key arn:... --dry-run
```

---

**Need Help?** Check the detailed guides in the documentation files above!
