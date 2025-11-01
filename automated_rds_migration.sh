#!/bin/bash

##############################################################################
# Automated RDS Migration Script
# Migrates RDS instance from source account to target account
##############################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_info() { echo -e "${BLUE}ℹ️  $1${NC}"; }
print_success() { echo -e "${GREEN}✅ $1${NC}"; }
print_warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
print_error() { echo -e "${RED}❌ $1${NC}"; }
print_header() { echo -e "\n${BLUE}========================================${NC}\n${BLUE}$1${NC}\n${BLUE}========================================${NC}"; }

# Target VPC Configuration
TARGET_VPC="vpc-0261473d76d9c5d21"
TARGET_VPC_NAME="DEV-VPC1"
TARGET_VPC_CIDR="10.1.0.0/16"
DB_SUBNET_GROUP_NAME="migrated-db-subnet-group"
SECURITY_GROUP_NAME="migrated-rds-sg"

print_header "Automated RDS Migration to $TARGET_VPC_NAME"

##############################################################################
# STEP 1: Verify AWS Profiles
##############################################################################
print_header "Step 1: Verifying AWS Profiles"

print_info "Checking source_acc profile..."
SOURCE_ACCOUNT=$(aws sts get-caller-identity --profile source_acc --query 'Account' --output text 2>/dev/null || echo "")
if [ -z "$SOURCE_ACCOUNT" ]; then
    print_error "source_acc profile not configured or invalid"
    exit 1
fi
print_success "Source account: $SOURCE_ACCOUNT"

print_info "Checking target_acc profile..."
TARGET_ACCOUNT=$(aws sts get-caller-identity --profile target_acc --query 'Account' --output text 2>/dev/null || echo "")
if [ -z "$TARGET_ACCOUNT" ]; then
    print_error "target_acc profile not configured or invalid"
    exit 1
fi
print_success "Target account: $TARGET_ACCOUNT"

##############################################################################
# STEP 2: Get RDS Instance from Source
##############################################################################
print_header "Step 2: Discovering RDS Instances in Source Account"

print_info "Fetching RDS instances..."
RDS_INSTANCES=$(aws rds describe-db-instances \
  --profile source_acc \
  --query 'DBInstances[*].DBInstanceIdentifier' \
  --output text 2>/dev/null || echo "")

if [ -z "$RDS_INSTANCES" ]; then
    print_error "No RDS instances found in source account"
    exit 1
fi

echo ""
echo "Available RDS instances:"
echo "------------------------"
i=1
for instance in $RDS_INSTANCES; do
    # Get instance details
    ENGINE=$(aws rds describe-db-instances \
      --db-instance-identifier $instance \
      --profile source_acc \
      --query 'DBInstances[0].Engine' \
      --output text 2>/dev/null)
    
    CLASS=$(aws rds describe-db-instances \
      --db-instance-identifier $instance \
      --profile source_acc \
      --query 'DBInstances[0].DBInstanceClass' \
      --output text 2>/dev/null)
    
    STORAGE=$(aws rds describe-db-instances \
      --db-instance-identifier $instance \
      --profile source_acc \
      --query 'DBInstances[0].AllocatedStorage' \
      --output text 2>/dev/null)
    
    ENCRYPTED=$(aws rds describe-db-instances \
      --db-instance-identifier $instance \
      --profile source_acc \
      --query 'DBInstances[0].StorageEncrypted' \
      --output text 2>/dev/null)
    
    echo "$i) $instance"
    echo "   Engine: $ENGINE | Class: $CLASS | Storage: ${STORAGE}GB | Encrypted: $ENCRYPTED"
    echo ""
    i=$((i + 1))
done

# Auto-select if only one instance
INSTANCE_COUNT=$(echo "$RDS_INSTANCES" | wc -w | tr -d ' ')
if [ "$INSTANCE_COUNT" -eq 1 ]; then
    RDS_INSTANCE="$RDS_INSTANCES"
    print_success "Auto-selected (only one instance): $RDS_INSTANCE"
