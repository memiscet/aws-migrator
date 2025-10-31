# 🌐 VPC Migration Guide

## Overview

The VPC migration feature allows you to migrate an entire VPC and all its components from a source AWS account to a target AWS account. This includes subnets, security groups, route tables, NAT gateways, internet gateways, and network ACLs.

## What Gets Migrated

### ✅ Automatically Migrated

1. **VPC Configuration**
   - CIDR block
   - DNS support settings
   - DNS hostname settings
   - Tags

2. **Subnets**
   - CIDR blocks
   - Availability zones
   - Public IP auto-assign settings
   - Tags

3. **Internet Gateway**
   - Created and attached to new VPC

4. **NAT Gateways**
   - Created in mapped subnets
   - New Elastic IPs allocated
   - Tags

5. **Security Groups**
   - All ingress rules
   - All egress rules
   - Inter-security-group references (automatically mapped)
   - Tags

6. **Route Tables**
   - All routes (IGW, NAT Gateway routes mapped)
   - Subnet associations
   - Main route table configuration
   - Tags

7. **Network ACLs**
   - All inbound rules
   - All outbound rules
   - Subnet associations
   - Tags

### ⚠️ Requires Manual Setup

1. **VPC Peering Connections**
   - Must be recreated manually
   - Requires coordination with peer VPC owners

2. **VPN Connections**
   - Customer gateways must be recreated
   - VPN tunnels must be reconfigured
   - BGP/static routes must be updated

3. **Transit Gateway Attachments**
   - Must be recreated in target account
   - Requires Transit Gateway access

4. **VPC Endpoints**
   - Interface endpoints for AWS services
   - Gateway endpoints (S3, DynamoDB)
   - Must be recreated after VPC migration

5. **Direct Connect Virtual Interfaces**
   - Requires coordination with AWS and network team

6. **Routes to Network Interfaces (ENIs)**
   - Custom routes pointing to specific ENIs
   - Must be updated after EC2 migration

## Migration Workflow

### Phase 1: Pre-Migration Analysis

```bash
# Step 1: Generate full migration report
docker run --rm \
  -v ~/.aws:/root/.aws:ro \
  -v $(pwd)/output:/output \
  aws-migration-tool:latest \
  python aws_migration.py --report

# Step 2: Review VPC details in migration_report.json
cat output/migration_report.json | jq '.vpcs'
```

### Phase 2: VPC Migration (Dry-Run)

```bash
# Dry-run to see what will be created
docker run --rm \
  -v ~/.aws:/root/.aws:ro \
  -v $(pwd)/output:/output \
  aws-migration-tool:latest \
  python aws_migration.py \
    --migrate-vpc vpc-abc123 \
    --dry-run
```

**Review the dry-run output carefully:**
- Verify subnet CIDR blocks don't overlap with existing networks
- Check security group rules
- Review route table configurations
- Note any manual setup requirements

### Phase 3: Execute VPC Migration

```bash
# Execute the actual migration
docker run --rm \
  -v ~/.aws:/root/.aws:ro \
  -v $(pwd)/output:/output \
  aws-migration-tool:latest \
  python aws_migration.py \
    --migrate-vpc vpc-abc123
```

**Optional: Use custom CIDR block**
```bash
# Migrate with different CIDR block
docker run --rm \
  -v ~/.aws:/root/.aws:ro \
  -v $(pwd)/output:/output \
  aws-migration-tool:latest \
  python aws_migration.py \
    --migrate-vpc vpc-abc123 \
    --target-cidr 172.16.0.0/16
```

### Phase 4: Post-Migration Setup

1. **Verify VPC Components**
   ```bash
   # Review the mapping file
   cat output/vpc_migration_mapping.json
   ```

2. **Create VPC Endpoints (if needed)**
   ```bash
   # S3 Gateway Endpoint
   aws ec2 create-vpc-endpoint \
     --vpc-id vpc-new123 \
     --service-name com.amazonaws.us-east-1.s3 \
     --route-table-ids rtb-xxx \
     --profile target_acc
   
   # DynamoDB Gateway Endpoint
   aws ec2 create-vpc-endpoint \
     --vpc-id vpc-new123 \
     --service-name com.amazonaws.us-east-1.dynamodb \
     --route-table-ids rtb-xxx \
     --profile target_acc
   ```

