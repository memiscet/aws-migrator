# VPC Migration - How It Works

## Overview

VPC migration is the **foundation** of AWS cross-account migrations. You should typically migrate the VPC infrastructure **before** migrating EC2 and RDS instances.

## Migration Approach

### Why VPC Components Can Be Migrated

Unlike EC2 instances (which contain state and data), VPC components are **configuration-based**:

| Component | Migration Method | Reason |
|-----------|------------------|---------|
| **VPC** | Recreate with same CIDR | VPC is just a logical container |
| **Subnets** | Recreate with same CIDR blocks | Subnet is a CIDR range within VPC |
| **Internet Gateway** | Create new, attach to VPC | Simple attachment, no data |
| **NAT Gateways** | Create new with new EIPs | Stateless routing device |
| **Security Groups** | Recreate with same rules | Just firewall rules, no state |
| **Route Tables** | Recreate with same routes | Routing configuration only |
| **Network ACLs** | Recreate with same rules | Stateless firewall rules |

### What Can't Be Migrated Automatically

| Component | Why Manual Setup Needed |
|-----------|------------------------|
| **VPC Peering** | Requires coordination between 2 VPCs/accounts |
| **VPN Connections** | Tied to customer gateway hardware |
| **Transit Gateway** | Multi-VPC/account orchestration |
| **VPC Endpoints** | Service-specific configurations |
| **Direct Connect** | Physical infrastructure dependency |

## Migration Order

### Recommended Sequence

```
1. VPC Migration (10-15 minutes)
   ├── VPC + DNS settings
   ├── Subnets (with AZ mapping)
   ├── Internet Gateway
   ├── Security Groups (without instances)
   ├── NAT Gateways (new Elastic IPs)
   └── Route Tables + associations

2. Manual Setup (variable time)
   ├── VPC Endpoints (S3, DynamoDB, etc.)
   ├── VPC Peering (if needed)
   └── VPN Connections (if needed)

3. EC2 Migration (15-30 min per instance)
   ├── Use VPC mapping from step 1
   ├── AMI copy + snapshots
   └── Launch in target subnets/SGs

4. RDS Migration (30-60+ min per instance)
   ├── Create DB subnet group from VPC mapping
   ├── Snapshot + share + re-encrypt
   └── Restore in target account
```

## Key Concepts

### 1. Resource Mapping

When you migrate a VPC, the tool creates a mapping file:

```json
{
  "source_vpc_id": "vpc-abc123",
  "target_vpc_id": "vpc-xyz789",
  "subnet_mapping": {
    "subnet-old1": "subnet-new1",
    "subnet-old2": "subnet-new2"
  },
  "sg_mapping": {
    "sg-old1": "sg-new1"
  }
}
```

**Use this mapping** when migrating EC2/RDS instances to know which target subnets and security groups to use.

### 2. Security Group Dependencies

Security groups often reference other security groups:

```
WebServer-SG:
  Ingress: Allow 443 from ALB-SG
  
ALB-SG:
  Ingress: Allow 443 from 0.0.0.0/0
```

The tool automatically:
1. Creates all security groups first
2. Maps the references (ALB-SG in source → new ALB-SG in target)
3. Adds rules with updated references

### 3. NAT Gateway Elastic IPs

**Important:** NAT Gateways get **new** public IP addresses because:
- Elastic IPs belong to the AWS account
- Cannot transfer EIPs between accounts
- Must allocate new EIPs in target account

**Action Required:**
- Note new NAT Gateway IPs from migration output
- Update firewall rules that whitelist old NAT IPs
- Update any third-party services that whitelist your IPs

### 4. Availability Zone Mapping

For **same-region** migrations:
- AZs map directly (us-east-1a → us-east-1a)

For **cross-region** migrations:
- Tool maps by AZ suffix (us-east-1a → us-west-2a)
- Verify target region has same AZ count
- May need manual adjustment if AZ architectures differ

## Example: Complete Migration

### Step 1: Analyze and Migrate VPC

```bash
# Dry-run to see plan
docker run --rm \
  -v ~/.aws:/root/.aws:ro \
  -v $(pwd)/output:/output \
  aws-migration-tool:latest \
  python aws_migration.py --migrate-vpc vpc-abc123 --dry-run

# Execute VPC migration
docker run --rm \
  -v ~/.aws:/root/.aws:ro \
  -v $(pwd)/output:/output \
  aws-migration-tool:latest \
  python aws_migration.py --migrate-vpc vpc-abc123
```

