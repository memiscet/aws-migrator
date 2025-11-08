# EC2 Migration Quick Reference

## 🚀 One-Command Migration

```bash
./automated_ec2_migration.sh
```

Follow the prompts to:
1. Select source EC2 instance
2. Choose target VPC
3. Choose target subnet
4. Review migration plan
5. Execute dry-run (recommended)
6. Confirm actual migration

## 🔑 Key Features

| Feature | Status | Description |
|---------|--------|-------------|
| **Security Group Dependencies** | ✅ AUTO | Automatically resolves SG references |
| **AMI Migration** | ✅ AUTO | Shares and copies with KMS grants |
| **Volume Snapshots** | ✅ AUTO | All volumes migrated with snapshots |
| **Encryption** | ✅ AUTO | KMS access configured automatically |
| **Elastic IP** | ✅ AUTO | Allocated and associated |
| **Dry Run** | ✅ SAFE | Validate before actual migration |

## ⏱️ Performance

```
Total Time: 12-20 minutes per instance

Breakdown:
├─ Instance Analysis     30s
├─ AMI Copy             5-8min
├─ Volume Snapshots     3-5min
├─ Security Groups      1-2min  ← NEW: Auto-dependency resolution!
├─ Instance Launch      2-3min
└─ Validation           1min
```

## 🔒 Security Group Intelligence

### What It Handles

```
Source Account:
┌─────────────┐
│   sg-lb     │ Allow 443 from 0.0.0.0/0
└──────┬──────┘
       │
┌──────▼──────┐
│   sg-web    │ Allow 8080 from sg-lb ← Reference to sg-lb
└──────┬──────┘
       │
┌──────▼──────┐
│   sg-app    │ Allow 5432 from sg-web ← Reference to sg-web
└─────────────┘

Target Account (After Migration):
┌─────────────────────┐
│   sg-lb-migrated    │ Allow 443 from 0.0.0.0/0
└──────┬──────────────┘
       │
┌──────▼──────────────┐
│   sg-web-migrated   │ Allow 8080 from sg-lb-migrated ← AUTO-UPDATED!
└──────┬──────────────┘
       │
┌──────▼──────────────┐
│   sg-app-migrated   │ Allow 5432 from sg-web-migrated ← AUTO-UPDATED!
└─────────────────────┘
```

### Process

1. **Collect** all security groups from instance
2. **Create** all SGs in target VPC
3. **Map** source SG IDs → target SG IDs
4. **Update** rules with new SG IDs
5. **Apply** corrected rules

## 📋 Prerequisites Checklist

- [ ] AWS credentials configured (source_acc, target_acc)
- [ ] IAM policies attached (auto-created by tool)
- [ ] Target VPC exists
- [ ] Key pair exists in target (same name as source)
- [ ] Docker image built (`docker build -t aws-migration-tool:latest .`)

## 🎯 Common Use Cases

### Case 1: Single Instance Migration

```bash
./automated_ec2_migration.sh
# Select: Instance 1
# Result: Instance + all SGs migrated
```

### Case 2: Multi-Tier Application

```bash
# Migrate web tier
./automated_ec2_migration.sh  # Select web instance

# Migrate app tier  
./automated_ec2_migration.sh  # Select app instance (reuses web SGs)

# Migrate DB tier
./automated_ec2_migration.sh  # Select db instance (reuses app SGs)
```

### Case 3: Microservices Cluster

```bash
# Each instance can be migrated independently
# Shared SGs automatically reused
./automated_ec2_migration.sh  # Service A
./automated_ec2_migration.sh  # Service B
./automated_ec2_migration.sh  # Service C
```

## 🔍 Validation Commands

### Find Migrated Instance

```bash
aws ec2 describe-instances \
  --profile target_acc \
  --filters "Name=tag:MigratedFrom,Values=i-SOURCE-ID" \
  --query 'Reservations[0].Instances[0].[InstanceId,State.Name,PrivateIpAddress]' \
  --output table
```

### Check Security Groups

```bash
# List migrated security groups
aws ec2 describe-security-groups \
  --profile target_acc \
  --filters "Name=vpc-id,Values=vpc-TARGET-VPC" \
  --query 'SecurityGroups[?contains(GroupName, `migrated`)].[GroupId,GroupName]' \
  --output table
```

### Verify SG Rules

```bash
# Check specific security group
aws ec2 describe-security-groups \
  --profile target_acc \
  --group-ids sg-MIGRATED-ID \
  --query 'SecurityGroups[0].IpPermissions' \
  --output json
```

### Test Connectivity

```bash
# SSH to instance
ssh -i ~/.ssh/key.pem ec2-user@PUBLIC-IP

# Test application
curl http://PRIVATE-IP:8080
```

## 🐛 Troubleshooting

