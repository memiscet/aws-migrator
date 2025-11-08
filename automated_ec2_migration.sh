#!/bin/bash

# Automated EC2 Migration Script
# Migrates EC2 instances from source account to target account
# with proper security group dependency handling

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SOURCE_PROFILE="source_acc"
TARGET_PROFILE="target_acc"
SOURCE_ACCOUNT_ID=""  # Will be auto-detected from AWS profile
TARGET_ACCOUNT_ID=""  # Will be auto-detected from AWS profile
REGION="us-east-1"

echo -e "${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║         AWS EC2 Instance Cross-Account Migration              ║${NC}"
echo -e "${BLUE}║                  Automated Workflow                            ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Function to print step header
print_step() {
    echo ""
    echo -e "${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║  Step $1: $2${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}"
}

# Function to print success message
print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

# Function to print error message
print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Function to print warning message
print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

# Step 1: Verify AWS credentials
print_step "1/12" "Verifying AWS Credentials"

echo "Checking source account credentials..."
if ! aws sts get-caller-identity --profile $SOURCE_PROFILE >/dev/null 2>&1; then
    print_error "Failed to authenticate with source account"
    echo "Please run: aws configure --profile $SOURCE_PROFILE"
    exit 1
fi

SOURCE_ACCOUNT=$(aws sts get-caller-identity --profile $SOURCE_PROFILE --query Account --output text)
print_success "Source account authenticated: $SOURCE_ACCOUNT"

echo "Checking target account credentials..."
if ! aws sts get-caller-identity --profile $TARGET_PROFILE >/dev/null 2>&1; then
    print_error "Failed to authenticate with target account"
    echo "Please run: aws configure --profile $TARGET_PROFILE"
    exit 1
fi

TARGET_ACCOUNT=$(aws sts get-caller-identity --profile $TARGET_PROFILE --query Account --output text)
print_success "Target account authenticated: $TARGET_ACCOUNT"

# Step 2: Verify IAM permissions
print_step "2/12" "Verifying IAM Policies"

echo "Checking source account IAM policy..."
SOURCE_POLICY=$(aws iam get-policy --policy-arn arn:aws:iam::${SOURCE_ACCOUNT}:policy/AWSMigrationToolSourcePolicy --profile $SOURCE_PROFILE 2>/dev/null || echo "")
if [ -z "$SOURCE_POLICY" ]; then
    print_warning "AWSMigrationToolSourcePolicy not found in source account"
    echo "The migration tool will create it automatically"
else
    print_success "Source account policy found"
fi

echo "Checking target account IAM policy..."
TARGET_POLICY=$(aws iam get-policy --policy-arn arn:aws:iam::${TARGET_ACCOUNT}:policy/AWSMigrationToolTargetPolicy --profile $TARGET_PROFILE 2>/dev/null || echo "")
if [ -z "$TARGET_POLICY" ]; then
    print_warning "AWSMigrationToolTargetPolicy not found in target account"
    echo "The migration tool will create it automatically"
else
    print_success "Target account policy found"
fi

# Step 3: Discover EC2 instances
print_step "3/12" "Discovering EC2 Instances in Source Account"

echo "Scanning for EC2 instances in region $REGION..."
INSTANCES=$(aws ec2 describe-instances \
    --profile $SOURCE_PROFILE \
    --region $REGION \
    --filters "Name=instance-state-name,Values=running,stopped" \
    --query 'Reservations[].Instances[].[InstanceId,State.Name,InstanceType,join(`,`,Tags[?Key==`Name`].Value)]' \
    --output text)

if [ -z "$INSTANCES" ]; then
    print_error "No EC2 instances found in source account"
    exit 1
fi

echo ""
echo "Available EC2 instances:"
echo "─────────────────────────────────────────────────────────────"
echo "$INSTANCES" | nl -w2 -s'. '
echo "─────────────────────────────────────────────────────────────"

# Step 4: Select EC2 instance
print_step "4/12" "Selecting EC2 Instance to Migrate"