3. **Recreate VPN Connections (if applicable)**
   ```bash
   # Create customer gateway
   aws ec2 create-customer-gateway \
     --type ipsec.1 \
     --public-ip YOUR_VPN_IP \
     --bgp-asn 65000 \
     --profile target_acc
   
   # Create VPN connection
   aws ec2 create-vpn-connection \
     --type ipsec.1 \
     --customer-gateway-id cgw-xxx \
     --vpn-gateway-id vgw-xxx \
     --profile target_acc
   ```

4. **Recreate VPC Peering (if applicable)**
   ```bash
   # Request VPC peering connection
   aws ec2 create-vpc-peering-connection \
     --vpc-id vpc-new123 \
     --peer-vpc-id vpc-peer456 \
     --profile target_acc
   ```

### Phase 5: Migrate Resources to New VPC

Now that the VPC is created, migrate EC2 and RDS instances:

```bash
# Get subnet and security group IDs from mapping file
NEW_VPC_ID=$(cat output/vpc_migration_mapping.json | jq -r '.target_vpc_id')
NEW_SUBNET_ID=$(cat output/vpc_migration_mapping.json | jq -r '.subnet_mapping | to_entries[0].value')
NEW_SG_IDS=$(cat output/vpc_migration_mapping.json | jq -r '.sg_mapping | to_entries | map(.value) | join(",")')

# Migrate EC2 instance
docker run --rm \
  -v ~/.aws:/root/.aws:ro \
  -v $(pwd)/output:/output \
  aws-migration-tool:latest \
  python aws_migration.py \
    --migrate-ec2 i-abc123 \
    --target-vpc $NEW_VPC_ID \
    --target-subnet $NEW_SUBNET_ID \
    --target-security-groups $NEW_SG_IDS \
    --dry-run

# Create RDS subnet group in new VPC
aws rds create-db-subnet-group \
  --db-subnet-group-name my-new-subnet-group \
  --db-subnet-group-description "Migrated subnet group" \
  --subnet-ids subnet-xxx subnet-yyy \
  --profile target_acc

# Migrate RDS instance
docker run --rm \
  -v ~/.aws:/root/.aws:ro \
  -v $(pwd)/output:/output \
  aws-migration-tool:latest \
  python aws_migration.py \
    --migrate-rds mydb \
    --target-subnet-group my-new-subnet-group \
    --target-security-groups $NEW_SG_IDS \
    --dry-run
```

## Resource Mapping

After migration, a mapping file is created at `output/vpc_migration_mapping.json`:

```json
{
  "source_vpc_id": "vpc-abc123",
  "target_vpc_id": "vpc-xyz789",
  "subnet_mapping": {
    "subnet-111": "subnet-aaa",
    "subnet-222": "subnet-bbb"
  },
  "sg_mapping": {
    "sg-111": "sg-aaa",
    "sg-222": "sg-bbb"
  },
  "nat_gateway_mapping": {
    "nat-111": "nat-aaa"
  },
  "route_table_mapping": {
    "rtb-111": "rtb-aaa"
  }
}
```

**Use this mapping to:**
- Update application configurations
- Update infrastructure-as-code templates
- Document the migration
- Migrate dependent resources

## Cross-Region Considerations

When migrating VPCs across regions:

1. **Availability Zones**
   - The script attempts to map AZ suffixes (e.g., us-east-1a → us-west-2a)
   - Verify AZ mappings after migration
   - Some regions have different numbers of AZs

2. **Service Availability**
   - Some AWS services may not be available in all regions
   - Check service availability before migration

3. **Elastic IP Addresses**
   - New Elastic IPs will be allocated
   - Update DNS records and firewall rules
   - Old IPs cannot be moved across regions

4. **VPC Endpoints**
   - Service names differ by region
   - Example: `com.amazonaws.us-east-1.s3` vs `com.amazonaws.us-west-2.s3`

