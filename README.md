# AWS Cross-Account Migration Tool

Docker-based solution for migrating AWS resources (EC2, RDS, VPC, etc.) between AWS accounts.

## 📋 Features

### ✅ EC2 Instance Migration (NEW!)
- **Automated Instance Migration**: Complete EC2 instance migration with all configurations
- **Security Group Dependencies**: Automatic detection and resolution of SG references
- **AMI & Snapshot Handling**: Encrypted AMI/snapshot sharing with KMS grants
- **Volume Migration**: All attached EBS volumes migrated with snapshots
- **Elastic IP**: Automatic allocation and association
- **Key Pair Validation**: Ensures key pairs exist in target account
- **Interactive Script**: 12-step guided workflow with dry-run option

### ✅ RDS Database Migration
- **Database Instances**: PostgreSQL, MySQL, MariaDB, SQL Server, Oracle
- **Aurora Clusters**: Full cluster migration support
- **KMS Encryption**: Automatic KMS key recreation and snapshot re-encryption
- **AWS-Managed Keys**: Automatic re-encryption from aws/rds to customer-managed keys
- **Performance**: 18-20 minutes per database migration
- **Infrastructure Reuse**: Subnet groups and security groups reused across migrations

### ✅ Network Migration
- **VPCs**: Complete VPC configuration
- **Subnets**: All subnets with availability zones
- **Security Groups**: With automatic dependency resolution
- **Route Tables**: Including routes and associations
- **NACLs**: Network access control lists

### ✅ Encryption & Security
- **KMS Handling**: Automatic key detection (AWS-managed vs customer-managed)
- **Cross-Account Access**: KMS grants and policies configured automatically
- **Re-encryption**: AWS-managed keys re-encrypted to customer-managed keys
- **IAM Policies**: Comprehensive permission templates

### ✅ Migration Workflow
- **Discovery**: Automatic resource inventory
- **Dry Run**: Validation without making changes
- **Execution**: Actual migration with progress tracking
- **Reporting**: Detailed JSON reports and timing summaries
- **Validation**: Post-migration verification steps

## 🚀 Quick Start

### Prerequisites

- Docker installed on your machine
- AWS credentials for both source and target accounts
- Appropriate IAM permissions in both accounts

### Setup

1. **Clone or create the project directory:**
   ```bash
   cd /Users/memiscet/repos/contract/
   ```

2. **Set up AWS credentials:**
   
   **Option A: Interactive Setup (Recommended)**
   ```bash
   chmod +x setup_credentials.sh
   ./setup_credentials.sh
   ```
   
   The script will prompt you for:
   - Source account AWS Access Key ID and Secret Access Key
   - Target account AWS Access Key ID and Secret Access Key
   - AWS regions for each account (default: us-east-1)
   
   This creates two profiles in `~/.aws/credentials`:
   - `source_acc` - Your source AWS account
   - `target_acc` - Your target AWS account

   **Option B: Manual Setup**
   
   Edit `~/.aws/credentials` and add:
   ```ini
   [source_acc]
   aws_access_key_id = YOUR_SOURCE_ACCESS_KEY
   aws_secret_access_key = YOUR_SOURCE_SECRET_KEY
   region = us-east-1

   [target_acc]
   aws_access_key_id = YOUR_TARGET_ACCESS_KEY
   aws_secret_access_key = YOUR_TARGET_SECRET_KEY
   region = us-west-2
   ```

   **Verify Your Setup:**
   ```bash
   aws ec2 describe-vpcs --profile source_acc
   aws ec2 describe-vpcs --profile target_acc
   ```