else
    # Prompt user to select
    read -p "Select RDS instance number to migrate (1-$INSTANCE_COUNT): " selection
    RDS_INSTANCE=$(echo "$RDS_INSTANCES" | tr ' ' '\n' | sed -n "${selection}p")
    print_success "Selected: $RDS_INSTANCE"
fi

# Get RDS engine for port detection
RDS_ENGINE=$(aws rds describe-db-instances \
  --db-instance-identifier $RDS_INSTANCE \
  --profile source_acc \
  --query 'DBInstances[0].Engine' \
  --output text)

# Detect database port
if [[ "$RDS_ENGINE" == *"mysql"* ]] || [[ "$RDS_ENGINE" == *"aurora-mysql"* ]] || [[ "$RDS_ENGINE" == *"mariadb"* ]]; then
    DB_PORT=3306
elif [[ "$RDS_ENGINE" == *"postgres"* ]] || [[ "$RDS_ENGINE" == *"aurora-postgresql"* ]]; then
    DB_PORT=5432
elif [[ "$RDS_ENGINE" == *"sqlserver"* ]]; then
    DB_PORT=1433
elif [[ "$RDS_ENGINE" == *"oracle"* ]]; then
    DB_PORT=1521
else
    DB_PORT=3306  # Default
fi

print_info "Detected database engine: $RDS_ENGINE (port: $DB_PORT)"

##############################################################################
# STEP 3: Get Subnets in Target VPC
##############################################################################
print_header "Step 3: Getting Subnets in Target VPC"

print_info "Fetching subnets in $TARGET_VPC ($TARGET_VPC_NAME)..."
SUBNETS=$(aws ec2 describe-subnets \
  --filters "Name=vpc-id,Values=$TARGET_VPC" \
  --profile target_acc \
  --query 'Subnets[*].SubnetId' \
  --output text)

if [ -z "$SUBNETS" ]; then
    print_error "No subnets found in target VPC $TARGET_VPC"
    exit 1
fi

SUBNET_COUNT=$(echo "$SUBNETS" | wc -w | tr -d ' ')
print_success "Found $SUBNET_COUNT subnets"

# Show subnet details
aws ec2 describe-subnets \
  --filters "Name=vpc-id,Values=$TARGET_VPC" \
  --profile target_acc \
  --query 'Subnets[*].[SubnetId,CidrBlock,AvailabilityZone]' \
  --output table

##############################################################################
# STEP 4: Create DB Subnet Group
##############################################################################
print_header "Step 4: Creating DB Subnet Group"

# Check if DB subnet group already exists
EXISTING_SUBNET_GROUP=$(aws rds describe-db-subnet-groups \
  --db-subnet-group-name $DB_SUBNET_GROUP_NAME \
  --profile target_acc \
  --query 'DBSubnetGroups[0].DBSubnetGroupName' \
  --output text 2>/dev/null || echo "")

if [ "$EXISTING_SUBNET_GROUP" == "$DB_SUBNET_GROUP_NAME" ]; then
    print_warning "DB subnet group '$DB_SUBNET_GROUP_NAME' already exists"
else
    print_info "Creating DB subnet group '$DB_SUBNET_GROUP_NAME'..."
    aws rds create-db-subnet-group \
      --db-subnet-group-name $DB_SUBNET_GROUP_NAME \
      --db-subnet-group-description "Subnet group for migrated RDS to $TARGET_VPC_NAME" \
      --subnet-ids $SUBNETS \
      --profile target_acc > /dev/null
    
    print_success "DB subnet group created successfully"
fi

##############################################################################
# STEP 5: Create Security Group
##############################################################################
print_header "Step 5: Creating Security Group"

