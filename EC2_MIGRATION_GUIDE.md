# EC2 Instance Migration Guide

## Overview

This guide covers migrating EC2 instances from a source AWS account to a target AWS account with **automatic security group dependency resolution**. The migration tool handles complex security group configurations where security groups reference each other in their rules.

## Key Features

### 🔒 Security Group Dependency Handling

The migration tool automatically:
- ✅ Detects all security groups attached to the instance
- ✅ Creates a dependency graph of security group references
- ✅ Creates all security groups in the target VPC
- ✅ Maps source security group IDs to target security group IDs
- ✅ Updates ingress/egress rules to use target account SG IDs
- ✅ Preserves CIDR blocks and port configurations
- ✅ Handles circular dependencies between security groups

### 🖼️ AMI and Snapshot Handling

- ✅ Shares and copies AMIs across accounts
- ✅ Handles encrypted AMIs with KMS grants
- ✅ Creates volume snapshots with KMS access
- ✅ Re-encrypts AWS-managed key snapshots automatically

### 🚀 Instance Migration

- ✅ Preserves instance type and configuration
- ✅ Maintains tags and metadata
- ✅ Handles Elastic IP associations
- ✅ Supports user data migration
- ✅ Validates key pair availability

## Prerequisites

### 1. AWS Credentials

Configure AWS CLI profiles for both accounts:

```bash
aws configure --profile source_acc
aws configure --profile target_acc
```

### 2. IAM Permissions

Required permissions are automatically created, but ensure the IAM user has rights to:
- Create/attach IAM policies
- Access EC2 resources
- Manage KMS keys and grants

### 3. Target VPC

Ensure you have a VPC configured in the target account with:
- Appropriate subnets
- Route tables configured
- Internet Gateway (if needed)

### 4. Key Pairs

The source instance's key pair must exist in the target account with the **same name**.

## Migration Process

### Method 1: Automated Script (Recommended)

Use the automated script for a guided migration experience:

```bash
./automated_ec2_migration.sh
```

The script will:
1. ✅ Verify AWS credentials
2. ✅ Check IAM policies
3. ✅ Discover available EC2 instances
4. ✅ Let you select the instance to migrate
5. ✅ Discover target VPCs and subnets
6. ✅ Display migration plan
7. ✅ Execute dry run (recommended)
8. ✅ Execute actual migration
9. ✅ Report results with timing

### Method 2: Docker Command

For direct control, use Docker commands:

**Dry Run:**
```bash
docker run --rm \
  -v ~/.aws:/root/.aws \
  aws-migration-tool:latest \
  --mode ec2 \
  --ec2-instance i-0123456789abcdef0 \
  --target-vpc vpc-0261473d76d9c5d21 \
  --target-subnet subnet-0a1b2c3d4e5f6g7h8 \
  --dry-run
```

**Actual Migration:**
```bash
docker run --rm \
  -v ~/.aws:/root/.aws \
  aws-migration-tool:latest \
  --mode ec2 \
  --ec2-instance i-0123456789abcdef0 \
  --target-vpc vpc-0261473d76d9c5d21 \
  --target-subnet subnet-0a1b2c3d4e5f6g7h8
```

## Security Group Migration Details

### How It Works

When you have security groups that reference each other (e.g., web tier allows traffic from load balancer SG), the migration tool:

1. **Collection Phase**
   ```
   Instance SGs: [sg-web, sg-app, sg-db]
   sg-web ingress: Allow 443 from sg-lb
   sg-app ingress: Allow 8080 from sg-web
   sg-db ingress: Allow 5432 from sg-app
   ```

2. **Creation Phase**
   - Creates `sg-web-migrated` in target VPC
   - Creates `sg-app-migrated` in target VPC
   - Creates `sg-db-migrated` in target VPC
   - Creates `sg-lb-migrated` (dependency discovered)

3. **Mapping Phase**
   ```
   sg-web → sg-web-migrated (sg-0abc123)
   sg-app → sg-app-migrated (sg-0def456)
   sg-db → sg-db-migrated (sg-0ghi789)
   sg-lb → sg-lb-migrated (sg-0jkl012)
   ```

4. **Rules Update Phase**
   - Updates `sg-web-migrated` ingress: Allow 443 from `sg-lb-migrated`
   - Updates `sg-app-migrated` ingress: Allow 8080 from `sg-web-migrated`
   - Updates `sg-db-migrated` ingress: Allow 5432 from `sg-app-migrated`

### Example Scenario