## CIDR Block Considerations

### Using Source CIDR Block (Default)

```bash
# Uses same CIDR as source VPC
python aws_migration.py --migrate-vpc vpc-abc123
```

**Pros:**
- No application changes needed
- Routing configurations remain the same
- Easier to maintain network documentation

**Cons:**
- May conflict with existing VPCs in target account
- Less flexibility for network redesign

### Using Custom CIDR Block

```bash
# Use different CIDR in target
python aws_migration.py --migrate-vpc vpc-abc123 --target-cidr 172.16.0.0/16
```

**Pros:**
- Avoid CIDR conflicts
- Opportunity to redesign network
- Better for long-term network planning

**Cons:**
- Application configurations must be updated
- IP-based security rules need modification
- More complex migration

**Important:** When using custom CIDR:
- Subnet CIDR blocks are automatically recalculated proportionally
- Maintain the same subnet structure
- Update security group rules that reference specific IPs

## Security Considerations

### Security Groups

✅ **Automatically Handled:**
- All ingress/egress rules copied
- Port ranges, protocols, CIDR blocks preserved
- Inter-SG references automatically mapped to new SG IDs

⚠️ **Requires Attention:**
- Rules referencing external security groups (different accounts)
- Rules with IP addresses that may change
- Integration with AWS security services (GuardDuty, Security Hub)

### Network ACLs

✅ **Automatically Handled:**
- All inbound/outbound rules copied
- Rule numbers preserved
- Subnet associations mapped

⚠️ **Review After Migration:**
- Rules may need adjustment for CIDR changes
- Compliance requirements in new account

## Timing and Performance

### Migration Duration

| Component | Estimated Time |
|-----------|---------------|
| VPC Creation | 10-30 seconds |
| Subnets | 5-10 seconds each |
| Internet Gateway | 10-20 seconds |
| NAT Gateways | 2-5 minutes each |
| Security Groups | 10-20 seconds each |
| Route Tables | 20-30 seconds each |
| Network ACLs | 10-20 seconds each |

**Total Time:** 10-15 minutes (depending on complexity)

### Best Practices

1. **Schedule During Maintenance Window**
   - No downtime for source VPC
   - But plan for resource migration afterward

2. **Test Migration in Non-Production First**
   - Migrate a test VPC first
   - Validate all components
   - Document any issues

3. **Use Dry-Run Extensively**
   - Always dry-run first
   - Review all planned changes
   - Get stakeholder approval

4. **Document Everything**
   - Save mapping file
   - Document manual steps
   - Update network diagrams

## Troubleshooting

### Common Issues

#### Issue: Subnet CIDR Overlap

```
Error: The CIDR 'x.x.x.x/x' conflicts with another subnet
```

**Solution:** Use `--target-cidr` with a non-overlapping block

#### Issue: Availability Zone Not Available

```
Error: The requested Availability Zone is not available
```

**Solution:** 
- Check available AZs in target region
- Manually adjust AZ mappings
- Some regions have fewer AZs

#### Issue: NAT Gateway Creation Timeout

```
NAT Gateway is taking longer than expected
```

**Solution:**
- This is normal (NAT Gateways take 2-5 minutes)
- Script waits automatically
- Check AWS console for status

#### Issue: Security Group Rule Dependencies

```
Error: Cannot authorize security group rule
```

**Solution:**
- Security groups are created in two passes
- Source SG references are automatically mapped
- External SG references need manual adjustment

### Validation Steps

After migration, verify:

```bash
# 1. Check VPC
aws ec2 describe-vpcs --vpc-ids vpc-new123 --profile target_acc

# 2. Check subnets
aws ec2 describe-subnets --filters "Name=vpc-id,Values=vpc-new123" --profile target_acc

# 3. Check route tables
aws ec2 describe-route-tables --filters "Name=vpc-id,Values=vpc-new123" --profile target_acc

# 4. Check security groups
aws ec2 describe-security-groups --filters "Name=vpc-id,Values=vpc-new123" --profile target_acc

# 5. Check NAT gateways
aws ec2 describe-nat-gateways --filter "Name=vpc-id,Values=vpc-new123" --profile target_acc

# 6. Check internet gateway
aws ec2 describe-internet-gateways --filters "Name=attachment.vpc-id,Values=vpc-new123" --profile target_acc
```

