# IAM Setup Guide

Complete guide for setting up IAM permissions for the AWS Migration Tool.

## 🚀 Quick Setup (Automated)

The migration tool can automatically create the required IAM policies in both accounts.

### Step 1: Preview Policies (Dry-Run)

```bash
docker run --rm -v ~/.aws:/root/.aws:ro aws-migration-tool:latest \
  python aws_migration.py --setup-policies --dry-run
```

This shows you what policies will be created without making any changes.

### Step 2: Create Policies

```bash
docker run --rm -v ~/.aws:/root/.aws:ro aws-migration-tool:latest \
  python aws_migration.py --setup-policies
```

This creates two managed policies:
- **Source Account**: `AWSMigrationToolSourcePolicy`
- **Target Account**: `AWSMigrationToolTargetPolicy`

### Step 3: Attach Policies to Users

After policies are created, attach them to your IAM users or roles:

**Source Account:**
```bash
aws iam attach-user-policy \
  --user-name YOUR_SOURCE_USER \
  --policy-arn arn:aws:iam::SOURCE_ACCOUNT_ID:policy/AWSMigrationToolSourcePolicy \
  --profile source_acc
```

**Target Account:**
```bash
aws iam attach-user-policy \
  --user-name YOUR_TARGET_USER \
  --policy-arn arn:aws:iam::TARGET_ACCOUNT_ID:policy/AWSMigrationToolTargetPolicy \
  --profile target_acc
```

---

## 📋 What Policies Are Created?

### Source Account Policy: `AWSMigrationToolSourcePolicy`

**Purpose**: Read-only access to analyze and snapshot resources in the source account.

**Permissions Include**:
- ✅ **EC2 Read**: Describe instances, images, volumes, snapshots
- ✅ **EC2 Snapshot**: Create images and snapshots for migration
- ✅ **RDS Read**: Describe DB instances, clusters, snapshots
- ✅ **RDS Snapshot**: Create and share DB snapshots
- ✅ **KMS**: Decrypt and describe keys for encrypted resources
- ✅ **IAM Read**: Get user/role information

**Key Actions**:
```
ec2:Describe*, ec2:CreateImage, ec2:CreateSnapshot, ec2:CopySnapshot
rds:Describe*, rds:CreateDBSnapshot, rds:ModifyDBSnapshotAttribute
kms:Describe*, kms:Decrypt, kms:CreateGrant
```

### Target Account Policy: `AWSMigrationToolTargetPolicy`

**Purpose**: Full permissions to create and configure migrated resources in the target account.

**Permissions Include**:
- ✅ **VPC Full**: Create/modify VPCs, subnets, route tables, NACLs
- ✅ **Security Groups**: Create and configure security groups
- ✅ **Internet Gateway**: Create and attach IGWs
- ✅ **NAT Gateway**: Create NAT gateways and allocate Elastic IPs
- ✅ **EC2 Full**: Launch instances, create AMIs, volumes, snapshots
- ✅ **RDS Full**: Restore DB instances from snapshots, create DB subnet groups
- ✅ **KMS Full**: Create keys, encrypt/decrypt, manage grants
- ✅ **IAM PassRole**: Pass roles to EC2 and RDS services

**Key Actions**:
```
ec2:*, rds:*, kms:*, iam:PassRole
```

---

## 🔄 Alternative: Create New Migration User

Instead of using existing users, you can create dedicated migration users:

### Source Account

```bash
# Create user
aws iam create-user --user-name aws-migration-source --profile source_acc

# Attach policy
aws iam attach-user-policy \
  --user-name aws-migration-source \
  --policy-arn arn:aws:iam::SOURCE_ACCOUNT_ID:policy/AWSMigrationToolSourcePolicy \
  --profile source_acc

# Create access keys
aws iam create-access-key --user-name aws-migration-source --profile source_acc
```

### Target Account

```bash
# Create user
aws iam create-user --user-name aws-migration-target --profile target_acc

# Attach policy
aws iam attach-user-policy \
  --user-name aws-migration-target \
  --policy-arn arn:aws:iam::TARGET_ACCOUNT_ID:policy/AWSMigrationToolTargetPolicy \
  --profile target_acc

# Create access keys
aws iam create-access-key --user-name aws-migration-taclearrget --profile target_acc
```

Then update your `~/.aws/credentials` with the new access keys.

---

## 🔐 Security Best Practices

### 1. Use Temporary Credentials
Consider using AWS STS assume-role for temporary credentials:
```bash
aws sts assume-role \
  --role-arn arn:aws:iam::ACCOUNT_ID:role/MigrationRole \
  --role-session-name migration-session
```

### 2. Enable MFA
Require MFA for sensitive operations:
```json
"Condition": {
  "Bool": {
    "aws:MultiFactorAuthPresent": "true"
  }
}
```

### 3. Limit by IP
Restrict access to specific IP addresses:
```json
"Condition": {
  "IpAddress": {
    "aws:SourceIp": "YOUR_IP_ADDRESS/32"
  }
}
```

### 4. Time-Limited Access
Create policies that expire after migration:
```bash
aws iam attach-user-policy \
  --user-name migration-user \
  --policy-arn arn:aws:iam::ACCOUNT_ID:policy/MigrationPolicy \
  --duration-seconds 86400
```