# Check if security group already exists
EXISTING_SG=$(aws ec2 describe-security-groups \
  --filters "Name=group-name,Values=$SECURITY_GROUP_NAME" \
  --filters "Name=vpc-id,Values=$TARGET_VPC" \
  --profile target_acc \
  --query 'SecurityGroups[0].GroupId' \
  --output text 2>/dev/null || echo "")

if [ "$EXISTING_SG" != "None" ] && [ -n "$EXISTING_SG" ]; then
    TARGET_SG="$EXISTING_SG"
    print_warning "Security group already exists: $TARGET_SG"
else
    print_info "Creating security group '$SECURITY_GROUP_NAME'..."
    TARGET_SG=$(aws ec2 create-security-group \
      --group-name $SECURITY_GROUP_NAME \
      --description "Security group for migrated RDS instance" \
      --vpc-id $TARGET_VPC \
      --profile target_acc \
      --query 'GroupId' \
      --output text)
    
    print_success "Security group created: $TARGET_SG"
    
    # Add inbound rule
    print_info "Adding inbound rule for port $DB_PORT..."
    aws ec2 authorize-security-group-ingress \
      --group-id $TARGET_SG \
      --protocol tcp \
      --port $DB_PORT \
      --cidr $TARGET_VPC_CIDR \
      --profile target_acc > /dev/null 2>&1 || print_warning "Inbound rule might already exist"
    
    print_success "Inbound rule added for port $DB_PORT"
fi

##############################################################################
# STEP 6: Build Docker Image
##############################################################################
print_header "Step 6: Ensuring Docker Image is Built"

if docker images | grep -q "aws-migration-tool.*latest"; then
    print_success "Docker image 'aws-migration-tool:latest' found"
else
    print_info "Building Docker image..."
    docker build -t aws-migration-tool:latest . > /dev/null 2>&1
    print_success "Docker image built successfully"
fi

##############################################################################
# STEP 7: Generate Migration Report
##############################################################################
print_header "Step 7: Generating Migration Report"

print_info "Analyzing resources in both accounts..."
docker run --rm -v ~/.aws:/root/.aws:ro -v $(pwd)/output:/output \
  aws-migration-tool:latest python aws_migration.py --report

if [ -f "output/migration_report.json" ]; then
    print_success "Migration report generated: output/migration_report.json"
else
    print_error "Failed to generate migration report"
    exit 1
fi

##############################################################################
# STEP 8: Setup IAM Policies (if needed)
##############################################################################
print_header "Step 8: Verifying IAM Policies"

print_info "Checking if IAM policies exist..."
SOURCE_POLICY=$(aws iam get-policy \
  --policy-arn "arn:aws:iam::${SOURCE_ACCOUNT}:policy/AWSMigrationToolSourcePolicy" \
  --profile source_acc \
  --query 'Policy.PolicyName' \
  --output text 2>/dev/null || echo "")

if [ -z "$SOURCE_POLICY" ]; then
    print_warning "IAM policies not found. Creating them..."
    docker run --rm -v ~/.aws:/root/.aws:ro \
      aws-migration-tool:latest python aws_migration.py --setup-policies
    print_success "IAM policies created"
else
    print_success "IAM policies already configured"
fi

##############################################################################
# STEP 9: Dry-Run Migration
##############################################################################
print_header "Step 9: Running Dry-Run Migration"

print_info "Performing dry-run to validate migration plan..."
echo ""

docker run --rm -v ~/.aws:/root/.aws:ro -v $(pwd)/output:/output \
  aws-migration-tool:latest python aws_migration.py \
  --migrate-rds $RDS_INSTANCE \
  --target-subnet-group $DB_SUBNET_GROUP_NAME \
  --target-security-groups $TARGET_SG \
  --dry-run

echo ""
print_success "Dry-run completed successfully"

##############################################################################
# STEP 10: Execute Migration
##############################################################################
print_header "Step 10: Execute Migration"