**Source Account:**
```
┌─────────────────┐
│   Load Balancer │ (sg-lb)
└────────┬────────┘
         │ 443
         ▼
┌─────────────────┐
│   Web Tier      │ (sg-web)
└────────┬────────┘
         │ 8080
         ▼
┌─────────────────┐
│   App Tier      │ (sg-app)
└────────┬────────┘
         │ 5432
         ▼
┌─────────────────┐
│   Database      │ (sg-db)
└─────────────────┘
```

**After Migration (Target Account):**
```
┌─────────────────────────┐
│   Load Balancer         │ (sg-lb-migrated)
└───────────┬─────────────┘
            │ 443
            ▼
┌─────────────────────────┐
│   Web Tier              │ (sg-web-migrated)
└───────────┬─────────────┘
            │ 8080
            ▼
┌─────────────────────────┐
│   App Tier              │ (sg-app-migrated)
└───────────┬─────────────┘
            │ 5432
            ▼
┌─────────────────────────┐
│   Database              │ (sg-db-migrated)
└─────────────────────────┘
```

All security group references are automatically updated!

## Migration Steps Detail

### Step 1: Instance Analysis
- Retrieves instance configuration
- Identifies AMI, volumes, security groups
- Checks encryption status

### Step 2: AMI Handling
- Detects encrypted snapshots in AMI
- Creates KMS grants for cross-account access
- Shares AMI with target account
- Copies AMI to target account
- Waits for AMI availability

### Step 3: Volume Snapshots
- Creates snapshots of all attached volumes
- Grants KMS access for encrypted volumes
- Tags snapshots for tracking

### Step 4: Security Group Replication (NEW)
- **4a:** Collects all security group details
- **4b:** Checks for existing migrated security groups
- **4c:** Creates security groups without cross-SG rules
- **4d:** Builds security group ID mapping
- **4e:** Updates rules with mapped SG IDs
- **4f:** Applies updated rules to all security groups

### Step 5: Instance Launch
- Launches instance with migrated AMI
- Attaches migrated security groups
- Applies tags and metadata
- Uses specified subnet and VPC

### Step 6: Elastic IP (if applicable)
- Allocates new Elastic IP in target
- Associates with new instance

## Common Scenarios

### Scenario 1: Web Application with Database

**Configuration:**
- Web server (sg-web): Allow 80, 443 from 0.0.0.0/0
- App server (sg-app): Allow 8080 from sg-web
- Database (sg-db): Allow 5432 from sg-app

**Migration:**
```bash
./automated_ec2_migration.sh
# Select web server instance
# All three security groups are automatically migrated with correct references
```

### Scenario 2: Microservices Architecture

**Configuration:**
- API Gateway (sg-api): Allow 443 from 0.0.0.0/0
- Service A (sg-svc-a): Allow 8001 from sg-api
- Service B (sg-svc-b): Allow 8002 from sg-api, sg-svc-a
- Service C (sg-svc-c): Allow 8003 from sg-svc-b

**Migration:**
Each service can be migrated independently. The tool will:
- Detect all referenced security groups
- Create them if they don't exist
- Reuse them if already migrated
- Update references automatically

### Scenario 3: Instance with Default Security Group

**Configuration:**
- Instance uses VPC default security group

**Migration:**
- Tool detects default security group
- Maps to target VPC's default security group
- No custom security group creation needed

## Troubleshooting

### Security Group Issues

**Problem:** "Security group sg-xxx does not exist"
- **Cause:** Referenced security group not found during mapping
- **Solution:** Tool will warn but continue; verify external references are intentional

**Problem:** "Cannot authorize security group ingress: duplicate rule"
- **Cause:** Rules already exist (from previous migration)
- **Solution:** Tool automatically reuses existing security groups and skips duplicate rules

### AMI/Snapshot Issues

**Problem:** "Cannot access encrypted snapshot"
- **Cause:** Missing KMS permissions
- **Solution:** Tool automatically creates KMS grants; verify IAM policies

**Problem:** "AMI copy failed"
- **Cause:** AMI not shared or snapshot access denied
- **Solution:** Check source account permissions and KMS key policies

### Instance Launch Issues

**Problem:** "Key pair 'my-key' does not exist"
- **Cause:** Key pair not present in target account
- **Solution:** Create key pair with same name in target account

**Problem:** "Insufficient subnet capacity"
- **Cause:** Target subnet has no available IPs
- **Solution:** Choose a different subnet with available IP addresses

## Performance Expectations

### Timing Benchmarks

Based on actual migrations:

| Component | Average Time |
|-----------|-------------|
| Instance Analysis | 30 seconds |
| AMI Sharing & Copy | 5-8 minutes |
| Volume Snapshots | 3-5 minutes |
| Security Group Creation | 1-2 minutes |
| Instance Launch | 2-3 minutes |
| **Total Migration Time** | **12-20 minutes** |

*Times vary based on:*
- Instance size
- Number of volumes
- Snapshot size
- Number of security groups
- Network connectivity

## Validation Steps

After migration, verify:

### 1. Instance Status
```bash
aws ec2 describe-instances \
  --profile target_acc \
  --filters "Name=tag:MigratedFrom,Values=i-0123456789abcdef0" \
  --query 'Reservations[0].Instances[0].[InstanceId,State.Name,PrivateIpAddress,PublicIpAddress]' \
  --output table
```

### 2. Security Groups
```bash
# List security groups
aws ec2 describe-security-groups \
  --profile target_acc \
  --filters "Name=vpc-id,Values=vpc-0261473d76d9c5d21" \
  --query 'SecurityGroups[?contains(GroupName, `migrated`)].[GroupId,GroupName]' \
  --output table

# Check specific security group rules
aws ec2 describe-security-groups \
  --profile target_acc \
  --group-ids sg-0abc123 \
  --query 'SecurityGroups[0].IpPermissions' \
  --output json
```

### 3. Network Connectivity
```bash
# SSH to instance
ssh -i ~/.ssh/my-key.pem ec2-user@<public-ip>

# Test internal connectivity
curl http://<private-ip>:8080
```

### 4. Application Functionality
- Verify application starts correctly
- Test database connections
- Check external API access
- Validate log files

## Security Group Reference Guide

### Rule Types Supported

#### CIDR-Based Rules (Simple)
```json
{
  "IpProtocol": "tcp",
  "FromPort": 443,
  "ToPort": 443,
  "IpRanges": [{"CidrIp": "0.0.0.0/0"}]
}
```
✅ Migrated as-is (no SG reference)

#### Security Group References (Complex)
```json
{
  "IpProtocol": "tcp",
  "FromPort": 8080,
  "ToPort": 8080,
  "UserIdGroupPairs": [
    {
      "GroupId": "sg-0abc123",
      "UserId": "123456789012"
    }
  ]
}
```
✅ Migrated with updated GroupId and UserId

#### Mixed Rules
```json
{
  "IpProtocol": "tcp",
  "FromPort": 22,
  "ToPort": 22,
  "IpRanges": [{"CidrIp": "10.0.0.0/16"}],
  "UserIdGroupPairs": [{"GroupId": "sg-0def456"}]
}
```
✅ Both CIDR and SG references handled

### Edge Cases Handled

1. **Circular Dependencies**
   - SG-A references SG-B
   - SG-B references SG-A
   - ✅ Both created, rules applied after both exist

2. **Self-References**
   - SG-A references itself
   - ✅ Mapped to new SG-A-migrated ID

3. **External SG References**
   - Rule references SG from another account/VPC
   - ⚠️ Warning logged, rule kept as-is

4. **Default Security Group**
   - Instance uses default SG
   - ✅ Mapped to target VPC default SG

## Best Practices

### Before Migration

1. **Document Current Configuration**
   ```bash
   # Export instance details
   aws ec2 describe-instances --instance-ids i-xxx > instance-before.json
   
   # Export security group rules
   aws ec2 describe-security-groups --group-ids sg-xxx > sg-before.json
   ```

2. **Create Backup/Snapshot**
   ```bash
   aws ec2 create-image --instance-id i-xxx --name "pre-migration-backup"
   ```

3. **Stop Instance** (for data consistency)
   ```bash
   aws ec2 stop-instances --instance-ids i-xxx
   ```

4. **Test in Dry Run Mode**
   ```bash
   ./automated_ec2_migration.sh
   # Answer 'Y' to dry run
   ```

### During Migration

1. **Monitor Progress**
   - Watch terminal output for errors
   - Note security group mapping logs
   - Track timing for each phase

2. **Have Rollback Plan**
   - Keep source instance available
   - Document any manual changes needed
   - Prepare DNS/LB rollback procedures

### After Migration

1. **Validate Connectivity**
   - Test all application endpoints
   - Verify security group rules work
   - Check database connections

2. **Update Configuration**
   - Update DNS records
   - Modify load balancer targets
   - Update monitoring/alerting

3. **Clean Up (After Verification)**
   ```bash
   # After successful validation (e.g., 7-30 days):
   # Delete source snapshots
   # Terminate source instance
   # Remove source security groups (if unused)
   ```