3. **Setup IAM Permissions (Automated):**
   
   The tool can automatically create required IAM policies in both accounts:
   
   ```bash
   # First, build the Docker image
   docker build -t aws-migration-tool:latest .
   
   # Preview what policies will be created (dry-run)
   docker run --rm -v ~/.aws:/root/.aws:ro aws-migration-tool:latest \
     python aws_migration.py --setup-policies --dry-run
   
   # Actually create the policies
   docker run --rm -v ~/.aws:/root/.aws:ro aws-migration-tool:latest \
     python aws_migration.py --setup-policies
   ```
   
   This creates two managed policies:
   - **Source Account**: `AWSMigrationToolSourcePolicy` (read/snapshot permissions)
   - **Target Account**: `AWSMigrationToolTargetPolicy` (full migration permissions)
   
   After creation, attach the policies to your IAM users:
   ```bash
   # In source account
   aws iam attach-user-policy --user-name YOUR_USER \
     --policy-arn arn:aws:iam::SOURCE_ACCOUNT_ID:policy/AWSMigrationToolSourcePolicy
   
   # In target account
   aws iam attach-user-policy --user-name YOUR_USER \
     --policy-arn arn:aws:iam::TARGET_ACCOUNT_ID:policy/AWSMigrationToolTargetPolicy
   ```
   
   **Or manually set up permissions:**
   
   <details>
   <summary>Click to see manual IAM permissions</summary>
   
   Ensure both profiles have the following permissions:
   
   **For VPC Migration:**
   - `ec2:Describe*` (VPCs, subnets, security groups, route tables, NAT gateways, Internet gateways)
   - `ec2:Create*` (VPCs, subnets, security groups, route tables, NAT gateways, Internet gateways)
   - `ec2:Authorize*` (security group rules)
   - `ec2:AllocateAddress`, `ec2:AssociateAddress` (Elastic IPs for NAT gateways)
   
   **For EC2 Migration:**
   - `ec2:DescribeInstances`, `ec2:DescribeImages`, `ec2:DescribeVolumes`, `ec2:DescribeSnapshots`
   - `ec2:CreateImage`, `ec2:CopyImage`, `ec2:RunInstances`
   - `ec2:CreateTags`, `ec2:CopySnapshot`, `ec2:CreateVolume`
   
   **For RDS Migration:**
   - `rds:Describe*` (DB instances, DB snapshots, DB clusters)
   - `rds:CreateDBSnapshot`, `rds:CopyDBSnapshot`
   - `rds:RestoreDBInstanceFromDBSnapshot`, `rds:ModifyDBInstance`
   
   **For KMS (if using encryption):**
   - `kms:CreateGrant`, `kms:Decrypt`, `kms:DescribeKey`, `kms:CreateKey`
   - `kms:ListAliases`, `kms:CreateAlias`
   
   </details>

4. **Build the Docker image (if not done already):**
   ```bash
   docker build -t aws-migration-tool:latest .
   ```

## 📦 Usage

### Option 1: Using Docker Compose (Recommended)

```bash
# Generate migration report (dry-run)
docker-compose up

# View the output
cat output/migration_report.json
```

### Option 2: Using Docker directly

#### Generate Migration Report
```bash
docker run --rm \
  -v ~/.aws:/root/.aws:ro \
  -v $(pwd)/output:/output \
  aws-migration-tool:latest \
  python aws_migration.py --report
```

#### Specify Custom Region
```bash
docker run --rm \
  -v ~/.aws:/root/.aws:ro \
  -v $(pwd)/output:/output \
  aws-migration-tool:latest \
  python aws_migration.py \
    --report \
    --source-region us-west-2 \
    --target-region us-west-2
```

#### Analyze Specific EC2 Instances
```bash
docker run --rm \
  -v ~/.aws:/root/.aws:ro \
  -v $(pwd)/output:/output \
  aws-migration-tool:latest \
  python aws_migration.py \
    --report \
    --ec2-instances i-abc123,i-def456
```

#### Analyze Specific RDS Instances
```bash
docker run --rm \
  -v ~/.aws:/root/.aws:ro \
  -v $(pwd)/output:/output \
  aws-migration-tool:latest \
  python aws_migration.py \
    --report \
    --rds-instances mydb-instance-1,mydb-instance-2
```

### Option 3: Interactive Shell

```bash
# Start an interactive shell in the container
docker run --rm -it \
  -v ~/.aws:/root/.aws:ro \
  -v $(pwd)/output:/output \
  aws-migration-tool:latest \
  /bin/bash

# Inside the container, run commands:
python aws_migration.py --report
python aws_migration.py --report --source-region us-west-2
```

## 📂 Output Files

After running the tool, check the `output/` directory:

- **migration_report.json** - Complete inventory of all resources
- **user_data_backup.json** - Backup of EC2 instance user data
- **generate_ssh_keys.sh** - Script to create new SSH keys in target account

## 🔧 Docker Commands Reference

### Build Commands

```bash
# Build the image
docker build -t aws-migration-tool:latest .

# Build with no cache
docker build --no-cache -t aws-migration-tool:latest .

# Build using docker-compose
docker-compose build
```

### Run Commands

```bash
# Run with docker-compose
docker-compose up

# Run detached
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

### Cleanup Commands

```bash
# Remove container
docker rm aws-migration

# Remove image
docker rmi aws-migration-tool:latest

