# AWS Cross-Account Migration Tool

Docker-based solution for migrating AWS resources (EC2, RDS, VPC, etc.) between AWS accounts.

## 📋 Features

- **EC2 Migration**: Instances, AMIs, EBS volumes, snapshots, user data, SSH keys
- **RDS Migration**: Database instances, Aurora clusters, with KMS encryption support
- **Network Migration**: VPCs, subnets, security groups, route tables, NACLs
- **KMS Handling**: Automatic KMS key recreation and snapshot re-encryption
- **Elastic IPs**: Automatic allocation in target account
- **Comprehensive Reporting**: Detailed dry-run analysis before migration

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

## 📄 IAM Permissions Required

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
