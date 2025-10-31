#!/bin/bash

# AWS Migration Tool - Complete Setup and Run Script
# This script sets up everything needed and runs the migration analysis

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=============================================="
echo "AWS Cross-Account Migration Tool"
echo "Setup and Execution Script"
echo -e "==============================================${NC}"
echo ""

# Function to print colored messages
print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    print_error "Docker is not installed. Please install Docker first."
    echo "Visit: https://docs.docker.com/get-docker/"
    exit 1
fi
print_success "Docker is installed"

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    print_warning "Docker Compose is not installed. Will use 'docker compose' instead."
    DOCKER_COMPOSE="docker compose"
else
    DOCKER_COMPOSE="docker-compose"
    print_success "Docker Compose is installed"
fi

# Create output directory
if [ ! -d "output" ]; then
    mkdir -p output
    print_success "Created output directory"
else
    print_info "Output directory already exists"
fi

# Check if AWS credentials are configured
if [ ! -f ~/.aws/credentials ]; then
    print_warning "AWS credentials not found"
    echo ""
    read -p "Do you want to set up AWS credentials now? (y/n): " SETUP_CREDS
    if [ "$SETUP_CREDS" = "y" ]; then
        chmod +x setup_credentials.sh
        ./setup_credentials.sh
    else
        print_error "AWS credentials are required. Exiting."
        exit 1
    fi
else
    print_success "AWS credentials file exists"
fi

# Check if profiles exist
if ! grep -q "\[source_acc\]" ~/.aws/credentials; then
    print_error "Profile 'source_acc' not found in ~/.aws/credentials"
    echo "Run ./setup_credentials.sh to create it"
    exit 1
fi

if ! grep -q "\[target_acc\]" ~/.aws/credentials; then
    print_error "Profile 'target_acc' not found in ~/.aws/credentials"
    echo "Run ./setup_credentials.sh to create it"
    exit 1
fi

print_success "AWS profiles 'source_acc' and 'target_acc' found"

echo ""
echo -e "${BLUE}=============================================="
echo "Building Docker Image"
echo -e "==============================================${NC}"

# Build Docker image
docker build -t aws-migration-tool:latest . || {
    print_error "Failed to build Docker image"
    exit 1
}
print_success "Docker image built successfully"

echo ""
echo -e "${BLUE}=============================================="
echo "Migration Analysis Options"
echo -e "==============================================${NC}"
echo ""
echo "1. Analyze ALL resources (EC2, RDS, VPC, etc.)"
echo "2. Analyze specific EC2 instances"
echo "3. Analyze specific RDS instances"
echo "4. Analyze with custom region"
echo "5. Interactive shell"
echo "6. Exit"
echo ""
read -p "Select an option (1-6): " OPTION

case $OPTION in
    1)
        echo ""
        print_info "Running complete migration analysis..."
        docker run --rm \
            -v ~/.aws:/root/.aws:ro \
            -v $(pwd)/output:/output \
            aws-migration-tool:latest \
            python aws_migration.py --report
        ;;
    2)
        echo ""
        read -p "Enter EC2 instance IDs (comma-separated): " EC2_IDS
        print_info "Analyzing EC2 instances: $EC2_IDS"
        docker run --rm \
            -v ~/.aws:/root/.aws:ro \
            -v $(pwd)/output:/output \
            aws-migration-tool:latest \
            python aws_migration.py --report --ec2-instances "$EC2_IDS"
        ;;
    3)
        echo ""
        read -p "Enter RDS instance IDs (comma-separated): " RDS_IDS
        print_info "Analyzing RDS instances: $RDS_IDS"
        docker run --rm \
            -v ~/.aws:/root/.aws:ro \
            -v $(pwd)/output:/output \
            aws-migration-tool:latest \
            python aws_migration.py --report --rds-instances "$RDS_IDS"
        ;;
    4)
        echo ""
        read -p "Enter source region [us-east-1]: " SOURCE_REGION
        SOURCE_REGION=${SOURCE_REGION:-us-east-1}
        read -p "Enter target region [us-east-1]: " TARGET_REGION
        TARGET_REGION=${TARGET_REGION:-us-east-1}
        print_info "Analyzing with source region: $SOURCE_REGION, target region: $TARGET_REGION"
        docker run --rm \
            -v ~/.aws:/root/.aws:ro \
            -v $(pwd)/output:/output \
            aws-migration-tool:latest \
            python aws_migration.py --report \
            --source-region "$SOURCE_REGION" \
            --target-region "$TARGET_REGION"
        ;;
    5)
        echo ""
        print_info "Starting interactive shell..."
        echo "Inside the container, you can run:"
        echo "  python aws_migration.py --report"
        echo "  python aws_migration.py --help"
        echo ""
        docker run --rm -it \
            -v ~/.aws:/root/.aws:ro \
            -v $(pwd)/output:/output \
            aws-migration-tool:latest \
            /bin/bash
        exit 0
        ;;
    6)
        echo "Exiting..."
        exit 0
        ;;
    *)
        print_error "Invalid option"
        exit 1
        ;;
esac

# Check if analysis was successful
if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}=============================================="
    echo "✅ Migration Analysis Complete!"
    echo -e "==============================================${NC}"
    echo ""
    print_success "Output files generated in ./output directory:"
    echo ""
    
    if [ -f "output/migration_report.json" ]; then
        echo "  📄 migration_report.json - Complete inventory"
        echo ""
        print_info "Report Summary:"
        if command -v jq &> /dev/null; then
            echo ""
            echo "  EC2 Instances: $(jq '.ec2_instances | length' output/migration_report.json)"
            echo "  RDS Instances: $(jq '.rds_instances | length' output/migration_report.json)"
            echo "  RDS Clusters: $(jq '.rds_clusters | length' output/migration_report.json)"
            echo "  VPCs: $(jq '.vpcs | length' output/migration_report.json)"
            echo "  Subnets: $(jq '.subnets | length' output/migration_report.json)"
            echo "  Security Groups: $(jq '.security_groups | length' output/migration_report.json)"
            echo "  KMS Keys: $(jq '.kms_keys | length' output/migration_report.json)"
        else
            print_warning "Install 'jq' to see detailed summary"
        fi
    fi
    
    if [ -f "output/user_data_backup.json" ]; then
        echo ""
        echo "  📄 user_data_backup.json - EC2 user data backup"
    fi
    
    if [ -f "output/generate_ssh_keys.sh" ]; then
        echo "  📄 generate_ssh_keys.sh - SSH key generation script"
    fi
    
    echo ""
    echo -e "${BLUE}=============================================="
    echo "Next Steps:"
    echo -e "==============================================${NC}"
    echo ""
    echo "1. Review the migration report:"
    echo "   cat output/migration_report.json | jq ."
    echo ""
    echo "2. Plan your maintenance window with stakeholders"
    echo ""
    echo "3. Generate new SSH keys (if needed):"
    echo "   chmod +x output/generate_ssh_keys.sh"
    echo "   ./output/generate_ssh_keys.sh"
    echo ""
    echo "4. Proceed with manual migration using AWS Console"
    echo "   Reference: migration_report.json for all configurations"
    echo ""
    echo -e "${YELLOW}⚠️  IMPORTANT:${NC}"
    echo "   - Schedule maintenance window"
    echo "   - Notify Insurance Pro and DWH teams"
    echo "   - Prepare rollback plan"
    echo "   - Zero data loss strategy: stop instances before snapshots"
    echo ""
else
    print_error "Migration analysis failed. Check the error messages above."
    exit 1
fi