INSTANCE_COUNT=$(echo "$INSTANCES" | wc -l)
echo "Found $INSTANCE_COUNT EC2 instance(s)"
echo ""
echo -n "Enter the number of the instance to migrate (1-${INSTANCE_COUNT}): "
read SELECTION

# Validate selection
if ! [[ "$SELECTION" =~ ^[0-9]+$ ]]; then
    print_error "Invalid selection. Please enter a number."
    exit 1
fi

if [ "$SELECTION" -lt 1 ] || [ "$SELECTION" -gt "$INSTANCE_COUNT" ]; then
    print_error "Selection out of range. Please enter a number between 1 and $INSTANCE_COUNT."
    exit 1
fi

SELECTED_INSTANCE=$(echo "$INSTANCES" | sed -n "${SELECTION}p" | awk '{print $1}')
INSTANCE_STATE=$(echo "$INSTANCES" | sed -n "${SELECTION}p" | awk '{print $2}')
INSTANCE_TYPE=$(echo "$INSTANCES" | sed -n "${SELECTION}p" | awk '{print $3}')
INSTANCE_NAME=$(echo "$INSTANCES" | sed -n "${SELECTION}p" | cut -f4-)

print_success "Selected instance: $SELECTED_INSTANCE ($INSTANCE_NAME) - State: $INSTANCE_STATE, Type: $INSTANCE_TYPE"

# Step 5: Discover target VPCs
print_step "5/12" "Discovering Target VPCs"

echo "Scanning for VPCs in target account..."
VPCS=$(aws ec2 describe-vpcs \
    --profile $TARGET_PROFILE \
    --region $REGION \
    --query 'Vpcs[].[VpcId,CidrBlock,join(`,`,Tags[?Key==`Name`].Value)]' \
    --output text)

if [ -z "$VPCS" ]; then
    print_error "No VPCs found in target account"
    exit 1
fi

echo ""
echo "Available VPCs:"
echo "─────────────────────────────────────────────────────────────"
echo "$VPCS" | nl -w2 -s'. '
echo "─────────────────────────────────────────────────────────────"

# Step 6: Select target VPC
print_step "6/12" "Selecting Target VPC"

VPC_COUNT=$(echo "$VPCS" | wc -l)
echo "Found $VPC_COUNT VPC(s)"
echo ""
echo -n "Enter the number of the target VPC (1-${VPC_COUNT}): "
read VPC_SELECTION

# Validate selection
if ! [[ "$VPC_SELECTION" =~ ^[0-9]+$ ]]; then
    print_error "Invalid selection. Please enter a number."
    exit 1
fi

if [ "$VPC_SELECTION" -lt 1 ] || [ "$VPC_SELECTION" -gt "$VPC_COUNT" ]; then
    print_error "Selection out of range. Please enter a number between 1 and $VPC_COUNT."
    exit 1
fi

TARGET_VPC=$(echo "$VPCS" | sed -n "${VPC_SELECTION}p" | awk '{print $1}')
VPC_CIDR=$(echo "$VPCS" | sed -n "${VPC_SELECTION}p" | awk '{print $2}')
VPC_NAME=$(echo "$VPCS" | sed -n "${VPC_SELECTION}p" | cut -f3-)

print_success "Selected VPC: $TARGET_VPC ($VPC_NAME) - CIDR: $VPC_CIDR"

# Step 7: Select target subnet
print_step "7/12" "Selecting Target Subnet"

echo "Scanning for subnets in VPC $TARGET_VPC..."
SUBNETS=$(aws ec2 describe-subnets \
    --profile $TARGET_PROFILE \
    --region $REGION \
    --filters "Name=vpc-id,Values=$TARGET_VPC" \
    --query 'Subnets[].[SubnetId,CidrBlock,AvailabilityZone,join(`,`,Tags[?Key==`Name`].Value)]' \
    --output text)

if [ -z "$SUBNETS" ]; then
    print_error "No subnets found in VPC $TARGET_VPC"
    exit 1
fi

echo ""
echo "Available Subnets:"
echo "─────────────────────────────────────────────────────────────"
echo "$SUBNETS" | nl -w2 -s'. '
echo "─────────────────────────────────────────────────────────────"

