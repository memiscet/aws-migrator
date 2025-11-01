# Automated RDS Migration Script

## 🚀 Quick Start

Run the fully automated RDS migration script:

```bash
./automated_rds_migration.sh
```

That's it! The script handles everything automatically.

---

## ✨ What It Does Automatically

The script performs all these steps without manual intervention:

### ✅ **Step 1: Profile Verification**
- Validates `source_acc` and `target_acc` profiles
- Gets account IDs for both accounts

### ✅ **Step 2: RDS Discovery**
- Lists all RDS instances in source account
- Shows engine, class, storage, and encryption details
- Auto-selects if only one instance exists
- Otherwise prompts for selection

### ✅ **Step 3: Target VPC Subnet Discovery**
- Automatically fetches all subnets in target VPC
- Uses VPC: `vpc-0261473d76d9c5d21` (DEV-VPC1)
- Shows subnet details with CIDR and AZ

### ✅ **Step 4: DB Subnet Group Creation**
- Creates `migrated-db-subnet-group` automatically
- Uses all available subnets for high availability
- Skips if already exists

### ✅ **Step 5: Security Group Creation**
- Creates `migrated-rds-sg` automatically
- Auto-detects database port based on engine:
  - MySQL/MariaDB/Aurora MySQL: port 3306
  - PostgreSQL/Aurora PostgreSQL: port 5432
  - SQL Server: port 1433
  - Oracle: port 1521
- Adds inbound rule automatically

### ✅ **Step 6: Docker Image Build**
- Checks if Docker image exists
- Builds it if needed

### ✅ **Step 7: Migration Report Generation**
- Generates complete resource inventory
- Saves to `output/migration_report.json`

### ✅ **Step 8: IAM Policy Setup**
- Checks if IAM policies exist
- Creates them automatically if missing

### ✅ **Step 9: Dry-Run Validation**
- Runs complete dry-run migration
- Shows what will happen
- Validates all permissions

### ✅ **Step 10: Migration Execution**
- Prompts for final confirmation
- Executes actual migration:
  - Creates snapshot in source account
  - Grants KMS access (if encrypted)
  - Shares snapshot with target account
  - Copies snapshot to target account
  - Restores RDS instance in target account

### ✅ **Step 11: Verification**
- Checks migrated instance status
- Gets connection endpoint
- Displays results

### ✅ **Step 12: Summary Report**
- Shows complete migration details
- Lists output files
- Provides next steps

---

## 📋 Prerequisites

Before running the script, ensure:

1. **AWS Profiles Configured**
   ```bash
   aws configure --profile source_acc
   aws configure --profile target_acc
   ```

2. **Docker Installed**
   ```bash
   docker --version
   ```

3. **Script Permissions**
   ```bash
   chmod +x automated_rds_migration.sh
   ```

---

## 🎯 Target Configuration

The script is pre-configured for:

- **Target VPC**: `vpc-0261473d76d9c5d21`
- **VPC Name**: `DEV-VPC1`
- **VPC CIDR**: `10.1.0.0/16`

To change the target VPC, edit these lines in the script:

```bash
TARGET_VPC="vpc-0261473d76d9c5d21"
TARGET_VPC_NAME="DEV-VPC1"
TARGET_VPC_CIDR="10.1.0.0/16"
```

---

## 📊 Example Run

```bash
$ ./automated_rds_migration.sh

========================================
Automated RDS Migration to DEV-VPC1
========================================

========================================
Step 1: Verifying AWS Profiles
========================================
ℹ️  Checking source_acc profile...
✅ Source account: 111111111111
ℹ️  Checking target_acc profile...
✅ Target account: 222222222222

========================================
Step 2: Discovering RDS Instances in Source Account
========================================
ℹ️  Fetching RDS instances...

Available RDS instances:
------------------------
1) my-production-db
   Engine: mysql | Class: db.t3.medium | Storage: 100GB | Encrypted: True

✅ Auto-selected (only one instance): my-production-db
ℹ️  Detected database engine: mysql (port: 3306)

========================================
Step 3: Getting Subnets in Target VPC
========================================
ℹ️  Fetching subnets in vpc-0261473d76d9c5d21 (DEV-VPC1)...
✅ Found 3 subnets

--------------------------------------------
|           DescribeSubnets                |
+-----------------------+-----------------+
|  subnet-xxx          |  10.1.1.0/24    | us-east-1a |
|  subnet-yyy          |  10.1.2.0/24    | us-east-1b |
|  subnet-zzz          |  10.1.3.0/24    | us-east-1c |
+-----------------------+-----------------+

... [continues with all steps]

========================================
Migration Complete!
========================================

======================================
Migration Results
======================================
Source Instance:         my-production-db
Migrated Instance:       my-production-db-migrated
Status:                  creating
VPC:                     vpc-0261473d76d9c5d21 (DEV-VPC1)
Security Group:          sg-0abcd1234efgh5678
======================================

✅ All done! 🚀
```