echo ""
echo "======================================"
echo "Migration Summary"
echo "======================================"
echo "Source RDS Instance:     $RDS_INSTANCE"
echo "Source Account:          $SOURCE_ACCOUNT"
echo "Target VPC:              $TARGET_VPC ($TARGET_VPC_NAME)"
echo "Target Account:          $TARGET_ACCOUNT"
echo "Target Subnet Group:     $DB_SUBNET_GROUP_NAME"
echo "Target Security Group:   $TARGET_SG"
echo "Database Port:           $DB_PORT"
echo "======================================"
echo ""

read -p "Execute actual migration? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    print_warning "Migration cancelled by user"
    exit 0
fi

print_info "Starting RDS migration..."
echo ""

docker run --rm -v ~/.aws:/root/.aws:ro -v $(pwd)/output:/output \
  aws-migration-tool:latest python aws_migration.py \
  --migrate-rds $RDS_INSTANCE \
  --target-subnet-group $DB_SUBNET_GROUP_NAME \
  --target-security-groups $TARGET_SG

MIGRATION_EXIT_CODE=$?

if [ $MIGRATION_EXIT_CODE -eq 0 ]; then
    print_success "Migration completed successfully!"
else
    print_error "Migration failed with exit code $MIGRATION_EXIT_CODE"
    exit $MIGRATION_EXIT_CODE
fi

##############################################################################
# STEP 11: Verify Migration
##############################################################################
print_header "Step 11: Verifying Migration"

MIGRATED_INSTANCE="${RDS_INSTANCE}-migrated"

print_info "Waiting for RDS instance to become available..."
sleep 10

print_info "Checking migrated instance status..."
INSTANCE_STATUS=$(aws rds describe-db-instances \
  --db-instance-identifier $MIGRATED_INSTANCE \
  --profile target_acc \
  --query 'DBInstances[0].DBInstanceStatus' \
  --output text 2>/dev/null || echo "not-found")

if [ "$INSTANCE_STATUS" == "not-found" ]; then
    print_error "Migrated instance not found: $MIGRATED_INSTANCE"
    exit 1
fi

print_success "Migrated instance status: $INSTANCE_STATUS"

# Get endpoint
if [ "$INSTANCE_STATUS" == "available" ]; then
    ENDPOINT=$(aws rds describe-db-instances \
      --db-instance-identifier $MIGRATED_INSTANCE \
      --profile target_acc \
      --query 'DBInstances[0].Endpoint.Address' \
      --output text)
    
    print_success "Instance is available!"
    print_success "Connection endpoint: $ENDPOINT:$DB_PORT"
else
    print_warning "Instance is still being created: $INSTANCE_STATUS"
    print_info "Monitor status with: aws rds describe-db-instances --db-instance-identifier $MIGRATED_INSTANCE --profile target_acc"
fi

##############################################################################
# STEP 12: Summary
##############################################################################
print_header "Migration Complete!"

echo ""
echo "======================================"
echo "Migration Results"
echo "======================================"
echo "Source Instance:         $RDS_INSTANCE"
echo "Migrated Instance:       $MIGRATED_INSTANCE"
echo "Status:                  $INSTANCE_STATUS"
if [ "$INSTANCE_STATUS" == "available" ]; then
    echo "Endpoint:                $ENDPOINT"
    echo "Port:                    $DB_PORT"
fi
echo "VPC:                     $TARGET_VPC ($TARGET_VPC_NAME)"
echo "Security Group:          $TARGET_SG"
echo "======================================"
echo ""

print_info "Output files:"
echo "  - Migration report:    output/migration_report.json"
echo "  - Migration mapping:   output/vpc_migration_mapping.json"
echo ""

print_success "All done! 🚀"
echo ""

# Next steps
echo "Next Steps:"
echo "1. Wait for instance to become 'available' if not already"
echo "2. Test database connectivity"
echo "3. Update application connection strings"
echo "4. Verify data integrity"
echo "5. Configure automated backups"
echo "6. Delete source instance after grace period"
echo ""
