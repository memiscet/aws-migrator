#!/bin/bash

##############################################################################
# QUICK START - RDS Migration
##############################################################################

echo "======================================"
echo "🚀 AWS RDS Migration - Quick Start"
echo "======================================"
echo ""
echo "This script will migrate your RDS instance from source account to target account."
echo ""
echo "Prerequisites:"
echo "  ✓ AWS profiles configured (source_acc and target_acc)"
echo "  ✓ Docker installed"
echo "  ✓ Source RDS instance exists"
echo ""
echo "What will happen:"
echo "  1. Discover RDS instances in source account"
echo "  2. Create DB subnet group in target VPC"
echo "  3. Create security group in target VPC"
echo "  4. Run dry-run migration"
echo "  5. Execute actual migration (with confirmation)"
echo ""
echo "Target VPC: vpc-0261473d76d9c5d21 (DEV-VPC1)"
echo ""

read -p "Ready to start? (y/n): " START

if [ "$START" != "y" ]; then
    echo "Cancelled."
    exit 0
fi

echo ""
echo "Starting automated migration..."
echo ""

./automated_rds_migration.sh