---

## ⏱️ Migration Timeline

| Database Size | Total Time |
|--------------|------------|
| < 10 GB      | 15-30 min  |
| 10-50 GB     | 35-65 min  |
| 50-100 GB    | 65-95 min  |
| 100-500 GB   | 95-190 min |
| > 500 GB     | 3.5-7.5 hrs|

---

## 📁 Output Files

After migration, check:

```bash
output/
├── migration_report.json           # Complete resource inventory
├── vpc_migration_mapping.json      # Resource ID mappings
└── rds_migration_*.json            # RDS-specific details
```

---

## 🔧 Advanced Options

### Custom Target Configuration

Edit the script to customize:

```bash
# Line 20-24
TARGET_VPC="vpc-YOUR_VPC_ID"
TARGET_VPC_NAME="Your-VPC-Name"
TARGET_VPC_CIDR="10.x.0.0/16"
DB_SUBNET_GROUP_NAME="your-subnet-group"
SECURITY_GROUP_NAME="your-security-group"
```

### Skip Confirmation

To run completely non-interactive, modify line 369:

```bash
# Change from:
read -p "Execute actual migration? (yes/no): " CONFIRM

# To:
CONFIRM="yes"
```

### Custom Database Port

To override auto-detection, edit line 110:

```bash
DB_PORT=3306  # Force specific port
```

---

## 🛠️ Troubleshooting

### Issue: "source_acc profile not configured"

**Solution:**
```bash
aws configure --profile source_acc
# Enter access key, secret key, and region
```

### Issue: "No RDS instances found"

**Solution:**
```bash
# Verify you have RDS instances
aws rds describe-db-instances --profile source_acc
```

### Issue: "Docker image not found"

**Solution:**
```bash
# Build Docker image manually
docker build -t aws-migration-tool:latest .
```

### Issue: "DB subnet group already exists"

This is normal! The script will reuse the existing subnet group.

### Issue: "Security group already exists"

This is normal! The script will reuse the existing security group.

---

## 🔒 Security Notes

1. **KMS Keys**: The script automatically handles KMS grants for encrypted databases
2. **Security Groups**: Only allows access from within the VPC CIDR
3. **Credentials**: AWS credentials are read-only mounted in Docker
4. **Snapshots**: Source snapshots remain in source account for rollback

---

## 📞 Manual Verification

After migration completes:

```bash
# Check instance status
aws rds describe-db-instances \
  --db-instance-identifier YOUR_INSTANCE-migrated \
  --profile target_acc

# Get endpoint
aws rds describe-db-instances \
  --db-instance-identifier YOUR_INSTANCE-migrated \
  --profile target_acc \
  --query 'DBInstances[0].Endpoint.Address' \
  --output text

# Test connection
mysql -h YOUR_ENDPOINT -u admin -p  # For MySQL
psql -h YOUR_ENDPOINT -U postgres   # For PostgreSQL
```

---

## ✅ Post-Migration Checklist

- [ ] Verify instance is in "available" status
- [ ] Test database connectivity
- [ ] Verify all data is present
- [ ] Check row counts match source
- [ ] Update application connection strings
- [ ] Test application functionality
- [ ] Configure automated backups
- [ ] Set up monitoring and alarms
- [ ] Enable deletion protection
- [ ] Schedule source database deletion (after grace period)

---

## 🎯 Quick Commands Reference

```bash
# Run automated migration
./automated_rds_migration.sh

# Check migration report
cat output/migration_report.json | jq '.rds_instances'

# Monitor migrated instance
aws rds describe-db-instances \
  --db-instance-identifier DB_NAME-migrated \
  --profile target_acc

# View logs (if migration fails)
docker logs <container_id>
```

---

## 🚀 One-Command Migration

For completely automated migration (no interaction):

1. Edit the script and set `CONFIRM="yes"` on line 369
2. Run: `./automated_rds_migration.sh`

That's it! Go grab a coffee ☕ while the migration runs.

---

## 📈 What Happens During Migration

```
Source Account                    Target Account
     │                                  │
     ├─ RDS Instance                    │
     │                                  │
     ├─ Create Snapshot ────────────────┤
     │  (10-30 min)                     │
     │                                  │
     ├─ Grant KMS Access ───────────────┤
     │  (for encrypted DBs)             │
     │                                  │
     ├─ Share Snapshot ─────────────────┤
     │                                  │
     │                            Copy & Re-encrypt
     │                            (15-45 min)
     │                                  │
     │                            Restore DB Instance
     │                            (10-20 min)
     │                                  │
     │                              RDS Instance
     │                              (migrated)
```

---

**Your RDS migration is now fully automated!** 🎉

Just run `./automated_rds_migration.sh` and let it handle everything.