SUBNET_COUNT=$(echo "$SUBNETS" | wc -l)
echo ""
echo -n "Enter the number of the target subnet (1-${SUBNET_COUNT}): "
read SUBNET_SELECTION

# Validate selection
if ! [[ "$SUBNET_SELECTION" =~ ^[0-9]+$ ]]; then
    print_error "Invalid selection. Please enter a number."
    exit 1
fi

if [ "$SUBNET_SELECTION" -lt 1 ] || [ "$SUBNET_SELECTION" -gt "$SUBNET_COUNT" ]; then
    print_error "Selection out of range. Please enter a number between 1 and $SUBNET_COUNT."
    exit 1
fi

TARGET_SUBNET=$(echo "$SUBNETS" | sed -n "${SUBNET_SELECTION}p" | awk '{print $1}')
SUBNET_CIDR=$(echo "$SUBNETS" | sed -n "${SUBNET_SELECTION}p" | awk '{print $2}')
SUBNET_AZ=$(echo "$SUBNETS" | sed -n "${SUBNET_SELECTION}p" | awk '{print $3}')

print_success "Selected subnet: $TARGET_SUBNET (AZ: $SUBNET_AZ, CIDR: $SUBNET_CIDR)"

# Step 8: Display migration plan
print_step "8/12" "Migration Plan Summary"

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  MIGRATION PLAN"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "Source:"
echo "  Account:         $SOURCE_ACCOUNT"
echo "  Instance ID:     $SELECTED_INSTANCE"
echo "  Instance Name:   $INSTANCE_NAME"
echo "  Instance State:  $INSTANCE_STATE"
echo "  Instance Type:   $INSTANCE_TYPE"
echo ""
echo "Target:"
echo "  Account:         $TARGET_ACCOUNT"
echo "  VPC:             $TARGET_VPC ($VPC_NAME)"
echo "  Subnet:          $TARGET_SUBNET (AZ: $SUBNET_AZ)"
echo ""
echo "Migration Steps:"
echo "  1. Analyze source instance and security groups"
echo "  2. Handle AMI with KMS grants for encrypted snapshots"
echo "  3. Share and copy AMI to target account"
echo "  4. Create volume snapshots with KMS access"
echo "  5. Replicate security groups with dependency resolution"
echo "  6. Launch new instance in target account"
echo "  7. Handle Elastic IP (if applicable)"
echo ""
echo "Security Group Handling:"
echo "  • Automatically replicates all security groups"
echo "  • Handles security group dependencies (SG references)"
echo "  • Updates rules to use target account SG IDs"
echo "  • Preserves CIDR and port configurations"
echo ""
echo "═══════════════════════════════════════════════════════════════"

# Step 9: Confirmation
print_step "9/12" "Confirmation"

echo ""
echo -n "Do you want to proceed with DRY RUN first? (recommended) [Y/n]: "
read DRY_RUN_CONFIRM

if [[ ! "$DRY_RUN_CONFIRM" =~ ^[Nn]$ ]]; then
    # Step 10: Execute dry run
    print_step "10/12" "Executing DRY RUN Migration"
    
    echo ""
    echo "Starting dry run migration..."
    echo "Command: docker run --rm -v ~/.aws:/root/.aws:ro -v $(pwd)/output:/output aws-migration-tool:latest python aws_migration.py --migrate-ec2 $SELECTED_INSTANCE --target-vpc $TARGET_VPC --target-subnet $TARGET_SUBNET --dry-run"
    echo ""
    
    START_TIME=$(date +%s)
    
    docker run --rm \
        -v ~/.aws:/root/.aws:ro \
        -v $(pwd)/output:/output \
        aws-migration-tool:latest \
        python aws_migration.py \
        --migrate-ec2 "$SELECTED_INSTANCE" \
        --target-vpc "$TARGET_VPC" \
        --target-subnet "$TARGET_SUBNET" \
        --dry-run
    
    DRY_RUN_EXIT_CODE=$?
    END_TIME=$(date +%s)
    DURATION=$((END_TIME - START_TIME))
    
    echo ""
    echo "─────────────────────────────────────────────────────────────"
    echo "Dry run completed in $DURATION seconds"
    echo "─────────────────────────────────────────────────────────────"
    
    if [ $DRY_RUN_EXIT_CODE -ne 0 ]; then
        print_error "Dry run failed. Please fix the errors before proceeding."
        exit 1
    fi
    
    print_success "Dry run completed successfully!"
    
    echo ""
    echo -n "Proceed with actual migration? [Y/n]: "
    read ACTUAL_CONFIRM
    
    if [[ "$ACTUAL_CONFIRM" =~ ^[Nn]$ ]]; then
        print_warning "Migration cancelled by user"
        exit 0
    fi
