# AWS Migration Tool - Complete Docker Setup

## 📁 Project Structure

```
/Users/memiscet/repos/contract/
├── aws_migration.py          # Main migration script
├── Dockerfile               # Docker image definition
├── docker-compose.yml       # Docker Compose configuration
├── requirements.txt         # Python dependencies
├── setup_credentials.sh     # AWS credentials setup script
├── run_migration.sh        # Automated run script
├── README.md               # Full documentation
├── QUICK_REFERENCE.md      # Quick command reference
├── .gitignore             # Git ignore rules
├── .dockerignore          # Docker ignore rules
└── output/                # Generated reports (created on first run)
    ├── migration_report.json
    ├── user_data_backup.json
    └── generate_ssh_keys.sh
```

## 🚀 Complete Setup Instructions

### Step 1: Setup AWS Credentials

Run the credential setup script:
```bash
cd /Users/memiscet/repos/contract
./setup_credentials.sh
```

This creates two profiles in `~/.aws/credentials`:
- `source_acc` - Source AWS account
- `target_acc` - Target AWS account

### Step 2: Build Docker Image

```bash
docker build -t aws-migration-tool:latest .
```

### Step 3: Run Migration Analysis

**Option A: Using the automated script (Recommended)**
```bash
./run_migration.sh
```

**Option B: Using Docker Compose**
```bash
docker-compose up
```

**Option C: Using Docker directly**
```bash
docker run --rm \
  -v ~/.aws:/root/.aws:ro \
  -v $(pwd)/output:/output \
  aws-migration-tool:latest \
  python aws_migration.py --report
```

## 📊 Output Files

After running, check the `output/` directory:

1. **migration_report.json** - Complete inventory including:
   - EC2 instances, AMIs, volumes, security groups
   - RDS instances, clusters, with KMS encryption details
   - VPCs, subnets, route tables, NACLs
   - Elastic IPs, key pairs

2. **user_data_backup.json** - Backup of all EC2 user data

3. **generate_ssh_keys.sh** - Script to create new SSH keys in target account

## 🔑 Key Features

### 1. KMS Key Handling
- **Detects** all KMS keys used for encryption
- **Creates** equivalent keys in target account
- **Re-encrypts** snapshots with target account keys
- **Handles** both AWS-managed and customer-managed keys

### 2. Complete Resource Analysis
- EC2: Instances, AMIs, snapshots, volumes, user data
- RDS: Instances, clusters, encrypted databases
- Network: VPCs, subnets, security groups, NACLs
- Security: KMS keys, SSH keys, IAM roles

### 3. Docker Benefits
- **Isolated environment** - No local Python/AWS CLI conflicts
- **Reproducible** - Same results on any machine
- **Portable** - Works on Mac, Linux, Windows (with WSL)
- **Easy cleanup** - Remove container when done

## 📝 Example Commands

### Analyze All Resources
```bash
docker run --rm \
  -v ~/.aws:/root/.aws:ro \
  -v $(pwd)/output:/output \
  aws-migration-tool:latest \
  python aws_migration.py --report
```

### Analyze Specific EC2 Instances
```bash
docker run --rm \
  -v ~/.aws:/root/.aws:ro \
  -v $(pwd)/output:/output \
  aws-migration-tool:latest \
  python aws_migration.py --report \
  --ec2-instances i-abc123,i-def456
```

### Analyze Specific RDS Instances
```bash
docker run --rm \
  -v ~/.aws:/root/.aws:ro \
  -v $(pwd)/output:/output \
  aws-migration-tool:latest \
  python aws_migration.py --report \
  --rds-instances mydb-prod,mydb-dev
```

### Custom Region
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

## 🔍 View Report Data

### Using jq (JSON processor)
```bash
# Install jq first: brew install jq (on Mac)

# View full report
cat output/migration_report.json | jq .

# Count resources
cat output/migration_report.json | jq '{
  ec2: (.ec2_instances | length),
  rds: (.rds_instances | length),
  vpcs: (.vpcs | length),
  kms: (.kms_keys | length)
}'

# List EC2 instances with details
cat output/migration_report.json | jq '.ec2_instances[] | {
  id: .instance_id,
  type: .instance_type,
  state: .state,
  ip: .private_ip
}'

# List RDS instances with encryption status
cat output/migration_report.json | jq '.rds_instances[] | {
  id: .db_instance_identifier,
  engine: .engine,
  encrypted: .storage_encrypted,
  kms_key: .kms_key_id
}'

# List all KMS keys
cat output/migration_report.json | jq '.kms_keys[] | {
  id: .key_id,
  aliases: .aliases,
  aws_managed: .is_aws_managed
}'
```