### 5. Audit and Monitor
- Enable CloudTrail in both accounts
- Monitor IAM credential reports
- Review AWS Access Analyzer findings
- Remove policies after migration completes

---

## 🛠️ Manual Policy Setup

If you prefer to create policies manually, here are the JSON documents:

### Source Account Policy

<details>
<summary>Click to expand JSON</summary>

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "EC2ReadPermissions",
      "Effect": "Allow",
      "Action": [
        "ec2:Describe*",
        "ec2:CreateImage",
        "ec2:CopyImage",
        "ec2:CreateSnapshot",
        "ec2:CopySnapshot",
        "ec2:CreateTags",
        "ec2:GetConsoleOutput"
      ],
      "Resource": "*"
    },
    {
      "Sid": "RDSReadPermissions",
      "Effect": "Allow",
      "Action": [
        "rds:Describe*",
        "rds:CreateDBSnapshot",
        "rds:CreateDBClusterSnapshot",
        "rds:CopyDBSnapshot",
        "rds:CopyDBClusterSnapshot",
        "rds:ModifyDBSnapshotAttribute",
        "rds:ModifyDBClusterSnapshotAttribute",
        "rds:ListTagsForResource",
        "rds:AddTagsToResource"
      ],
      "Resource": "*"
    },
    {
      "Sid": "KMSPermissions",
      "Effect": "Allow",
      "Action": [
        "kms:Describe*",
        "kms:List*",
        "kms:CreateGrant",
        "kms:Decrypt",
        "kms:DescribeKey",
        "kms:GetKeyPolicy"
      ],
      "Resource": "*"
    },
    {
      "Sid": "IAMReadPermissions",
      "Effect": "Allow",
      "Action": [
        "iam:GetUser",
        "iam:GetRole",
        "iam:ListAttachedUserPolicies",
        "iam:ListAttachedRolePolicies"
      ],
      "Resource": "*"
    }
  ]
}
```

</details>

### Target Account Policy

<details>
<summary>Click to expand JSON (large)</summary>

See the full policy in the tool output or use `--setup-policies --dry-run` to view it.

</details>

---

## 🔍 Verify Policy Attachment

Check if policies are attached correctly:

```bash
# Source account
aws iam list-attached-user-policies --user-name YOUR_USER --profile source_acc

# Target account
aws iam list-attached-user-policies --user-name YOUR_USER --profile target_acc
```

---

## 🧪 Test Permissions

Verify permissions are working:

```bash
# Test source account (read-only)
docker run --rm -v ~/.aws:/root/.aws:ro aws-migration-tool:latest \
  python aws_migration.py --report

# Test target account (create test VPC)
aws ec2 create-vpc --cidr-block 10.99.0.0/16 --profile target_acc
aws ec2 delete-vpc --vpc-id vpc-xxx --profile target_acc
```

---

## ❌ Troubleshooting

### Error: "User is not authorized to perform: iam:CreatePolicy"

**Solution**: Your AWS credentials need IAM admin permissions to create policies. Either:
1. Use an admin account to run `--setup-policies`
2. Have your AWS admin create the policies manually
3. Use the JSON documents provided above

### Error: "Policy already exists"

**Solution**: The tool will automatically create a new version of the existing policy. If you hit the 5-version limit, it will delete the oldest version first.

### Error: "Access Denied" during migration

**Solution**: 
1. Verify policies are attached: `aws iam list-attached-user-policies`
2. Check you're using the correct profile names
3. Ensure policies have all required permissions
4. Run `--setup-policies` again to update policies

### Minimum Permissions for Setup Script

To run `--setup-policies`, you need:
```
iam:CreatePolicy
iam:GetPolicy
iam:CreatePolicyVersion
iam:ListPolicyVersions
iam:DeletePolicyVersion
```

---

## 📝 Policy Lifecycle

### During Migration
1. ✅ Policies are in use
2. ✅ Monitor CloudTrail for unauthorized access
3. ✅ Keep policies active

### After Migration
1. 🧹 Detach policies from users
2. 🧹 Delete or archive policies
3. 🧹 Revoke access keys for migration users
4. 🧹 Document what was migrated

```bash
# Detach policies
aws iam detach-user-policy \
  --user-name migration-user \
  --policy-arn arn:aws:iam::ACCOUNT_ID:policy/AWSMigrationToolSourcePolicy

# Delete policy (optional)
aws iam delete-policy \
  --policy-arn arn:aws:iam::ACCOUNT_ID:policy/AWSMigrationToolSourcePolicy
```

---

## 🎯 Summary

**Quick Commands**:
```bash
# 1. Setup policies (automated)
docker run --rm -v ~/.aws:/root/.aws:ro aws-migration-tool:latest \
  python aws_migration.py --setup-policies

# 2. Attach to users (replace ACCOUNT_ID and USER_NAME)
aws iam attach-user-policy --user-name USER --policy-arn arn:aws:iam::ACCOUNT_ID:policy/AWSMigrationToolSourcePolicy
aws iam attach-user-policy --user-name USER --policy-arn arn:aws:iam::ACCOUNT_ID:policy/AWSMigrationToolTargetPolicy

# 3. Verify
aws iam list-attached-user-policies --user-name USER

# 4. Test
docker run --rm -v ~/.aws:/root/.aws:ro aws-migration-tool:latest \
  python aws_migration.py --report
```

You're ready to migrate! 🚀