| Issue | Solution |
|-------|----------|
| "Key pair not found" | Create key pair in target with same name |
| "AccessDenied" | Run `--setup-policies` or check IAM |
| "Subnet has no IPs" | Choose different subnet |
| "AMI copy failed" | Check KMS permissions (auto-created) |
| "SG reference not found" | Normal for external refs, check logs |

## 📊 Progress Indicators

During migration, you'll see:

```
✅ Step completed successfully
⚠️  Warning (migration continues)
❌ Error (migration stops)
🔒 Security group operation
🖼️  AMI operation
💾 Snapshot operation
🖥️  Instance operation
```

## 🔄 Dry Run vs Actual

### Dry Run (Recommended First)
```bash
./automated_ec2_migration.sh
# Answer: Y to dry run

Result:
• Validates configuration
• Shows what WOULD happen
• No resources created
• Safe to run multiple times
```

### Actual Migration
```bash
./automated_ec2_migration.sh
# Answer: N to skip dry run or proceed after dry run
# Confirm with: MIGRATE

Result:
• Creates actual resources
• Takes 12-20 minutes
• Charges AWS costs
• Instance available in target
```

## 💡 Pro Tips

1. **Always Dry Run First**
   ```bash
   # Answer "Y" when prompted for dry run
   # Review output for issues
   # Then proceed with actual
   ```

2. **Stop Source Instance** (for data consistency)
   ```bash
   aws ec2 stop-instances --instance-ids i-SOURCE --profile source_acc
   ```

3. **Migrate During Maintenance Window**
   - Coordinate with team
   - Update DNS after validation
   - Keep source running for rollback

4. **Test Connectivity Immediately**
   ```bash
   # As soon as migration completes
   ssh -i key.pem ec2-user@NEW-IP
   systemctl status your-app
   ```

5. **Multiple Instances with Same SGs**
   ```bash
   # First instance: Creates all SGs (slower)
   # Subsequent: Reuses SGs (faster)
   ```

## 📚 Documentation Links

- **Complete Guide:** [EC2_MIGRATION_GUIDE.md](EC2_MIGRATION_GUIDE.md)
- **Implementation:** [EC2_MIGRATION_IMPLEMENTATION_SUMMARY.md](EC2_MIGRATION_IMPLEMENTATION_SUMMARY.md)
- **Main README:** [README.md](README.md)

## 🎬 Example Session

```bash
$ ./automated_ec2_migration.sh

╔════════════════════════════════════════════════════════════════╗
║         AWS EC2 Instance Cross-Account Migration              ║
║                  Automated Workflow                            ║
╚════════════════════════════════════════════════════════════════╝

╔════════════════════════════════════════════════════════════════╗
║  Step 1/12: Verifying AWS Credentials
╚════════════════════════════════════════════════════════════════╝
✅ Source account authenticated: 123456789012
✅ Target account authenticated: 987654321098

...

╔════════════════════════════════════════════════════════════════╗
║  Step 3/12: Discovering EC2 Instances in Source Account
╚════════════════════════════════════════════════════════════════╝

Available EC2 instances:
─────────────────────────────────────────────────────────────
 1. i-0abc123  running  t3.medium  web-server-prod
 2. i-0def456  running  t3.large   app-server-prod
 3. i-0ghi789  stopped  t3.small   db-server-test
─────────────────────────────────────────────────────────────

Enter the number of the instance to migrate (1-3): 1

✅ Selected instance: i-0abc123 (web-server-prod) - State: running

...

╔════════════════════════════════════════════════════════════════╗
║  Step 8/12: Migration Plan Summary
╚════════════════════════════════════════════════════════════════╝

═══════════════════════════════════════════════════════════════
  MIGRATION PLAN
═══════════════════════════════════════════════════════════════

Source:
  Instance ID:     i-0abc123
  Instance Name:   web-server-prod
  Instance Type:   t3.medium

Target:
  VPC:             vpc-0261473d76d9c5d21 (DEV-VPC1)
  Subnet:          subnet-0a1b2c3d4e5f6g7h8

Security Group Handling:
  • Automatically replicates all security groups
  • Handles security group dependencies (SG references)
  • Updates rules to use target account SG IDs
  • Preserves CIDR and port configurations

═══════════════════════════════════════════════════════════════

Proceed with DRY RUN first? (recommended) [Y/n]: Y

...

╔════════════════════════════════════════════════════════════════╗
║  Step 12/12: Migration Complete
╚════════════════════════════════════════════════════════════════╝

✅ Migration completed successfully!
Duration: 18m 32s
```

## 🏆 Success Criteria

Migration is successful when:

- [ ] New instance shows "running" state
- [ ] Security groups exist with "-migrated" suffix
- [ ] Security group rules reference target SG IDs (not source)
- [ ] SSH connection works
- [ ] Application starts correctly
- [ ] Network connectivity verified (internal + external)
- [ ] Tags include "MigratedFrom" with source instance ID

---

**Ready to migrate? Run: `./automated_ec2_migration.sh`**