fi

# Step 11: Execute actual migration
print_step "11/12" "Executing ACTUAL Migration"

echo ""
print_warning "IMPORTANT: This will create resources in the target account!"
print_warning "Instance state: $INSTANCE_STATE"
if [ "$INSTANCE_STATE" == "running" ]; then
    print_warning "Consider stopping the instance before migration for data consistency"
fi
echo ""
echo -n "Type 'MIGRATE' to confirm: "
read FINAL_CONFIRM

if [ "$FINAL_CONFIRM" != "MIGRATE" ]; then
    print_warning "Migration cancelled"
    exit 0
fi

echo ""
echo "Starting actual migration..."
echo "Command: docker run --rm -v ~/.aws:/root/.aws:ro -v $(pwd)/output:/output aws-migration-tool:latest python aws_migration.py --migrate-ec2 $SELECTED_INSTANCE --target-vpc $TARGET_VPC --target-subnet $TARGET_SUBNET"
echo ""

START_TIME=$(date +%s)
START_DATETIME=$(date '+%Y-%m-%d %H:%M:%S')

docker run --rm \
    -v ~/.aws:/root/.aws:ro \
    -v $(pwd)/output:/output \
    aws-migration-tool:latest \
    python aws_migration.py \
    --migrate-ec2 "$SELECTED_INSTANCE" \
    --target-vpc "$TARGET_VPC" \
    --target-subnet "$TARGET_SUBNET"

MIGRATION_EXIT_CODE=$?
END_TIME=$(date +%s)
END_DATETIME=$(date '+%Y-%m-%d %H:%M:%S')
DURATION=$((END_TIME - START_TIME))
MINUTES=$((DURATION / 60))
SECONDS=$((DURATION % 60))

# Step 12: Report results
print_step "12/12" "Migration Complete"

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  MIGRATION SUMMARY"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "Source Instance:  $SELECTED_INSTANCE ($INSTANCE_NAME)"
echo "Target VPC:       $TARGET_VPC ($VPC_NAME)"
echo "Target Subnet:    $TARGET_SUBNET"
echo ""
echo "Start Time:       $START_DATETIME"
echo "End Time:         $END_DATETIME"
echo "Duration:         ${MINUTES}m ${SECONDS}s"
echo ""

if [ $MIGRATION_EXIT_CODE -eq 0 ]; then
    print_success "Migration completed successfully!"
    echo ""
    echo "Next Steps:"
    echo "  1. Verify the new instance in target account"
    echo "  2. Test connectivity and security group rules"
    echo "  3. Update DNS/load balancer configurations"
    echo "  4. Validate application functionality"
    echo "  5. Consider decommissioning source instance"
    echo ""
    echo "To find the new instance:"
    echo "  aws ec2 describe-instances --profile $TARGET_PROFILE --filters \"Name=tag:MigratedFrom,Values=$SELECTED_INSTANCE\""
else
    print_error "Migration failed with exit code $MIGRATION_EXIT_CODE"
    echo ""
    echo "Please check the error messages above and:"
    echo "  1. Verify IAM permissions"
    echo "  2. Check KMS key policies"
    echo "  3. Ensure target VPC/subnet configuration"
    echo "  4. Review security group dependencies"
    exit 1
fi

echo ""
echo "═══════════════════════════════════════════════════════════════"