# Clean up everything
docker-compose down
docker rmi aws-migration-tool:latest
```

## 🛠️ Advanced Usage

### Custom AWS Profiles

If you're using different AWS profile names:

```bash
docker run --rm \
  -v ~/.aws:/root/.aws:ro \
  -v $(pwd)/output:/output \
  aws-migration-tool:latest \
  python aws_migration.py \
    --report \
    --source-profile my-source-profile \
    --target-profile my-target-profile
```

### Multiple Regions

```bash
docker run --rm \
  -v ~/.aws:/root/.aws:ro \
  -v $(pwd)/output:/output \
  aws-migration-tool:latest \
  python aws_migration.py \
    --report \
    --source-region eu-west-1 \
    --target-region eu-west-1
```

### Environment Variables

You can also set environment variables:

```bash
docker run --rm \
  -v ~/.aws:/root/.aws:ro \
  -v $(pwd)/output:/output \
  -e AWS_DEFAULT_REGION=us-west-2 \
  aws-migration-tool:latest \
  python aws_migration.py --report
```

## 📊 Understanding the Report

The migration report includes:

1. **EC2 Instances:**
   - Instance details (type, state, IPs)
   - AMI information
   - Security groups
   - EBS volumes
   - User data
   - SSH keys

2. **RDS Instances:**
   - Database configuration
   - Engine and version
   - Storage details
   - **KMS encryption keys**
   - Backup settings
   - Multi-AZ configuration

3. **Network Infrastructure:**
   - VPCs and CIDR blocks
   - Subnets and availability zones
   - Route tables
   - Security group rules
   - Network ACLs

4. **KMS Keys:**
   - Key IDs and aliases
   - Encryption status
   - AWS-managed vs customer-managed

## 🔐 KMS Key Handling

The tool automatically handles KMS-encrypted resources:

1. **Detection**: Identifies all KMS keys used for encryption
2. **Recreation**: Creates equivalent keys in target account
3. **Re-encryption**: Snapshots are re-encrypted with target keys
4. **AWS-Managed Keys**: Uses default AWS-managed keys in target

## 📝 Migration Workflow

1. **Generate Report (Dry-Run)**
   ```bash
   docker-compose up
   ```

2. **Review Output**
   ```bash
   cat output/migration_report.json
   ```

3. **Plan Maintenance Window**
   - Review with stakeholders
   - Schedule downtime
   - Prepare rollback plan

4. **Create SSH Keys**
   ```bash
   # Extract the script from container
   docker run --rm \
     -v $(pwd)/output:/output \
     aws-migration-tool:latest \
     cat /output/generate_ssh_keys.sh > generate_ssh_keys.sh
   
   chmod +x generate_ssh_keys.sh
   ./generate_ssh_keys.sh
   ```

5. **Execute Migration**
   - Follow the manual migration checklist
   - Use AWS Console for actual resource creation
   - Reference the report for configurations

## 🐛 Troubleshooting

### Credentials Not Found

```bash
# Verify AWS credentials
docker run --rm \
  -v ~/.aws:/root/.aws:ro \
  aws-migration-tool:latest \
  aws sts get-caller-identity --profile source_acc

docker run --rm \
  -v ~/.aws:/root/.aws:ro \
  aws-migration-tool:latest \
  aws sts get-caller-identity --profile target_acc
```

### Permission Denied

```bash
# Fix permissions on output directory
chmod -R 755 output/

# Fix permissions on scripts
chmod +x setup_credentials.sh
```

### Container Exits Immediately

```bash
# Check logs
docker-compose logs

# Run with interactive shell
docker run --rm -it \
  -v ~/.aws:/root/.aws:ro \
  -v $(pwd)/output:/output \
  aws-migration-tool:latest \
  /bin/bash