## 🔐 Security Best Practices

1. **AWS Credentials:**
   - Never commit credentials to git (.gitignore includes .aws/)
   - Use read-only mount for credentials (`-v ~/.aws:/root/.aws:ro`)
   - Rotate credentials regularly

2. **IAM Permissions:**
   - Use minimum required permissions
   - See README.md for detailed IAM policy

3. **Output Files:**
   - May contain sensitive information
   - .gitignore excludes output directory
   - Review before sharing

## 🧪 Testing Your Setup

### 1. Test Docker
```bash
docker --version
docker ps
```

### 2. Test AWS Credentials
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

### 3. Test Migration Script
```bash
docker run --rm \
  -v ~/.aws:/root/.aws:ro \
  -v $(pwd)/output:/output \
  aws-migration-tool:latest \
  python aws_migration.py --help
```

## 🐛 Troubleshooting

### Problem: "Cannot connect to Docker daemon"
```bash
# Start Docker Desktop (Mac) or Docker service (Linux)
# Mac: Open Docker Desktop application
# Linux: sudo systemctl start docker
```

### Problem: "AWS credentials not found"
```bash
# Verify credentials file exists
cat ~/.aws/credentials

# Re-run setup
./setup_credentials.sh

# Test credentials
aws sts get-caller-identity --profile source_acc
aws sts get-caller-identity --profile target_acc
```

### Problem: "Permission denied" on scripts
```bash
chmod +x setup_credentials.sh run_migration.sh
```

### Problem: "No such file or directory: /output"
```bash
mkdir -p output
```

### Problem: Docker image build fails
```bash
# Clean rebuild
docker build --no-cache -t aws-migration-tool:latest .
```

## 🗑️ Cleanup

### Remove Generated Files
```bash
rm -rf output/*
```

### Remove Docker Resources
```bash
# Stop and remove container
docker-compose down

# Remove image
docker rmi aws-migration-tool:latest

# Remove all unused Docker resources
docker system prune -a
```

## 📋 Migration Workflow

1. **Prepare:**
   ```bash
   ./setup_credentials.sh  # One-time setup
   ```

2. **Analyze:**
   ```bash
   ./run_migration.sh      # Generate report
   ```

3. **Review:**
   ```bash
   cat output/migration_report.json | jq .
   ```

4. **Plan:**
   - Schedule maintenance window
   - Notify Insurance Pro team
   - Notify DWH team
   - Prepare rollback plan

5. **Generate SSH Keys:**
   ```bash
   chmod +x output/generate_ssh_keys.sh
   ./output/generate_ssh_keys.sh
   ```

6. **Execute:**
   - Follow the manual migration checklist
   - Use AWS Console for resource creation
   - Reference migration_report.json for all configurations

7. **Verify:**
   - Test all migrated resources
   - Verify data integrity
   - Update connection strings

8. **Cleanup:**
   - Decommission source resources (after verification)
   - Update documentation
   - Archive migration reports

## 🎯 Customer Requirements Addressed

✅ **EC2 instance manual migration** - Report provides all details for manual migration
✅ **Share between 2 accounts** - Automated AMI and snapshot sharing
✅ **AMI identification** - All AMIs detected and documented
✅ **New SSH keys** - Script generated to create new keys
✅ **RDS instances** - Complete RDS analysis including Aurora clusters
✅ **KMS encryption** - Automatic KMS key handling and re-encryption
✅ **VPC and subnets** - Complete network topology captured
✅ **Security Groups and IP addresses** - All rules documented
✅ **Storage and Volumes** - EBS volumes analyzed with snapshot strategy
✅ **Zero data loss** - Maintenance window planning supported

## 📞 Support

For issues:
1. Check the troubleshooting section above
2. Review Docker logs: `docker-compose logs`
3. Check AWS permissions
4. Verify network connectivity

## 🔄 Updates

To update the tool:
```bash
# Pull latest changes (if using git)
git pull

# Rebuild Docker image
docker build --no-cache -t aws-migration-tool:latest .

# Run updated version
./run_migration.sh
```
