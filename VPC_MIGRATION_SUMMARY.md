# 🌐 VPC Migration - Quick Summary

## What It Does

Migrates an entire VPC from source account to target account, including:
- ✅ VPC with CIDR block and DNS settings
- ✅ All subnets with availability zone mapping
- ✅ Internet Gateway
- ✅ NAT Gateways with new Elastic IPs
- ✅ All Security Groups with rules
- ✅ All Route Tables with routes
- ✅ Network ACLs

## Quick Start

```bash
# 1. Dry-run (always first!)
docker run --rm -v ~/.aws:/root/.aws:ro -v $(pwd)/output:/output \
  aws-migration-tool:latest python aws_migration.py \
  --migrate-vpc vpc-abc123 --dry-run

# 2. Execute migration
docker run --rm -v ~/.aws:/root/.aws:ro -v $(pwd)/output:/output \
  aws-migration-tool:latest python aws_migration.py \
  --migrate-vpc vpc-abc123

# 3. Check mapping file
cat output/vpc_migration_mapping.json
```

## Custom CIDR Block

```bash
# Migrate with different CIDR
docker run --rm -v ~/.aws:/root/.aws:ro -v $(pwd)/output:/output \
  aws-migration-tool:latest python aws_migration.py \
  --migrate-vpc vpc-abc123 --target-cidr 172.16.0.0/16
```

## What Happens

1. **Creates VPC** (10-30 seconds)
2. **Creates Subnets** (5-10 seconds each)
3. **Creates Internet Gateway** (10-20 seconds)
4. **Creates NAT Gateways** (2-5 minutes each) ⏱️
5. **Creates Security Groups** (10-20 seconds each)
6. **Adds Security Group Rules** (with SG reference mapping)
7. **Creates Route Tables** (20-30 seconds each)
8. **Associates Routes** (IGW and NAT Gateway routes mapped)
9. **Creates Network ACLs** (10-20 seconds each)

**Total Time:** 10-15 minutes

## After Migration

### Mapping File Created
`output/vpc_migration_mapping.json` contains:
- Source → Target VPC ID
- Source → Target Subnet IDs
- Source → Target Security Group IDs
- Source → Target NAT Gateway IDs
- Source → Target Route Table IDs

### Use Mapping to Migrate Resources

```bash
# Extract IDs from mapping
NEW_VPC=$(cat output/vpc_migration_mapping.json | jq -r '.target_vpc_id')
NEW_SUBNET=$(cat output/vpc_migration_mapping.json | jq -r '.subnet_mapping | to_entries[0].value')
NEW_SGS=$(cat output/vpc_migration_mapping.json | jq -r '.sg_mapping | to_entries | map(.value) | join(",")')

# Migrate EC2 instance to new VPC
docker run --rm -v ~/.aws:/root/.aws:ro -v $(pwd)/output:/output \
  aws-migration-tool:latest python aws_migration.py \
  --migrate-ec2 i-abc123 \
  --target-vpc $NEW_VPC \
  --target-subnet $NEW_SUBNET \
  --target-security-groups $NEW_SGS \
  --dry-run
```

## Manual Steps Required

After VPC migration, manually recreate:
1. **VPC Endpoints** (S3, DynamoDB, etc.)
2. **VPN Connections** (Customer Gateways, VPN tunnels)
3. **VPC Peering Connections**
4. **Transit Gateway Attachments**
5. **Direct Connect Virtual Interfaces**

### Example: Create S3 Endpoint

```bash
NEW_VPC=$(cat output/vpc_migration_mapping.json | jq -r '.target_vpc_id')
NEW_RTB=$(cat output/vpc_migration_mapping.json | jq -r '.route_table_mapping | to_entries[0].value')

aws ec2 create-vpc-endpoint \
  --vpc-id $NEW_VPC \
  --service-name com.amazonaws.us-east-1.s3 \
  --route-table-ids $NEW_RTB \
  --profile target_acc
```

## Important Notes

⚠️ **CIDR Overlaps:** If target account has VPCs with overlapping CIDR, use `--target-cidr` to specify different CIDR

⚠️ **NAT Gateway IPs:** New Elastic IPs will be allocated (different from source)

⚠️ **Cross-Region:** AZs are mapped by suffix (us-east-1a → us-west-2a)

⚠️ **Security Groups:** Inter-SG references are automatically mapped to new SG IDs

⚠️ **Source VPC:** Remains unchanged - you can keep or delete after verification

## Verification Commands

```bash
NEW_VPC=$(cat output/vpc_migration_mapping.json | jq -r '.target_vpc_id')

# Check VPC
aws ec2 describe-vpcs --vpc-ids $NEW_VPC --profile target_acc

# Check subnets
aws ec2 describe-subnets --filters "Name=vpc-id,Values=$NEW_VPC" --profile target_acc

# Check security groups
aws ec2 describe-security-groups --filters "Name=vpc-id,Values=$NEW_VPC" --profile target_acc

# Check route tables
aws ec2 describe-route-tables --filters "Name=vpc-id,Values=$NEW_VPC" --profile target_acc

# Check NAT gateways
aws ec2 describe-nat-gateways --filter "Name=vpc-id,Values=$NEW_VPC" --profile target_acc
```

## Rollback

If something goes wrong:
1. Source VPC is unchanged
2. Delete target VPC: `aws ec2 delete-vpc --vpc-id $NEW_VPC --profile target_acc`
3. Fix issues and retry
4. No impact to production

## Cost Considerations

- **NAT Gateway:** ~$0.045/hour + $0.045/GB data processing
- **Elastic IPs:** Free when associated
- **VPN Connection:** $0.05/hour per connection
- **VPC Endpoints:** ~$0.01/hour for interface endpoints

## Complete Workflow

```bash
# Step 1: Analysis
docker run --rm -v ~/.aws:/root/.aws:ro -v $(pwd)/output:/output \
  aws-migration-tool:latest python aws_migration.py --report

# Step 2: Dry-run VPC migration
docker run --rm -v ~/.aws:/root/.aws:ro -v $(pwd)/output:/output \
  aws-migration-tool:latest python aws_migration.py \
  --migrate-vpc vpc-abc123 --dry-run

# Step 3: Execute VPC migration
docker run --rm -v ~/.aws:/root/.aws:ro -v $(pwd)/output:/output \
  aws-migration-tool:latest python aws_migration.py \
  --migrate-vpc vpc-abc123

# Step 4: Create VPC endpoints
# (See VPC_MIGRATION_GUIDE.md)

# Step 5: Migrate EC2 instances
# (Use mapping file IDs)

# Step 6: Migrate RDS instances
# (Create DB subnet group first, then migrate)
```

## Documentation

- **Detailed Guide:** [VPC_MIGRATION_GUIDE.md](VPC_MIGRATION_GUIDE.md)
- **Full Documentation:** [README.md](README.md)
- **Quick Commands:** [QUICK_REFERENCE.md](QUICK_REFERENCE.md)
- **Migration Workflow:** [MIGRATION_WORKFLOW.md](MIGRATION_WORKFLOW.md)

---

**Always test with non-production VPCs first!**