## Complete Example

Here's a complete migration workflow:

```bash
# 1. Analyze source VPC
docker run --rm -v ~/.aws:/root/.aws:ro -v $(pwd)/output:/output \
  aws-migration-tool:latest python aws_migration.py --report

# 2. Dry-run VPC migration
docker run --rm -v ~/.aws:/root/.aws:ro -v $(pwd)/output:/output \
  aws-migration-tool:latest python aws_migration.py \
  --migrate-vpc vpc-0abc123 --dry-run

# 3. Review and approve

# 4. Execute VPC migration
docker run --rm -v ~/.aws:/root/.aws:ro -v $(pwd)/output:/output \
  aws-migration-tool:latest python aws_migration.py \
  --migrate-vpc vpc-0abc123

# 5. Save the mapping
cp output/vpc_migration_mapping.json vpc_mapping_$(date +%Y%m%d).json

# 6. Verify VPC
aws ec2 describe-vpcs --vpc-ids $(cat vpc_mapping_*.json | jq -r '.target_vpc_id') --profile target_acc

# 7. Create VPC endpoints (example)
NEW_VPC=$(cat vpc_mapping_*.json | jq -r '.target_vpc_id')
NEW_RTB=$(cat vpc_mapping_*.json | jq -r '.route_table_mapping | to_entries[0].value')

aws ec2 create-vpc-endpoint \
  --vpc-id $NEW_VPC \
  --service-name com.amazonaws.us-east-1.s3 \
  --route-table-ids $NEW_RTB \
  --profile target_acc

# 8. Now migrate EC2/RDS instances to new VPC
# ... (see Phase 5 above)
```

## Cost Considerations

### One-Time Costs
- **NAT Gateway:** Hourly charges start immediately (~$0.045/hour)
- **Elastic IPs:** Free if associated, $0.005/hour if unassociated
- **VPN Connection:** $0.05/hour per connection

### Ongoing Costs
- **Data Transfer:** NAT Gateway data processing ($0.045/GB)
- **VPC Endpoints:** Interface endpoints (~$0.01/hour + data)
- **Transit Gateway:** Per attachment and data transfer costs

### Cost Optimization Tips
1. Remove unused NAT Gateways after migration
2. Use VPC endpoints for AWS services to avoid NAT charges
3. Review and optimize security group rules
4. Consider using IPv6 to avoid NAT Gateway costs

## FAQ

**Q: Can I migrate multiple VPCs at once?**
A: Currently, migrate one VPC at a time. Use shell scripts to batch multiple VPCs.

**Q: What happens to the source VPC?**
A: Source VPC remains unchanged. You can keep it or delete it after verifying the migration.

**Q: Can I migrate VPC across regions?**
A: Yes! Use `--source-region` and `--target-region` flags. Note AZ mapping considerations.

**Q: Are VPC flow logs migrated?**
A: No, VPC flow logs must be recreated manually in the target VPC.

**Q: What about DHCP option sets?**
A: Custom DHCP option sets need to be recreated manually and associated with the new VPC.

**Q: Can I change the VPC name during migration?**
A: Yes, the script appends "-migrated" to the name. Edit the tag afterward if needed.

**Q: How do I rollback if something goes wrong?**
A: Source VPC is unchanged. Simply delete the target VPC and retry. No impact to production.

## Related Documentation

- [Migration Workflow Guide](MIGRATION_WORKFLOW.md) - Complete migration process
- [Quick Reference](QUICK_REFERENCE.md) - Command examples
- [Docker Setup Guide](DOCKER_SETUP_GUIDE.md) - Initial setup
- [README](README.md) - Main documentation

---

**Need Help?** Review the migration report, use dry-run mode, and test with non-production VPCs first.