**Output:**
```
✅ VPC MIGRATION COMPLETE
Source VPC: vpc-abc123
Target VPC: vpc-xyz789
Subnets migrated: 4
Security groups migrated: 5
NAT Gateways created: 2

💾 Resource mapping saved to: /output/vpc_migration_mapping.json
```

### Step 2: Parse Mapping

```bash
# Get target VPC ID
TARGET_VPC=$(cat output/vpc_migration_mapping.json | jq -r '.target_vpc_id')

# Get subnet mapping for a specific subnet
TARGET_SUBNET=$(cat output/vpc_migration_mapping.json | jq -r '.subnet_mapping["subnet-abc123"]')

# Get security group mapping
TARGET_SG=$(cat output/vpc_migration_mapping.json | jq -r '.sg_mapping["sg-abc123"]')
```

### Step 3: Migrate EC2 Instance

```bash
# Use mapped resources
docker run --rm \
  -v ~/.aws:/root/.aws:ro \
  -v $(pwd)/output:/output \
  aws-migration-tool:latest \
  python aws_migration.py \
    --migrate-ec2 i-instance123 \
    --target-vpc $TARGET_VPC \
    --target-subnet $TARGET_SUBNET \
    --target-security-groups $TARGET_SG
```

### Step 4: Create DB Subnet Group

```bash
# Get all target subnet IDs
SUBNETS=$(cat output/vpc_migration_mapping.json | \
  jq -r '.subnet_mapping | to_entries[] | .value' | paste -sd, -)

# Create DB subnet group
aws rds create-db-subnet-group \
  --db-subnet-group-name migrated-db-subnet-group \
  --db-subnet-group-description "Migrated from source account" \
  --subnet-ids $(echo $SUBNETS | tr ',' ' ') \
  --profile target_acc
```

### Step 5: Migrate RDS Instance

```bash
docker run --rm \
  -v ~/.aws:/root/.aws:ro \
  -v $(pwd)/output:/output \
  aws-migration-tool:latest \
  python aws_migration.py \
    --migrate-rds mydb \
    --target-subnet-group migrated-db-subnet-group
```

## Understanding CIDR Block Options

### Option 1: Keep Same CIDR (Default)

```bash
# VPC in source: 10.0.0.0/16
# VPC in target: 10.0.0.0/16 (same)

docker run --rm \
  -v ~/.aws:/root/.aws:ro \
  -v $(pwd)/output:/output \
  aws-migration-tool:latest \
  python aws_migration.py --migrate-vpc vpc-abc123
```

**Benefits:**
- No IP address changes needed
- Subnets maintain exact same CIDR blocks
- Easier for documentation/troubleshooting

**Considerations:**
- Target account must not have conflicting CIDR blocks
- Check existing VPCs in target account first

### Option 2: Change CIDR Block

```bash
# VPC in source: 10.0.0.0/16
# VPC in target: 172.16.0.0/16 (different)

docker run --rm \
  -v ~/.aws:/root/.aws:ro \
  -v $(pwd)/output:/output \
  aws-migration-tool:latest \
  python aws_migration.py \
    --migrate-vpc vpc-abc123 \
    --target-cidr 172.16.0.0/16
```

**Benefits:**
- Avoids CIDR conflicts in target account
- Allows VPC peering between source and target
- Can isolate environments by IP range

**Considerations:**
- Subnet CIDR blocks are still taken from source (not automatically recalculated)
- May need manual subnet CIDR adjustment
- Application configurations with hardcoded IPs need updates

## Security Considerations

### 1. IAM Permissions

VPC migration requires extensive EC2 permissions. Review required permissions in `VPC_MIGRATION_GUIDE.md`.

### 2. Network Access During Migration

- Source VPC remains operational
- Target VPC is created fresh
- No downtime for source resources
- Migration happens in parallel to production

### 3. Security Group Rule Migration

All security group rules are preserved:
- Ingress rules (inbound)
- Egress rules (outbound)
- IP ranges (CIDR blocks)
- Security group references (automatically mapped)
- Port ranges and protocols

### 4. Network ACL Migration