```

## 🔒 Security Best Practices

1. **Credentials:**
   - Never commit AWS credentials to git
   - Use IAM roles with minimum required permissions
   - Rotate credentials regularly

2. **Network:**
   - Run migrations from secure networks
   - Use VPN for sensitive operations
   - Enable CloudTrail for audit

3. **Data:**
   - Encrypt snapshots with KMS
   - Test backups before migration
   - Maintain rollback capability

## � Migration Guides

### EC2 Instance Migration (NEW!)

**Fully automated with security group dependency resolution!**

#### Quick Start - Automated Script

```bash
# Run the automated migration script
./automated_ec2_migration.sh
```

The script provides:
- ✅ Interactive instance selection
- ✅ Automatic security group dependency handling
- ✅ Dry-run validation before actual migration
- ✅ Complete progress tracking and timing
- ✅ 12-step guided workflow

#### What Gets Migrated

1. **Instance Configuration**
   - Instance type and settings
   - User data and metadata
   - Tags and monitoring config

2. **AMI and Snapshots**
   - Source AMI shared and copied
   - Encrypted AMI/snapshot handling
   - KMS grants for cross-account access

3. **Storage**
   - All attached EBS volumes
   - Volume snapshots created
   - Encryption preserved

4. **Security Groups (AUTO-RESOLVED)**
   - All security groups detected
   - Dependencies automatically resolved
   - Rules updated with target SG IDs
   - Circular references handled

5. **Networking**
   - Placed in target VPC/subnet
   - Elastic IP allocated (if needed)
   - Network interfaces configured

#### Manual Docker Command

```bash
# Dry run
docker run --rm \
  -v ~/.aws:/root/.aws \
  aws-migration-tool:latest \
  --mode ec2 \
  --ec2-instance i-0123456789abcdef0 \
  --target-vpc vpc-0261473d76d9c5d21 \
  --target-subnet subnet-0a1b2c3d4e5f6g7h8 \
  --dry-run

# Actual migration
docker run --rm \
  -v ~/.aws:/root/.aws \
  aws-migration-tool:latest \
  --mode ec2 \
  --ec2-instance i-0123456789abcdef0 \
  --target-vpc vpc-0261473d76d9c5d21 \
  --target-subnet subnet-0a1b2c3d4e5f6g7h8
```

#### Performance

- **Total Time:** 12-20 minutes per instance
- **Security Groups:** 1-2 minutes (handles dependencies automatically)
- **AMI Copy:** 5-8 minutes
- **Snapshots:** 3-5 minutes

#### Detailed Documentation

See [EC2_MIGRATION_GUIDE.md](EC2_MIGRATION_GUIDE.md) for:
- Complete feature documentation
- Security group dependency explanation
- Architecture diagrams
- Troubleshooting guide
- Validation steps
- Best practices

---

### RDS Database Migration

**Fully automated with AWS-managed KMS key handling!**

#### Quick Start - Automated Script

```bash
# Run the automated migration script
./automated_rds_migration.sh
```

The script provides:
- ✅ Interactive database selection
- ✅ Automatic KMS key creation and re-encryption
- ✅ Dry-run validation before actual migration
- ✅ Complete progress tracking
- ✅ 12-step guided workflow

#### What Gets Migrated

1. **Database Configuration**
   - Engine type and version
   - Instance class
   - Storage configuration
   - Parameter groups

2. **Encryption (AUTOMATIC)**
   - Detects AWS-managed keys (aws/rds)
   - Creates customer-managed key in source
   - Re-encrypts snapshot for sharing
   - Copies to target with encryption

3. **Networking**
   - DB subnet group created/reused
   - Security group created/reused
   - VPC placement

4. **Tags and Metadata**
   - All tags preserved
   - Migration tracking tags added

#### Performance

- **Total Time:** 18-20 minutes per database
- **KMS Setup:** Automatic (1-2 minutes)
- **Snapshot:** 5-8 minutes
- **Copy & Restore:** 10-12 minutes

#### Detailed Documentation

See [AUTOMATED_RDS_MIGRATION.md](AUTOMATED_RDS_MIGRATION.md) for:
- Complete workflow documentation
- KMS key handling details
- Troubleshooting guide
- Best practices

---

## �📄 IAM Permissions Required

### Source Account
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ec2:Describe*",
        "ec2:CreateSnapshot",
        "ec2:CreateImage",
        "ec2:ModifyImageAttribute",
        "ec2:ModifySnapshotAttribute",
        "rds:Describe*",
        "rds:CreateDBSnapshot",
        "rds:CreateDBClusterSnapshot",
        "rds:ModifyDBSnapshotAttribute",
        "rds:ModifyDBClusterSnapshotAttribute",
        "kms:DescribeKey",
        "kms:ListAliases",
        "kms:ListResourceTags"
      ],
      "Resource": "*"
    }
  ]
}
```

### Target Account
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ec2:*",
        "rds:*",
        "kms:CreateKey",
        "kms:CreateAlias",
        "kms:DescribeKey"
      ],
      "Resource": "*"
    }
  ]
}
```

## 📞 Support

For issues or questions:
1. Check the troubleshooting section
2. Review AWS CloudTrail logs
3. Verify IAM permissions
4. Check the migration report for errors

## 📜 License

This tool is provided as-is for AWS migration purposes.

## ⚠️ Disclaimer

- Always test in a non-production environment first
- Verify all resources after migration
- Maintain backups of critical data
- Follow AWS best practices for cross-account migrations