## Advanced Usage

### Migrating Multiple Instances

For a cluster of instances with shared security groups:

```bash
# Migrate first instance (creates all SGs)
./automated_ec2_migration.sh
# Select instance 1

# Migrate subsequent instances (reuses SGs)
./automated_ec2_migration.sh
# Select instance 2
# Same SGs will be reused automatically
```

### Custom Security Groups

To use different security groups in target:

```bash
docker run --rm \
  -v ~/.aws:/root/.aws \
  aws-migration-tool:latest \
  --mode ec2 \
  --ec2-instance i-xxx \
  --target-vpc vpc-xxx \
  --target-subnet subnet-xxx \
  --target-security-groups sg-target-1,sg-target-2
```

### Parallel Migrations

Can migrate multiple instances simultaneously (from different terminals):

```bash
# Terminal 1
./automated_ec2_migration.sh  # Instance 1

# Terminal 2
./automated_ec2_migration.sh  # Instance 2
```

Security groups are tagged and checked for existence to prevent conflicts.

## Support and Troubleshooting

### Getting Help

1. Check logs in terminal output
2. Review migration report: `output/migration_report.json`
3. Verify IAM policies are attached
4. Check AWS service quotas

### Common Error Messages

| Error | Meaning | Solution |
|-------|---------|----------|
| "AccessDenied: User is not authorized" | Missing IAM permission | Update IAM policy |
| "VPC vpc-xxx does not exist" | Invalid VPC ID | Verify target VPC exists |
| "InvalidGroup.NotFound" | Security group missing | Let tool create automatically |
| "Encrypted snapshot but no grant found" | KMS access issue | Tool creates grants automatically |
| "InvalidKeyPair.NotFound" | Key pair missing in target | Create key pair in target |

### Debug Mode

For detailed debugging:

```bash
# Add debug logging
export AWS_DEBUG=1

# Run migration
./automated_ec2_migration.sh
```

## Appendix

### Architecture Diagram

```
Source Account (123456789012)          Target Account (987654321098)
┌─────────────────────────────┐       ┌─────────────────────────────┐
│                             │       │                             │
│  ┌──────────────┐          │       │  ┌──────────────┐          │
│  │  Instance    │          │       │  │  Instance    │          │
│  │  i-source    │          │       │  │  i-migrated  │          │
│  └──────┬───────┘          │       │  └──────┬───────┘          │
│         │                   │       │         │                   │
│  ┌──────▼───────┐          │       │  ┌──────▼───────┐          │
│  │  sg-web      │◄─────────┼───────┼─►│sg-web-migr'd │          │
│  │  sg-app      │  Mapping │       │  │sg-app-migr'd │          │
│  │  sg-db       │          │       │  │sg-db-migr'd  │          │
│  └──────────────┘          │       │  └──────────────┘          │
│                             │       │                             │
│  ┌──────────────┐          │       │  ┌──────────────┐          │
│  │  AMI + Snaps │──Share───┼──────►│  │  AMI Copy    │          │
│  └──────────────┘          │       │  └──────────────┘          │
│                             │       │                             │
│  ┌──────────────┐          │       │  ┌──────────────┐          │
│  │  KMS Key     │──Grant───┼──────►│  │  Access      │          │
│  └──────────────┘          │       │  └──────────────┘          │
│                             │       │                             │
└─────────────────────────────┘       └─────────────────────────────┘
```

### Security Group Dependency Graph Example

```
sg-lb (Load Balancer)
  ↓ (referenced by)
sg-web (Web Tier)
  ↓ (referenced by)
sg-app (Application Tier)
  ↓ (referenced by)
sg-db (Database Tier)
  ↓ (referenced by)
sg-backup (Backup Server)
  ↑↓ (circular reference)
sg-monitoring (Monitoring Server)
```

Migration order: sg-lb-migrated → sg-web-migrated → sg-app-migrated → sg-db-migrated → sg-backup-migrated ↔ sg-monitoring-migrated

## Summary

The EC2 migration tool with **automatic security group dependency resolution** provides a robust, production-ready solution for cross-account instance migration. Key advantages:

✅ **Automated:** 12-step guided process
✅ **Safe:** Dry-run mode before actual migration  
✅ **Smart:** Automatic security group dependency handling  
✅ **Secure:** KMS encryption preserved  
✅ **Fast:** 12-20 minutes per instance  
✅ **Reliable:** Handles complex multi-tier architectures  

Ready to migrate your EC2 instances!
