#!/bin/bash

# AWS Migration Tool Setup Script
# This script sets up AWS credentials for the migration tool

set -e

echo "=============================================="
echo "AWS Migration Tool - Credentials Setup"
echo "=============================================="
echo ""

# Create AWS credentials directory if it doesn't exist
mkdir -p ~/.aws

# Check if credentials file exists
if [ -f ~/.aws/credentials ]; then
    echo "⚠️  AWS credentials file already exists at ~/.aws/credentials"
    read -p "Do you want to append new profiles? (y/n): " APPEND
    if [ "$APPEND" != "y" ]; then
        echo "Exiting without changes."
        exit 0
    fi
fi

# Function to add profile
add_profile() {
    local profile_name=$1
    local profile_label=$2
    
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "Setting up $profile_label ($profile_name)"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    read -p "Enter AWS Access Key ID: " access_key
    read -p "Enter AWS Secret Access Key: " -s secret_key
    echo ""
    read -p "Enter AWS Region [us-east-1]: " region
    region=${region:-us-east-1}
    
    # Append to credentials file
    cat >> ~/.aws/credentials <<EOF

[$profile_name]
aws_access_key_id = $access_key
aws_secret_access_key = $secret_key
region = $region

EOF
    
    echo "✅ Profile '$profile_name' added successfully"
}

# Add source account profile
add_profile "source_acc" "Source Account"

# Add target account profile
add_profile "target_acc" "Target Account"

echo ""
echo "=============================================="
echo "✅ AWS Credentials Setup Complete!"
echo "=============================================="
echo ""
echo "📝 Profiles created:"
echo "   - source_acc (Source Account)"
echo "   - target_acc (Target Account)"
echo ""
echo "🚀 You can now run the migration tool using:"
echo "   docker-compose up"
echo ""
echo "   OR"
echo ""
echo "   docker run --rm -v ~/.aws:/root/.aws:ro -v \$(pwd)/output:/output aws-migration-tool:latest python aws_migration.py --report"
echo ""