Custom Network ACLs are migrated with:
- All inbound rules
- All outbound rules  
- Rule numbers and priorities
- Subnet associations (automatically mapped)

## Cost Impact

### One-Time Costs

| Resource | Cost | Duration |
|----------|------|----------|
| NAT Gateway Elastic IPs | ~$0.005/hour | During allocation |
| Data transfer (cross-region) | ~$0.02/GB | If migrating regions |

### Ongoing Costs (New Resources)

| Resource | Cost | Notes |
|----------|------|-------|
| NAT Gateway | ~$0.045/hour + $0.045/GB | Per NAT Gateway |
| VPC | Free | No charge for VPC itself |
| Subnets | Free | No charge |
| Security Groups | Free | No charge |
| Route Tables | Free | No charge |

**Cost Optimization:**
- Delete source VPC after successful migration (saves duplicate costs)
- Use VPC Endpoints for S3/DynamoDB (reduce NAT Gateway data transfer)
- Consider single NAT Gateway if high availability not critical in dev/test

## Troubleshooting

### Issue: CIDR Block Already Exists

**Error:** `VPC CIDR block 10.0.0.0/16 conflicts with existing VPC`

**Solution:**
```bash
# Use different CIDR block
docker run --rm \
  -v ~/.aws:/root/.aws:ro \
  -v $(pwd)/output:/output \
  aws-migration-tool:latest \
  python aws_migration.py \
    --migrate-vpc vpc-abc123 \
    --target-cidr 172.16.0.0/16
```

### Issue: NAT Gateway Creation Timeout

**Error:** `NAT Gateway still pending after 5 minutes`

**Solution:**
- NAT Gateway creation can take 2-5 minutes
- Tool includes wait time, but may timeout on slow AWS regions
- Check AWS Console to verify NAT Gateway status
- Re-run migration (tool is idempotent where possible)

### Issue: Security Group Rule Error

**Error:** `Cannot authorize security group rule: duplicate`

**Solution:**
- Tool attempts to skip duplicate rules
- Verify target VPC doesn't have conflicting security groups from previous migration
- Delete partial migration and retry

### Issue: Subnet CIDR Doesn't Fit in New VPC CIDR

**Error:** `Subnet CIDR 10.0.1.0/24 is not within VPC CIDR 172.16.0.0/16`

**Solution:**
- When changing VPC CIDR, subnets must fit within it
- Tool uses source subnet CIDRs by default
- Requires manual subnet re-planning for CIDR changes
- Consider using same CIDR if possible

## Best Practices

### 1. Always Dry-Run First
```bash
--dry-run  # Shows complete plan without making changes
```

### 2. Document NAT Gateway IPs
```bash
# Before migration, note source NAT IPs
aws ec2 describe-nat-gateways --filter Name=vpc-id,Values=vpc-abc123

# After migration, note new NAT IPs from output
# Update firewall rules and whitelists
```

### 3. Test Network Connectivity
```bash
# Launch test instance in new VPC
# Verify internet access through NAT
# Test security group rules
# Verify route table routing
```

### 4. Plan for VPC Endpoints
```bash
# List source VPC endpoints
aws ec2 describe-vpc-endpoints --filters Name=vpc-id,Values=vpc-abc123

# Recreate in target VPC after migration
aws ec2 create-vpc-endpoint \
  --vpc-id $TARGET_VPC \
  --service-name com.amazonaws.us-east-1.s3 \
  --route-table-ids rtb-xxx
```

### 5. Keep Source VPC Running
- Don't delete source VPC immediately
- Keep as backup for 1-2 weeks
- Allows rollback if issues discovered
- Can compare configurations if needed

## Summary

VPC migration is **configuration cloning**, not data migration:

✅ **Fast:** 10-15 minutes for complete VPC  
✅ **Safe:** Source VPC unchanged, non-destructive  
✅ **Complete:** All core networking components  
✅ **Mapped:** Provides resource mapping for EC2/RDS migration  
✅ **Automated:** Single command with dry-run validation  

**Workflow:**
1. Migrate VPC → Get resource mapping
2. Setup manual components (endpoints, peering, VPN)
3. Migrate EC2/RDS using resource mapping
4. Test and validate
5. Delete source VPC after validation period

For complete details, see **`VPC_MIGRATION_GUIDE.md`**
