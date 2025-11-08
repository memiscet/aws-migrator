#!/usr/bin/env python3
"""
AWS Cross-Account Migration Tool
Migrates EC2 instances, RDS databases, and network infrastructure between AWS accounts
"""

import boto3
import json
from datetime import datetime
from typing import Dict, List, Any, Optional
import sys
import base64
import time
import argparse
from migration_state import MigrationStateManager, ResourceType, MigrationStatus


class AWSMigrationOrchestrator:
    def __init__(self, source_profile: str, target_profile: str, source_region: str, target_region: str, state_file: str = "migration_state.json"):
        """Initialize AWS sessions for source and target accounts"""
        print(f"🔧 Initializing AWS sessions...")
        print(f"   Source: {source_profile} ({source_region})")
        print(f"   Target: {target_profile} ({target_region})")
        
        # Initialize state manager
        self.state_manager = MigrationStateManager(state_file_path=state_file)
        
        self.source_session = boto3.Session(profile_name=source_profile, region_name=source_region)
        self.target_session = boto3.Session(profile_name=target_profile, region_name=target_region)
        
        # EC2 clients
        self.source_ec2 = self.source_session.client('ec2')
        self.target_ec2 = self.target_session.client('ec2')
        
        # RDS clients
        self.source_rds = self.source_session.client('rds')
        self.target_rds = self.target_session.client('rds')
        
        # KMS clients
        self.source_kms = self.source_session.client('kms')
        self.target_kms = self.target_session.client('kms')
        
        # IAM clients
        self.source_iam = self.source_session.client('iam')
        self.target_iam = self.target_session.client('iam')
        
        # Get account IDs
        self.source_account_id = self.source_session.client('sts').get_caller_identity()['Account']
        self.target_account_id = self.target_session.client('sts').get_caller_identity()['Account']
        
        print(f"✅ Connected to accounts:")
        print(f"   Source Account ID: {self.source_account_id}")
        print(f"   Target Account ID: {self.target_account_id}")
        
        self.migration_report = {
            'metadata': {
                'timestamp': datetime.now().isoformat(),
                'source_account': self.source_account_id,
                'target_account': self.target_account_id,
                'source_region': source_region,
                'target_region': target_region
            },
            'ec2_instances': [],
            'rds_instances': [],
            'rds_clusters': [],
            'vpcs': [],
            'subnets': [],
            'route_tables': [],
            'network_acls': [],
            'security_groups': [],
            'elastic_ips': [],
            'volumes': [],
            'amis': [],
            'snapshots': [],
            'key_pairs': [],
            'kms_keys': []
        }
    
    def setup_iam_policies(self, dry_run: bool = True):
        """
        Create required IAM policies in both source and target accounts
        
        Args:
            dry_run: If True, show what would be created without making changes
        """
        print("\n" + "=" * 100)
        if dry_run:
            print("🧪 DRY RUN: IAM Policy Setup")
        else:
            print("🚀 IAM Policy Setup")
        print("=" * 100)
        
        # Define policy documents
        policies = {
            'source': {
                'name': 'AWSMigrationToolSourcePolicy',
                'description': 'Policy for AWS Migration Tool in source account',
                'document': {
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
                                "kms:RetireGrant",
                                "kms:RevokeGrant",
                                "kms:Decrypt",
                                "kms:Encrypt",
                                "kms:DescribeKey",
                                "kms:GetKeyPolicy",
                                "kms:PutKeyPolicy",
                                "kms:CreateKey",
                                "kms:CreateAlias",
                                "kms:DeleteAlias",
                                "kms:UpdateAlias",
                                "kms:TagResource",
                                "kms:UntagResource",
                                "kms:ListResourceTags"
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
            },
            'target': {
                'name': 'AWSMigrationToolTargetPolicy',
                'description': 'Policy for AWS Migration Tool in target account',
                'document': {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Sid": "VPCFullPermissions",
                            "Effect": "Allow",
                            "Action": [
                                "ec2:CreateVpc",
                                "ec2:DeleteVpc",
                                "ec2:ModifyVpcAttribute",
                                "ec2:DescribeVpcs",
                                "ec2:DescribeVpcAttribute",
                                "ec2:CreateSubnet",
                                "ec2:DeleteSubnet",
                                "ec2:ModifySubnetAttribute",
                                "ec2:DescribeSubnets",
                                "ec2:CreateInternetGateway",
                                "ec2:DeleteInternetGateway",
                                "ec2:AttachInternetGateway",
                                "ec2:DetachInternetGateway",
                                "ec2:DescribeInternetGateways",
                                "ec2:CreateNatGateway",
                                "ec2:DeleteNatGateway",
                                "ec2:DescribeNatGateways",
                                "ec2:AllocateAddress",
                                "ec2:ReleaseAddress",
                                "ec2:AssociateAddress",
                                "ec2:DisassociateAddress",
                                "ec2:DescribeAddresses"
                            ],
                            "Resource": "*"
                        },
                        {
                            "Sid": "SecurityGroupPermissions",
                            "Effect": "Allow",
                            "Action": [
                                "ec2:CreateSecurityGroup",
                                "ec2:DeleteSecurityGroup",
                                "ec2:DescribeSecurityGroups",
                                "ec2:AuthorizeSecurityGroupIngress",
                                "ec2:AuthorizeSecurityGroupEgress",
                                "ec2:RevokeSecurityGroupIngress",
                                "ec2:RevokeSecurityGroupEgress",
                                "ec2:UpdateSecurityGroupRuleDescriptionsIngress",
                                "ec2:UpdateSecurityGroupRuleDescriptionsEgress"
                            ],
                            "Resource": "*"
                        },
                        {
                            "Sid": "RouteTablePermissions",
                            "Effect": "Allow",
                            "Action": [
                                "ec2:CreateRouteTable",
                                "ec2:DeleteRouteTable",
                                "ec2:DescribeRouteTables",
                                "ec2:CreateRoute",
                                "ec2:DeleteRoute",
                                "ec2:ReplaceRoute",
                                "ec2:AssociateRouteTable",
                                "ec2:DisassociateRouteTable",
                                "ec2:ReplaceRouteTableAssociation"
                            ],
                            "Resource": "*"
                        },
                        {
                            "Sid": "NetworkACLPermissions",
                            "Effect": "Allow",
                            "Action": [
                                "ec2:CreateNetworkAcl",
                                "ec2:DeleteNetworkAcl",
                                "ec2:DescribeNetworkAcls",
                                "ec2:CreateNetworkAclEntry",
                                "ec2:DeleteNetworkAclEntry",
                                "ec2:ReplaceNetworkAclEntry",
                                "ec2:ReplaceNetworkAclAssociation"
                            ],
                            "Resource": "*"
                        },
                        {
                            "Sid": "EC2InstancePermissions",
                            "Effect": "Allow",
                            "Action": [
                                "ec2:Describe*",
                                "ec2:RunInstances",
                                "ec2:StartInstances",
                                "ec2:StopInstances",
                                "ec2:TerminateInstances",
                                "ec2:CreateImage",
                                "ec2:CopyImage",
                                "ec2:RegisterImage",
                                "ec2:DeregisterImage",
                                "ec2:CreateSnapshot",
                                "ec2:CopySnapshot",
                                "ec2:DeleteSnapshot",
                                "ec2:CreateVolume",
                                "ec2:DeleteVolume",
                                "ec2:AttachVolume",
                                "ec2:DetachVolume",
                                "ec2:CreateTags",
                                "ec2:DeleteTags",
                                "ec2:ImportKeyPair",
                                "ec2:CreateKeyPair"
                            ],
                            "Resource": "*"
                        },
                        {
                            "Sid": "RDSPermissions",
                            "Effect": "Allow",
                            "Action": [
                                "rds:Describe*",
                                "rds:CopyDBSnapshot",
                                "rds:CopyDBClusterSnapshot",
                                "rds:RestoreDBInstanceFromDBSnapshot",
                                "rds:RestoreDBClusterFromSnapshot",
                                "rds:CreateDBInstance",
                                "rds:CreateDBCluster",
                                "rds:ModifyDBInstance",
                                "rds:ModifyDBCluster",
                                "rds:DeleteDBInstance",
                                "rds:DeleteDBCluster",
                                "rds:AddTagsToResource",
                                "rds:ListTagsForResource",
                                "rds:CreateDBSubnetGroup",
                                "rds:ModifyDBSubnetGroup"
                            ],
                            "Resource": "*"
                        },
                        {
                            "Sid": "KMSPermissions",
                            "Effect": "Allow",
                            "Action": [
                                "kms:CreateKey",
                                "kms:CreateAlias",
                                "kms:DeleteAlias",
                                "kms:UpdateAlias",
                                "kms:Describe*",
                                "kms:List*",
                                "kms:Encrypt",
                                "kms:Decrypt",
                                "kms:CreateGrant",
                                "kms:RetireGrant",
                                "kms:RevokeGrant",
                                "kms:DescribeKey",
                                "kms:GetKeyPolicy",
                                "kms:PutKeyPolicy",
                                "kms:TagResource",
                                "kms:UntagResource",
                                "kms:ListResourceTags",
                                "kms:ScheduleKeyDeletion",
                                "kms:CancelKeyDeletion",
                                "kms:EnableKey",
                                "kms:DisableKey"
                            ],
                            "Resource": "*"
                        },
                        {
                            "Sid": "IAMPassRolePermissions",
                            "Effect": "Allow",
                            "Action": [
                                "iam:PassRole",
                                "iam:GetRole"
                            ],
                            "Resource": "*",
                            "Condition": {
                                "StringEquals": {
                                    "iam:PassedToService": [
                                        "ec2.amazonaws.com",
                                        "rds.amazonaws.com"
                                    ]
                                }
                            }
                        }
                    ]
                }
            }
        }
        
        # Create policies in both accounts
        for account_type, policy_info in policies.items():
            iam_client = self.source_iam if account_type == 'source' else self.target_iam
            account_id = self.source_account_id if account_type == 'source' else self.target_account_id
            
            print(f"\n{'=' * 80}")
            print(f"📋 {account_type.upper()} Account ({account_id})")
            print(f"{'=' * 80}")
            
            if dry_run:
                print(f"\n[DRY RUN] Would create/update policy: {policy_info['name']}")
                print(f"   Description: {policy_info['description']}")
                print(f"   Permissions: {len(policy_info['document']['Statement'])} statement groups")
                for i, statement in enumerate(policy_info['document']['Statement'], 1):
                    print(f"      {i}. {statement['Sid']}: {len(statement['Action'])} actions")
            else:
                try:
                    # Check if policy exists
                    try:
                        policy_arn = f"arn:aws:iam::{account_id}:policy/{policy_info['name']}"
                        iam_client.get_policy(PolicyArn=policy_arn)
                        print(f"   ℹ️  Policy already exists: {policy_info['name']}")
                        
                        # Get current version
                        versions = iam_client.list_policy_versions(PolicyArn=policy_arn)['Versions']
                        if len(versions) >= 5:
                            # Delete oldest version if at limit
                            oldest = sorted(versions, key=lambda x: x['CreateDate'])[0]
                            if not oldest['IsDefaultVersion']:
                                iam_client.delete_policy_version(
                                    PolicyArn=policy_arn,
                                    VersionId=oldest['VersionId']
                                )
                        
                        # Create new version
                        iam_client.create_policy_version(
                            PolicyArn=policy_arn,
                            PolicyDocument=json.dumps(policy_info['document']),
                            SetAsDefault=True
                        )
                        print(f"   ✅ Updated policy with new version")
                        
                    except iam_client.exceptions.NoSuchEntityException:
                        # Create new policy
                        response = iam_client.create_policy(
                            PolicyName=policy_info['name'],
                            PolicyDocument=json.dumps(policy_info['document']),
                            Description=policy_info['description']
                        )
                        print(f"   ✅ Created policy: {policy_info['name']}")
                        print(f"      ARN: {response['Policy']['Arn']}")
                    
                except Exception as e:
                    print(f"   ❌ Error creating/updating policy: {str(e)}")
        
        print("\n" + "=" * 100)
        if dry_run:
            print("📝 Next Steps (after running without --dry-run):")
        else:
            print("📝 Next Steps:")
        print("=" * 100)
        print("\n1️⃣  Attach policies to IAM users or roles:")
        print(f"   Source Account:")
        print(f"      aws iam attach-user-policy --user-name YOUR_USER --policy-arn arn:aws:iam::{self.source_account_id}:policy/AWSMigrationToolSourcePolicy")
        print(f"   Target Account:")
        print(f"      aws iam attach-user-policy --user-name YOUR_USER --policy-arn arn:aws:iam::{self.target_account_id}:policy/AWSMigrationToolTargetPolicy")
        print("\n2️⃣  Or create new users and attach policies:")
        print(f"   aws iam create-user --user-name migration-tool-user")
        print(f"   aws iam attach-user-policy --user-name migration-tool-user --policy-arn <POLICY_ARN>")
        print(f"   aws iam create-access-key --user-name migration-tool-user")
        print("\n3️⃣  Update your AWS credentials with the new access keys")
        print("=" * 100)
    
    def generate_complete_migration_report(self, ec2_instance_ids: List[str] = None, 
                                          rds_instance_ids: List[str] = None) -> Dict:
        """Generate comprehensive migration report for all resources"""
        print("\n" + "=" * 100)
        print("AWS CROSS-ACCOUNT MIGRATION - COMPREHENSIVE ANALYSIS")
        print("=" * 100)
        print(f"Source Account: {self.source_account_id}")
        print(f"Target Account: {self.target_account_id}")
        print(f"Migration Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 100)
        
        # Analyze EC2 instances
        print("\n📊 Analyzing EC2 Instances...")
        self._analyze_ec2_instances(ec2_instance_ids)
        
        # Analyze RDS instances
        print("\n📊 Analyzing RDS Instances...")
        self._analyze_rds_instances(rds_instance_ids)
        
        # Analyze Network Infrastructure
        print("\n📊 Analyzing Network Infrastructure...")
        self._analyze_network_infrastructure()
        
        # Print comprehensive report
        self._print_comprehensive_report()
        
        return self.migration_report
    
    def _analyze_ec2_instances(self, instance_ids: List[str] = None):
        """Analyze EC2 instances and dependencies"""
        try:
            if instance_ids:
                instances = self.source_ec2.describe_instances(InstanceIds=instance_ids)
            else:
                instances = self.source_ec2.describe_instances()
            
            for reservation in instances['Reservations']:
                for instance in reservation['Instances']:
                    instance_info = self._get_instance_details(instance)
                    self.migration_report['ec2_instances'].append(instance_info)
                    
                    # Collect AMI information
                    ami_info = self._get_ami_details(instance['ImageId'])
                    if ami_info and ami_info not in self.migration_report['amis']:
                        self.migration_report['amis'].append(ami_info)
                    
                    # Collect security group information
                    for sg in instance.get('SecurityGroups', []):
                        sg_details = self._get_security_group_details(sg['GroupId'])
                        if sg_details not in self.migration_report['security_groups']:
                            self.migration_report['security_groups'].append(sg_details)
                    
                    # Collect volume information
                    for bdm in instance.get('BlockDeviceMappings', []):
                        if 'Ebs' in bdm:
                            volume_info = self._get_volume_details(bdm['Ebs']['VolumeId'])
                            volume_info['device_name'] = bdm['DeviceName']
                            volume_info['instance_id'] = instance['InstanceId']
                            if volume_info not in self.migration_report['volumes']:
                                self.migration_report['volumes'].append(volume_info)
                    
                    # Collect Elastic IP information
                    if instance.get('PublicIpAddress'):
                        eip_info = self._check_elastic_ip(instance['InstanceId'])
                        if eip_info and eip_info not in self.migration_report['elastic_ips']:
                            self.migration_report['elastic_ips'].append(eip_info)
                    
                    # Collect key pair information
                    if instance.get('KeyName'):
                        key_info = self._get_key_pair_details(instance['KeyName'])
                        if key_info not in self.migration_report['key_pairs']:
                            self.migration_report['key_pairs'].append(key_info)
        except Exception as e:
            print(f"   ⚠️  Error analyzing EC2 instances: {str(e)}")
    
    def _analyze_rds_instances(self, instance_ids: List[str] = None):
        """Analyze RDS instances"""
        try:
            if instance_ids:
                for db_id in instance_ids:
                    response = self.source_rds.describe_db_instances(DBInstanceIdentifier=db_id)
                    for db in response['DBInstances']:
                        db_info = self._get_rds_details(db)
                        self.migration_report['rds_instances'].append(db_info)
            else:
                response = self.source_rds.describe_db_instances()
                for db in response['DBInstances']:
                    db_info = self._get_rds_details(db)
                    self.migration_report['rds_instances'].append(db_info)
            
            # Analyze RDS clusters (Aurora)
            try:
                paginator = self.source_rds.get_paginator('describe_db_clusters')
                for page in paginator.paginate():
                    for db_cluster in page['DBClusters']:
                        cluster_info = self._get_rds_cluster_details(db_cluster)
                        self.migration_report['rds_clusters'].append(cluster_info)
            except:
                pass  # No clusters in account
                
        except Exception as e:
            print(f"   ⚠️  Error analyzing RDS instances: {str(e)}")
    
    def _analyze_network_infrastructure(self):
        """Analyze VPCs, subnets, route tables, NACLs"""
        try:
            # Get all VPCs
            vpcs = self.source_ec2.describe_vpcs()
            for vpc in vpcs['Vpcs']:
                vpc_info = {
                    'vpc_id': vpc['VpcId'],
                    'cidr_block': vpc['CidrBlock'],
                    'is_default': vpc['IsDefault'],
                    'tags': vpc.get('Tags', []),
                    'enable_dns_support': self.source_ec2.describe_vpc_attribute(
                        VpcId=vpc['VpcId'], Attribute='enableDnsSupport'
                    )['EnableDnsSupport']['Value'],
                    'enable_dns_hostnames': self.source_ec2.describe_vpc_attribute(
                        VpcId=vpc['VpcId'], Attribute='enableDnsHostnames'
                    )['EnableDnsHostnames']['Value']
                }
                self.migration_report['vpcs'].append(vpc_info)
            
            # Get subnets
            subnets = self.source_ec2.describe_subnets()
            for subnet in subnets['Subnets']:
                subnet_info = {
                    'subnet_id': subnet['SubnetId'],
                    'vpc_id': subnet['VpcId'],
                    'cidr_block': subnet['CidrBlock'],
                    'availability_zone': subnet['AvailabilityZone'],
                    'map_public_ip_on_launch': subnet['MapPublicIpOnLaunch'],
                    'tags': subnet.get('Tags', [])
                }
                self.migration_report['subnets'].append(subnet_info)
            
            # Get route tables
            route_tables = self.source_ec2.describe_route_tables()
            for rt in route_tables['RouteTables']:
                rt_info = {
                    'route_table_id': rt['RouteTableId'],
                    'vpc_id': rt['VpcId'],
                    'routes': rt['Routes'],
                    'associations': rt.get('Associations', []),
                    'tags': rt.get('Tags', [])
                }
                self.migration_report['route_tables'].append(rt_info)
            
            # Get Network ACLs
            nacls = self.source_ec2.describe_network_acls()
            for nacl in nacls['NetworkAcls']:
                nacl_info = {
                    'network_acl_id': nacl['NetworkAclId'],
                    'vpc_id': nacl['VpcId'],
                    'is_default': nacl['IsDefault'],
                    'entries': nacl['Entries'],
                    'associations': nacl.get('Associations', []),
                    'tags': nacl.get('Tags', [])
                }
                self.migration_report['network_acls'].append(nacl_info)
        except Exception as e:
            print(f"   ⚠️  Error analyzing network infrastructure: {str(e)}")
    
    def _get_instance_details(self, instance: Dict) -> Dict:
        """Get detailed instance information"""
        user_data = self._get_instance_user_data(instance['InstanceId'])
        
        return {
            'instance_id': instance['InstanceId'],
            'instance_type': instance['InstanceType'],
            'state': instance['State']['Name'],
            'ami_id': instance['ImageId'],
            'vpc_id': instance.get('VpcId'),
            'subnet_id': instance.get('SubnetId'),
            'private_ip': instance.get('PrivateIpAddress'),
            'public_ip': instance.get('PublicIpAddress'),
            'key_name': instance.get('KeyName'),
            'security_groups': [{'id': sg['GroupId'], 'name': sg['GroupName']} for sg in instance.get('SecurityGroups', [])],
            'user_data': user_data,
            'iam_instance_profile': instance.get('IamInstanceProfile'),
            'monitoring': instance.get('Monitoring', {}).get('State'),
            'placement': instance.get('Placement'),
            'architecture': instance.get('Architecture'),
            'root_device_type': instance.get('RootDeviceType'),
            'block_device_mappings': instance.get('BlockDeviceMappings', []),
            'tags': instance.get('Tags', []),
            'launch_time': instance.get('LaunchTime').isoformat() if instance.get('LaunchTime') else None
        }
    
    def _get_rds_details(self, db: Dict) -> Dict:
        """Get RDS instance details"""
        db_info = {
            'db_instance_identifier': db['DBInstanceIdentifier'],
            'db_instance_class': db['DBInstanceClass'],
            'engine': db['Engine'],
            'engine_version': db['EngineVersion'],
            'status': db['DBInstanceStatus'],
            'master_username': db['MasterUsername'],
            'db_name': db.get('DBName'),
            'endpoint': db.get('Endpoint'),
            'port': db.get('DbInstancePort'),
            'allocated_storage': db['AllocatedStorage'],
            'storage_type': db.get('StorageType'),
            'storage_encrypted': db.get('StorageEncrypted', False),
            'kms_key_id': db.get('KmsKeyId'),
            'kms_key_details': None,
            'vpc_security_groups': db.get('VpcSecurityGroups', []),
            'db_subnet_group': db.get('DBSubnetGroup'),
            'multi_az': db.get('MultiAZ'),
            'backup_retention_period': db.get('BackupRetentionPeriod'),
            'preferred_backup_window': db.get('PreferredBackupWindow'),
            'preferred_maintenance_window': db.get('PreferredMaintenanceWindow'),
            'auto_minor_version_upgrade': db.get('AutoMinorVersionUpgrade'),
            'publicly_accessible': db.get('PubliclyAccessible'),
            'deletion_protection': db.get('DeletionProtection', False),
            'performance_insights_enabled': db.get('PerformanceInsightsEnabled', False),
            'performance_insights_kms_key_id': db.get('PerformanceInsightsKMSKeyId'),
            'tags': db.get('TagList', [])
        }
        
        # Get KMS key details if encrypted
        if db_info['storage_encrypted'] and db_info['kms_key_id']:
            kms_details = self._get_kms_key_details(db_info['kms_key_id'])
            db_info['kms_key_details'] = kms_details
            
            if not any(k.get('key_id') == kms_details.get('key_id') for k in self.migration_report['kms_keys']):
                self.migration_report['kms_keys'].append(kms_details)
        
        return db_info
    
    def _get_rds_cluster_details(self, db_cluster: Dict) -> Dict:
        """Get RDS cluster details"""
        cluster_info = {
            'db_cluster_identifier': db_cluster['DBClusterIdentifier'],
            'engine': db_cluster['Engine'],
            'engine_version': db_cluster['EngineVersion'],
            'engine_mode': db_cluster.get('EngineMode', 'provisioned'),
            'master_username': db_cluster['MasterUsername'],
            'storage_encrypted': db_cluster.get('StorageEncrypted', False),
            'kms_key_id': db_cluster.get('KmsKeyId'),
            'kms_key_details': None,
            'db_subnet_group': db_cluster.get('DBSubnetGroup'),
            'vpc_security_groups': db_cluster.get('VpcSecurityGroups', []),
            'availability_zones': db_cluster.get('AvailabilityZones', []),
            'multi_az': db_cluster.get('MultiAZ', False),
            'backup_retention_period': db_cluster.get('BackupRetentionPeriod'),
            'deletion_protection': db_cluster.get('DeletionProtection', False),
            'tags': db_cluster.get('TagList', [])
        }
        
        # Get KMS key details if encrypted
        if cluster_info['storage_encrypted'] and cluster_info['kms_key_id']:
            kms_details = self._get_kms_key_details(cluster_info['kms_key_id'])
            cluster_info['kms_key_details'] = kms_details
            
            if not any(k.get('key_id') == kms_details.get('key_id') for k in self.migration_report['kms_keys']):
                self.migration_report['kms_keys'].append(kms_details)
        
        return cluster_info
    
    def _get_kms_key_details(self, kms_key_id: str) -> Dict:
        """Get detailed information about a KMS key"""
        try:
            key_metadata = self.source_kms.describe_key(KeyId=kms_key_id)['KeyMetadata']
            
            aliases = self.source_kms.list_aliases(KeyId=kms_key_id).get('Aliases', [])
            alias_names = [alias['AliasName'] for alias in aliases]
            
            # Check if any alias indicates this is AWS-managed
            is_aws_managed = any(alias.startswith('alias/aws/') for alias in alias_names)
            
            # Also check key manager field
            if key_metadata.get('KeyManager') == 'AWS':
                is_aws_managed = True
            
            try:
                tags = self.source_kms.list_resource_tags(KeyId=kms_key_id).get('Tags', [])
            except:
                tags = []
            
            return {
                'key_id': key_metadata['KeyId'],
                'arn': key_metadata['Arn'],
                'description': key_metadata.get('Description', ''),
                'key_state': key_metadata['KeyState'],
                'enabled': key_metadata['Enabled'],
                'aliases': alias_names,
                'tags': tags,
                'is_aws_managed': is_aws_managed,
                'needs_recreation': not is_aws_managed
            }
        except Exception as e:
            return {
                'key_id': kms_key_id,
                'error': str(e),
                'needs_recreation': True
            }
    
    def _get_ami_details(self, ami_id: str) -> Optional[Dict]:
        """Get AMI details"""
        try:
            response = self.source_ec2.describe_images(ImageIds=[ami_id])
            if response['Images']:
                ami = response['Images'][0]
                return {
                    'ami_id': ami_id,
                    'name': ami.get('Name'),
                    'description': ami.get('Description'),
                    'architecture': ami.get('Architecture'),
                    'platform': ami.get('Platform'),
                    'root_device_type': ami.get('RootDeviceType'),
                    'virtualization_type': ami.get('VirtualizationType'),
                    'block_device_mappings': ami.get('BlockDeviceMappings', []),
                    'tags': ami.get('Tags', [])
                }
        except Exception as e:
            print(f"   ⚠️  Could not retrieve AMI {ami_id}: {str(e)}")
        return None
    
    def _get_security_group_details(self, sg_id: str) -> Dict:
        """Get security group details"""
        sg = self.source_ec2.describe_security_groups(GroupIds=[sg_id])['SecurityGroups'][0]
        return {
            'group_id': sg['GroupId'],
            'group_name': sg['GroupName'],
            'description': sg['Description'],
            'vpc_id': sg.get('VpcId'),
            'ingress_rules': sg.get('IpPermissions', []),
            'egress_rules': sg.get('IpPermissionsEgress', []),
            'tags': sg.get('Tags', [])
        }
    
    def _get_volume_details(self, volume_id: str) -> Dict:
        """Get EBS volume details"""
        volume = self.source_ec2.describe_volumes(VolumeIds=[volume_id])['Volumes'][0]
        return {
            'volume_id': volume_id,
            'size': volume['Size'],
            'volume_type': volume['VolumeType'],
            'iops': volume.get('Iops'),
            'throughput': volume.get('Throughput'),
            'encrypted': volume['Encrypted'],
            'kms_key_id': volume.get('KmsKeyId'),
            'snapshot_id': volume.get('SnapshotId'),
            'availability_zone': volume['AvailabilityZone'],
            'state': volume['State'],
            'tags': volume.get('Tags', [])
        }
    
    def _get_instance_user_data(self, instance_id: str) -> Dict:
        """Retrieve user data from instance"""
        try:
            response = self.source_ec2.describe_instance_attribute(
                InstanceId=instance_id,
                Attribute='userData'
            )
            user_data = response.get('UserData', {}).get('Value')
            if user_data:
                decoded_user_data = base64.b64decode(user_data).decode('utf-8')
                return {
                    'exists': True,
                    'encoded': user_data,
                    'decoded': decoded_user_data,
                    'length': len(decoded_user_data)
                }
            else:
                return {'exists': False}
        except Exception as e:
            return {'exists': False, 'error': str(e)}
    
    def _get_key_pair_details(self, key_name: str) -> Dict:
        """Get key pair details"""
        try:
            response = self.source_ec2.describe_key_pairs(KeyNames=[key_name])
            key_pair = response['KeyPairs'][0]
            return {
                'key_name': key_pair['KeyName'],
                'key_fingerprint': key_pair['KeyFingerprint'],
                'key_pair_id': key_pair.get('KeyPairId'),
                'key_type': key_pair.get('KeyType', 'rsa'),
                'tags': key_pair.get('Tags', [])
            }
        except Exception as e:
            return {
                'key_name': key_name,
                'error': str(e)
            }
    
    def _check_elastic_ip(self, instance_id: str) -> Optional[Dict]:
        """Check if instance has an Elastic IP"""
        addresses = self.source_ec2.describe_addresses(
            Filters=[{'Name': 'instance-id', 'Values': [instance_id]}]
        )
        if addresses['Addresses']:
            addr = addresses['Addresses'][0]
            return {
                'allocation_id': addr.get('AllocationId'),
                'public_ip': addr.get('PublicIp'),
                'instance_id': instance_id,
                'tags': addr.get('Tags', [])
            }
        return None
    
    def _print_comprehensive_report(self):
        """Print comprehensive migration report"""
        print("\n" + "=" * 100)
        print("MIGRATION SUMMARY")
        print("=" * 100)
        print(f"📊 EC2 Instances: {len(self.migration_report['ec2_instances'])}")
        print(f"📊 RDS Instances: {len(self.migration_report['rds_instances'])}")
        print(f"📊 RDS Clusters: {len(self.migration_report['rds_clusters'])}")
        print(f"📊 AMIs: {len(self.migration_report['amis'])}")
        print(f"📊 VPCs: {len(self.migration_report['vpcs'])}")
        print(f"📊 Subnets: {len(self.migration_report['subnets'])}")
        print(f"📊 Security Groups: {len(self.migration_report['security_groups'])}")
        print(f"📊 Route Tables: {len(self.migration_report['route_tables'])}")
        print(f"📊 Network ACLs: {len(self.migration_report['network_acls'])}")
        print(f"📊 EBS Volumes: {len(self.migration_report['volumes'])}")
        print(f"📊 Elastic IPs: {len(self.migration_report['elastic_ips'])}")
        print(f"📊 Key Pairs: {len(self.migration_report['key_pairs'])}")
        print(f"📊 KMS Keys: {len(self.migration_report['kms_keys'])}")
        
        # EC2 Instances Details
        if self.migration_report['ec2_instances']:
            print("\n" + "=" * 100)
            print("EC2 INSTANCES")
            print("=" * 100)
            for inst in self.migration_report['ec2_instances']:
                print(f"\n🖥️  Instance: {inst['instance_id']}")
                print(f"   Name: {self._get_name_tag(inst['tags'])}")
                print(f"   Type: {inst['instance_type']}")
                print(f"   State: {inst['state']}")
                print(f"   AMI: {inst['ami_id']}")
                print(f"   VPC: {inst['vpc_id']}")
                print(f"   Subnet: {inst['subnet_id']}")
                print(f"   Private IP: {inst['private_ip']}")
                print(f"   Public IP: {inst['public_ip']}")
                print(f"   Key Pair: {inst['key_name']}")
                print(f"   User Data: {'✅ Present' if inst['user_data']['exists'] else '❌ None'}")
                print(f"   Security Groups: {', '.join([sg['name'] for sg in inst['security_groups']])}")
        
        # RDS Instances Details
        if self.migration_report['rds_instances']:
            print("\n" + "=" * 100)
            print("RDS INSTANCES")
            print("=" * 100)
            for db in self.migration_report['rds_instances']:
                print(f"\n💾 Database: {db['db_instance_identifier']}")
                print(f"   Engine: {db['engine']} {db['engine_version']}")
                print(f"   Class: {db['db_instance_class']}")
                print(f"   Status: {db['status']}")
                print(f"   Storage: {db['allocated_storage']} GB ({db['storage_type']})")
                print(f"   Encrypted: {'✅ Yes' if db['storage_encrypted'] else '❌ No'}")
                if db['storage_encrypted']:
                    print(f"   KMS Key: {db['kms_key_id']}")
                print(f"   Multi-AZ: {'✅ Yes' if db['multi_az'] else '❌ No'}")
        
        # KMS Keys
        if self.migration_report['kms_keys']:
            print("\n" + "=" * 100)
            print("KMS KEYS")
            print("=" * 100)
            for kms in self.migration_report['kms_keys']:
                print(f"\n🔐 KMS Key: {kms.get('key_id', 'Unknown')}")
                if kms.get('aliases'):
                    print(f"   Aliases: {', '.join(kms['aliases'])}")
                print(f"   Description: {kms.get('description', 'N/A')}")
                print(f"   AWS Managed: {kms.get('is_aws_managed', False)}")
        
        # Network Infrastructure
        if self.migration_report['vpcs']:
            print("\n" + "=" * 100)
            print("NETWORK INFRASTRUCTURE")
            print("=" * 100)
            for vpc in self.migration_report['vpcs']:
                print(f"\n🌐 VPC: {vpc['vpc_id']}")
                print(f"   Name: {self._get_name_tag(vpc['tags'])}")
                print(f"   CIDR: {vpc['cidr_block']}")
                print(f"   DNS Support: {'✅' if vpc['enable_dns_support'] else '❌'}")
                print(f"   DNS Hostnames: {'✅' if vpc['enable_dns_hostnames'] else '❌'}")
                
                vpc_subnets = [s for s in self.migration_report['subnets'] if s['vpc_id'] == vpc['vpc_id']]
                print(f"   Subnets: {len(vpc_subnets)}")
                for subnet in vpc_subnets:
                    print(f"      - {subnet['subnet_id']}: {subnet['cidr_block']} ({subnet['availability_zone']})")
    
    def _get_name_tag(self, tags: List[Dict]) -> str:
        """Extract Name tag from tags list"""
        for tag in tags:
            if tag['Key'] == 'Name':
                return tag['Value']
        return 'N/A'
    
    def save_migration_report(self, filename: str = '/output/migration_report.json'):
        """Save comprehensive migration report"""
        with open(filename, 'w') as f:
            json.dump(self.migration_report, f, indent=2, default=str)
        print(f"\n✅ Migration report saved to: {filename}")
        
        # Save user data separately
        userdata_file = '/output/user_data_backup.json'
        userdata_backup = {}
        for inst in self.migration_report['ec2_instances']:
            if inst['user_data']['exists']:
                userdata_backup[inst['instance_id']] = {
                    'decoded': inst['user_data']['decoded'],
                    'encoded': inst['user_data']['encoded']
                }
        
        if userdata_backup:
            with open(userdata_file, 'w') as f:
                json.dump(userdata_backup, f, indent=2)
            print(f"✅ User data backup saved to: {userdata_file}")
    
    def generate_ssh_keys_script(self, filename: str = '/output/generate_ssh_keys.sh'):
        """Generate script to create new SSH keys"""
        print("\n🔑 Generating SSH key creation script...")
        
        script_content = "#!/bin/bash\n\n"
        script_content += "# SSH Key Generation Script for Migration\n"
        script_content += f"# Generated: {datetime.now().isoformat()}\n\n"
        script_content += "set -e\n\n"
        script_content += "TARGET_PROFILE='target_acc'\n"
        script_content += f"TARGET_REGION='{self.target_session.region_name}'\n\n"
        
        for key in self.migration_report['key_pairs']:
            key_name = key['key_name']
            new_key_name = f"{key_name}-migrated"
            
            script_content += f"\necho 'Creating new key pair: {new_key_name}'\n"
            script_content += f"aws ec2 create-key-pair \\\n"
            script_content += f"  --key-name {new_key_name} \\\n"
            script_content += f"  --profile $TARGET_PROFILE \\\n"
            script_content += f"  --region $TARGET_REGION \\\n"
            script_content += f"  --query 'KeyMaterial' \\\n"
            script_content += f"  --output text > /output/{new_key_name}.pem\n\n"
            script_content += f"chmod 400 /output/{new_key_name}.pem\n"
            script_content += f"echo '✅ Created key: {new_key_name}'\n\n"
        
        with open(filename, 'w') as f:
            f.write(script_content)
        
        import os
        os.chmod(filename, 0o755)
        
        print(f"✅ SSH key generation script saved to: {filename}")
    
    def _replicate_security_groups_with_dependencies(self, security_group_ids: List[str], 
                                                     target_vpc_id: str, 
                                                     dry_run: bool = False) -> Dict[str, str]:
        """
        Replicate security groups to target VPC handling dependencies between groups.
        Returns mapping of source SG IDs to target SG IDs.
        """
        print(f"\n🔒 Replicating {len(security_group_ids)} security groups with dependencies...")
        
        sg_mapping = {}  # source_sg_id -> target_sg_id
        sg_details_map = {}  # source_sg_id -> details
        
        # Step 1: Collect all security group details
        print(f"   Step 1: Collecting security group details...")
        for sg_id in security_group_ids:
            sg_details = self._get_security_group_details(sg_id)
            
            if sg_details['group_name'] == 'default':
                # Handle default security group
                if dry_run:
                    print(f"      [DRY RUN] Would map default SG to target VPC default")
                    sg_mapping[sg_id] = 'default-sg-id'
                else:
                    try:
                        default_sg = self.target_ec2.describe_security_groups(
                            Filters=[
                                {'Name': 'vpc-id', 'Values': [target_vpc_id]},
                                {'Name': 'group-name', 'Values': ['default']}
                            ]
                        )
                        if default_sg['SecurityGroups']:
                            target_sg_id = default_sg['SecurityGroups'][0]['GroupId']
                            sg_mapping[sg_id] = target_sg_id
                            print(f"      ✅ Mapped default SG: {sg_id} -> {target_sg_id}")
                    except Exception as e:
                        print(f"      ⚠️  Could not find default security group: {str(e)}")
            else:
                sg_details_map[sg_id] = sg_details
                print(f"      📋 {sg_details['group_name']} ({sg_id})")
        
        # Step 2: Check if security groups already exist in target
        print(f"   Step 2: Checking for existing security groups in target...")
        for sg_id, sg_details in sg_details_map.items():
            migrated_name = f"{sg_details['group_name']}-migrated"
            
            if dry_run:
                print(f"      [DRY RUN] Would check for existing: {migrated_name}")
            else:
                try:
                    existing = self.target_ec2.describe_security_groups(
                        Filters=[
                            {'Name': 'vpc-id', 'Values': [target_vpc_id]},
                            {'Name': 'group-name', 'Values': [migrated_name]}
                        ]
                    )
                    if existing['SecurityGroups']:
                        target_sg_id = existing['SecurityGroups'][0]['GroupId']
                        sg_mapping[sg_id] = target_sg_id
                        print(f"      ♻️  Reusing existing: {migrated_name} ({target_sg_id})")
                except Exception as e:
                    print(f"      ⚠️  Error checking for existing SG: {str(e)}")
        
        # Step 3: Create security groups without inter-SG rules
        print(f"   Step 3: Creating security groups (without cross-SG rules)...")
        for sg_id, sg_details in sg_details_map.items():
            if sg_id in sg_mapping:
                continue  # Already exists
            
            migrated_name = f"{sg_details['group_name']}-migrated"
            
            if dry_run:
                print(f"      [DRY RUN] Would create: {migrated_name}")
                sg_mapping[sg_id] = f"dry-run-sg-{sg_id}"
            else:
                try:
                    sg_response = self.target_ec2.create_security_group(
                        GroupName=migrated_name,
                        Description=sg_details['description'] or f"Migrated from {sg_details['group_name']}",
                        VpcId=target_vpc_id
                    )
                    target_sg_id = sg_response['GroupId']
                    sg_mapping[sg_id] = target_sg_id
                    
                    # Tag the security group
                    tags = sg_details.get('tags', [])
                    tags.append({'Key': 'MigratedFrom', 'Value': sg_id})
                    tags.append({'Key': 'MigrationDate', 'Value': datetime.now().isoformat()})
                    
                    self.target_ec2.create_tags(
                        Resources=[target_sg_id],
                        Tags=tags
                    )
                    
                    print(f"      ✅ Created: {migrated_name} ({target_sg_id})")
                except Exception as e:
                    print(f"      ❌ Failed to create {migrated_name}: {str(e)}")
        
        # Step 4: Update and apply rules with mapped SG IDs
        print(f"   Step 4: Applying security group rules with dependencies...")
        for sg_id, sg_details in sg_details_map.items():
            if sg_id not in sg_mapping:
                continue
            
            target_sg_id = sg_mapping[sg_id]
            
            # Process ingress rules
            if sg_details.get('ingress_rules'):
                updated_ingress = self._update_sg_rule_references(
                    sg_details['ingress_rules'], 
                    sg_mapping
                )
                
                if dry_run:
                    print(f"      [DRY RUN] Would apply {len(updated_ingress)} ingress rules to {sg_details['group_name']}")
                    for rule in updated_ingress:
                        protocol = rule.get('IpProtocol', 'all')
                        from_port = rule.get('FromPort', 'all')
                        to_port = rule.get('ToPort', 'all')
                        cidrs = [r.get('CidrIp') for r in rule.get('IpRanges', [])]
                        sg_refs = [p.get('GroupId') for p in rule.get('UserIdGroupPairs', [])]
                        sources = ', '.join(cidrs + sg_refs) if (cidrs + sg_refs) else 'all'
                        print(f"         • Protocol: {protocol}, Ports: {from_port}-{to_port}, Sources: {sources}")
                else:
                    try:
                        if updated_ingress:
                            self.target_ec2.authorize_security_group_ingress(
                                GroupId=target_sg_id,
                                IpPermissions=updated_ingress
                            )
                            print(f"      ✅ Applied {len(updated_ingress)} ingress rules to {sg_details['group_name']}")
                            for rule in updated_ingress:
                                protocol = rule.get('IpProtocol', 'all')
                                from_port = rule.get('FromPort', 'all')
                                to_port = rule.get('ToPort', 'all')
                                cidrs = [r.get('CidrIp') for r in rule.get('IpRanges', [])]
                                sg_refs = [p.get('GroupId') for p in rule.get('UserIdGroupPairs', [])]
                                sources = ', '.join(cidrs + sg_refs) if (cidrs + sg_refs) else 'all'
                                print(f"         • Protocol: {protocol}, Ports: {from_port}-{to_port}, Sources: {sources}")
                    except Exception as e:
                        # Rules might already exist
                        if 'already exists' not in str(e).lower():
                            print(f"      ⚠️  Ingress rules error for {sg_details['group_name']}: {str(e)}")
            
            # Process egress rules (usually needs updating for non-default SGs)
            if sg_details.get('egress_rules'):
                updated_egress = self._update_sg_rule_references(
                    sg_details['egress_rules'], 
                    sg_mapping
                )
                
                if dry_run:
                    print(f"      [DRY RUN] Would apply {len(updated_egress)} egress rules to {sg_details['group_name']}")
                    for rule in updated_egress:
                        protocol = rule.get('IpProtocol', 'all')
                        from_port = rule.get('FromPort', 'all')
                        to_port = rule.get('ToPort', 'all')
                        cidrs = [r.get('CidrIp') for r in rule.get('IpRanges', [])]
                        sg_refs = [p.get('GroupId') for p in rule.get('UserIdGroupPairs', [])]
                        destinations = ', '.join(cidrs + sg_refs) if (cidrs + sg_refs) else 'all'
                        print(f"         • Protocol: {protocol}, Ports: {from_port}-{to_port}, Destinations: {destinations}")
                else:
                    try:
                        # Remove default egress rule first if it exists
                        self.target_ec2.revoke_security_group_egress(
                            GroupId=target_sg_id,
                            IpPermissions=[{
                                'IpProtocol': '-1',
                                'IpRanges': [{'CidrIp': '0.0.0.0/0'}]
                            }]
                        )
                    except:
                        pass  # Default rule might not exist
                    
                    try:
                        if updated_egress:
                            self.target_ec2.authorize_security_group_egress(
                                GroupId=target_sg_id,
                                IpPermissions=updated_egress
                            )
                            print(f"      ✅ Applied {len(updated_egress)} egress rules to {sg_details['group_name']}")
                            for rule in updated_egress:
                                protocol = rule.get('IpProtocol', 'all')
                                from_port = rule.get('FromPort', 'all')
                                to_port = rule.get('ToPort', 'all')
                                cidrs = [r.get('CidrIp') for r in rule.get('IpRanges', [])]
                                sg_refs = [p.get('GroupId') for p in rule.get('UserIdGroupPairs', [])]
                                destinations = ', '.join(cidrs + sg_refs) if (cidrs + sg_refs) else 'all'
                                print(f"         • Protocol: {protocol}, Ports: {from_port}-{to_port}, Destinations: {destinations}")
                    except Exception as e:
                        if 'already exists' not in str(e).lower():
                            print(f"      ⚠️  Egress rules error for {sg_details['group_name']}: {str(e)}")
        
        print(f"   ✅ Security group replication complete!")
        return sg_mapping
    
    def _update_sg_rule_references(self, rules: List[Dict], sg_mapping: Dict[str, str]) -> List[Dict]:
        """
        Update security group rules to replace source SG IDs with target SG IDs.
        """
        updated_rules = []
        
        for rule in rules:
            updated_rule = rule.copy()
            
            # Update UserIdGroupPairs (references to other security groups)
            if 'UserIdGroupPairs' in rule and rule['UserIdGroupPairs']:
                updated_pairs = []
                for pair in rule['UserIdGroupPairs']:
                    source_sg_id = pair.get('GroupId')
                    
                    if source_sg_id in sg_mapping:
                        # Replace with target SG ID
                        updated_pair = pair.copy()
                        updated_pair['GroupId'] = sg_mapping[source_sg_id]
                        # Remove UserId to use current account
                        if 'UserId' in updated_pair:
                            del updated_pair['UserId']
                        updated_pairs.append(updated_pair)
                    else:
                        # Keep original if not in mapping (might be external reference)
                        print(f"         ⚠️  Warning: SG reference {source_sg_id} not in mapping, keeping as-is")
                        updated_pairs.append(pair)
                
                updated_rule['UserIdGroupPairs'] = updated_pairs
            
            updated_rules.append(updated_rule)
        
        return updated_rules
    
    def migrate_single_ec2_instance(self, instance_id: str, target_vpc_id: str, 
                                   target_subnet_id: str, target_security_groups: List[str],
                                   dry_run: bool = True, target_key_pair: str = None):
        """Migrate a single EC2 instance with state management"""
        print("\n" + "=" * 100)
        if dry_run:
            print(f"🧪 DRY RUN: EC2 Instance Migration - {instance_id}")
        else:
            print(f"🚀 MIGRATING EC2 Instance - {instance_id}")
        print("=" * 100)
        
        # Initialize state management
        migration_id = f"ec2-{instance_id}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        if not dry_run:
            # Check for existing incomplete migration
            existing_migrations = self.state_manager.get_incomplete_migrations(
                resource_type=ResourceType.EC2_INSTANCE,
                source_id=instance_id
            )
            if existing_migrations:
                print(f"\n♻️  Found existing migration state for {instance_id}")
                print(f"   Migration ID: {existing_migrations[0]}")
                print(f"   Attempting to resume from previous state...")
                migration_id = existing_migrations[0]
            else:
                # Initialize new migration
                migration_id = self.state_manager.initialize_migration(
                    resource_type=ResourceType.EC2_INSTANCE,
                    source_id=instance_id,
                    source_metadata={
                        'target_vpc': target_vpc_id,
                        'target_subnet': target_subnet_id,
                        'target_security_groups': target_security_groups
                    }
                )
        
        # Step 1: Analyze the instance
        if not dry_run and self.state_manager.is_step_completed(migration_id, 'analyze_instance'):
            print(f"\n📊 Step 1: Analyzing instance {instance_id}...")
            print(f"   ♻️  Step already completed, loading from state...")
            instance_info = self.state_manager.get_step_data(migration_id, 'analyze_instance')
        else:
            print(f"\n📊 Step 1: Analyzing instance {instance_id}...")
            if not dry_run:
                self.state_manager.update_step_status(migration_id, 'analyze_instance', 
                                                     MigrationStatus.IN_PROGRESS)
            try:
                response = self.source_ec2.describe_instances(InstanceIds=[instance_id])
                instance = response['Reservations'][0]['Instances'][0]
                instance_info = self._get_instance_details(instance)
                
                if not dry_run:
                    self.state_manager.update_step_status(migration_id, 'analyze_instance',
                                                         MigrationStatus.COMPLETED,
                                                         data=instance_info)
            except Exception as e:
                print(f"❌ Error: Instance {instance_id} not found or cannot be accessed")
                print(f"   {str(e)}")
                if not dry_run:
                    self.state_manager.update_step_status(migration_id, 'analyze_instance',
                                                         MigrationStatus.FAILED, error=str(e))
                return
        
        print(f"✅ Instance found:")
        print(f"   Type: {instance_info['instance_type']}")
        print(f"   State: {instance_info['state']}")
        print(f"   AMI: {instance_info['ami_id']}")
        print(f"   Key Pair: {instance_info['key_name']}")
        print(f"   User Data: {'Yes' if instance_info['user_data']['exists'] else 'No'}")
        
        # Step 2: Create custom AMI (with reuse detection)
        source_custom_ami_id = None
        target_ami_id = None
        
        if not dry_run and self.state_manager.is_step_completed(migration_id, 'create_ami'):
            print(f"\n📦 Step 2: Creating custom AMI from instance...")
            print(f"   ♻️  AMI already created, reusing from state...")
            step_data = self.state_manager.get_step_data(migration_id, 'create_ami')
            source_custom_ami_id = step_data.get('source_ami_id')
            print(f"   ✅ Reusing AMI: {source_custom_ami_id}")
            
            # Verify AMI still exists
            try:
                self.source_ec2.describe_images(ImageIds=[source_custom_ami_id])
                print(f"   ✅ AMI verified in source account")
            except Exception as e:
                print(f"   ⚠️  Warning: Stored AMI not found, will create new one")
                print(f"      Error: {str(e)}")
                source_custom_ami_id = None
                self.state_manager.update_step_status(migration_id, 'create_ami',
                                                     MigrationStatus.NOT_STARTED)
        
        if source_custom_ami_id is None:
            print(f"\n📦 Step 2: Creating custom AMI from instance...")
            
            if dry_run:
                print(f"   [DRY RUN] Would create custom AMI from instance {instance_id}")
                print(f"   [DRY RUN] Would check AMI for encrypted snapshots")
                print(f"   [DRY RUN] Would grant KMS access if needed")
            else:
                if not dry_run:
                    self.state_manager.update_step_status(migration_id, 'create_ami',
                                                         MigrationStatus.IN_PROGRESS)
                try:
                    print(f"   ℹ️  Creating AMI snapshot of instance {instance_id}")
                    print(f"   ℹ️  This captures all volumes, applications, and data")
                    
                    ami_name = f"migration-{instance_id}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
                    create_image_response = self.source_ec2.create_image(
                        InstanceId=instance_id,
                        Name=ami_name,
                        Description=f"Migration snapshot of {instance_id}",
                        NoReboot=True  # Don't reboot the instance
                    )
                    source_custom_ami_id = create_image_response['ImageId']
                    print(f"   ✅ Custom AMI created: {source_custom_ami_id}")
                    
                    # Store AMI ID immediately
                    self.state_manager.add_created_resource(
                        migration_id=migration_id,
                        resource_type=ResourceType.AMI,
                        resource_id=source_custom_ami_id,
                        resource_metadata={'account': 'source', 'instance_id': instance_id}
                    )
                    
                    print(f"   ⏳ Waiting for AMI to become available...")
                    
                    # Wait for AMI to be available with extended timeout
                    waiter = self.source_ec2.get_waiter('image_available')
                    waiter_config = {
                        'Delay': 15,  # Check every 15 seconds
                        'MaxAttempts': 80  # Try for 20 minutes (15s * 80 = 1200s)
                    }
                    waiter.wait(ImageIds=[source_custom_ami_id], WaiterConfig=waiter_config)
                    print(f"   ✅ Custom AMI is ready")
                    
                    # Mark step as completed
                    self.state_manager.update_step_status(
                        migration_id, 'create_ami',
                        MigrationStatus.COMPLETED,
                        data={'source_ami_id': source_custom_ami_id, 'ami_name': ami_name}
                    )
                    
                except Exception as e:
                    print(f"   ❌ Error creating custom AMI: {str(e)}")
                    if not dry_run:
                        self.state_manager.update_step_status(migration_id, 'create_ami',
                                                             MigrationStatus.FAILED, error=str(e))
                    return
        
        # Step 3: Grant snapshot permissions (with state tracking)
        if not dry_run and self.state_manager.is_step_completed(migration_id, 'grant_snapshot_permissions'):
            print(f"\n🔑 Step 3: Granting snapshot permissions...")
            print(f"   ♻️  Snapshot permissions already granted")
        elif not dry_run:
            print(f"\n🔑 Step 3: Granting snapshot permissions to target account...")
            self.state_manager.update_step_status(migration_id, 'grant_snapshot_permissions',
                                                 MigrationStatus.IN_PROGRESS)
            try:
                ami_details = self.source_ec2.describe_images(ImageIds=[source_custom_ami_id])['Images'][0]
                for bdm in ami_details.get('BlockDeviceMappings', []):
                    if 'Ebs' in bdm and 'SnapshotId' in bdm['Ebs']:
                        snapshot_id = bdm['Ebs']['SnapshotId']
                        try:
                            self.source_ec2.modify_snapshot_attribute(
                                SnapshotId=snapshot_id,
                                Attribute='createVolumePermission',
                                OperationType='add',
                                UserIds=[self.target_account_id]
                            )
                            print(f"   ✅ Granted access to snapshot {snapshot_id}")
                        except Exception as e:
                            print(f"   ⚠️  Warning: Could not grant snapshot access: {str(e)}")
                
                self.state_manager.update_step_status(migration_id, 'grant_snapshot_permissions',
                                                     MigrationStatus.COMPLETED)
            except Exception as e:
                print(f"   ❌ Error granting snapshot permissions: {str(e)}")
                self.state_manager.update_step_status(migration_id, 'grant_snapshot_permissions',
                                                     MigrationStatus.FAILED, error=str(e))
                return
        
        # Step 4: Share AMI (with state tracking)
        if not dry_run and self.state_manager.is_step_completed(migration_id, 'share_ami'):
            print(f"\n🔗 Step 4: Sharing AMI with target account...")
            print(f"   ♻️  AMI already shared")
        elif not dry_run:
            print(f"\n🔗 Step 4: Sharing AMI with target account...")
            self.state_manager.update_step_status(migration_id, 'share_ami',
                                                 MigrationStatus.IN_PROGRESS)
            try:
                self.source_ec2.modify_image_attribute(
                    ImageId=source_custom_ami_id,
                    LaunchPermission={'Add': [{'UserId': self.target_account_id}]}
                )
                print(f"   ✅ AMI shared with target account")
                self.state_manager.update_step_status(migration_id, 'share_ami',
                                                     MigrationStatus.COMPLETED)
            except Exception as e:
                print(f"   ❌ Error sharing AMI: {str(e)}")
                self.state_manager.update_step_status(migration_id, 'share_ami',
                                                     MigrationStatus.FAILED, error=str(e))
                return
        
        # Step 5: Copy AMI to target (with state tracking and reuse)
        if not dry_run and self.state_manager.is_step_completed(migration_id, 'copy_ami'):
            print(f"\n📋 Step 5: Copying AMI to target account...")
            print(f"   ♻️  AMI already copied, reusing from state...")
            step_data = self.state_manager.get_step_data(migration_id, 'copy_ami')
            target_ami_id = step_data.get('target_ami_id')
            print(f"   ✅ Reusing target AMI: {target_ami_id}")
            
            # Verify target AMI still exists
            try:
                self.target_ec2.describe_images(ImageIds=[target_ami_id])
                print(f"   ✅ Target AMI verified")
            except Exception as e:
                print(f"   ⚠️  Warning: Stored target AMI not found, will copy again")
                print(f"      Error: {str(e)}")
                target_ami_id = None
                self.state_manager.update_step_status(migration_id, 'copy_ami',
                                                     MigrationStatus.NOT_STARTED)
        
        if target_ami_id is None and not dry_run:
            print(f"\n📋 Step 5: Copying AMI to target account...")
            self.state_manager.update_step_status(migration_id, 'copy_ami',
                                                 MigrationStatus.IN_PROGRESS)
            try:
                target_ami_name = f"migrated-{instance_id}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
                copy_response = self.target_ec2.copy_image(
                    SourceImageId=source_custom_ami_id,
                    SourceRegion=self.source_session.region_name,
                    Name=target_ami_name,
                    Description=f"Migrated from instance {instance_id}"
                )
                target_ami_id = copy_response['ImageId']
                print(f"   ✅ AMI copied to target: {target_ami_id}")
                
                # Store target AMI ID immediately
                self.state_manager.add_created_resource(
                    migration_id=migration_id,
                    resource_type=ResourceType.AMI,
                    resource_id=target_ami_id,
                    resource_metadata={'account': 'target', 'source_ami': source_custom_ami_id}
                )
                
                print(f"   ⏳ Waiting for target AMI to become available...")
                
                # Wait for target AMI to be available with extended timeout
                target_waiter = self.target_ec2.get_waiter('image_available')
                target_waiter_config = {
                    'Delay': 15,  # Check every 15 seconds
                    'MaxAttempts': 80  # Try for 20 minutes (15s * 80 = 1200s)
                }
                target_waiter.wait(ImageIds=[target_ami_id], WaiterConfig=target_waiter_config)
                print(f"   ✅ Target AMI is ready")
                
                self.state_manager.update_step_status(migration_id, 'copy_ami',
                                                     MigrationStatus.COMPLETED,
                                                     data={'target_ami_id': target_ami_id, 
                                                          'target_ami_name': target_ami_name})
            except Exception as e:
                print(f"   ❌ Error copying AMI to target: {str(e)}")
                self.state_manager.update_step_status(migration_id, 'copy_ami',
                                                     MigrationStatus.FAILED, error=str(e))
                return
        
        if dry_run:
            print(f"\n[DRY RUN] Steps 2-5: Would create, share, and copy AMI")
            print(f"   Would create custom AMI from instance {instance_id}")
            print(f"   Would grant snapshot permissions to target account")
            print(f"   Would share AMI with target account")
            print(f"   Would copy AMI to target account")
        
        # Step 3: Volume snapshots are included in the AMI
        print(f"\n� Step 3: Volume snapshots included in custom AMI")
        print(f"   ℹ️  All volumes and data are captured in the AMI created above")
        print(f"   ✅ No separate volume snapshots needed")
        
        # Step 4: Handle security groups with dependencies
        print(f"\n🔒 Step 4: Handling security groups with dependencies...")
        target_sg_ids = target_security_groups if target_security_groups else []
        
        if not target_sg_ids:
            print(f"   No target security groups specified - replicating from source...")
            
            # Collect all security group IDs from the instance
            source_sg_ids = [sg['id'] for sg in instance_info['security_groups']]
            
            # Replicate security groups handling dependencies
            sg_mapping = self._replicate_security_groups_with_dependencies(
                source_sg_ids,
                target_vpc_id,
                dry_run
            )
            
            # Get target security group IDs
            target_sg_ids = [sg_mapping[sg_id] for sg_id in source_sg_ids if sg_id in sg_mapping]
            
            if not dry_run and target_sg_ids:
                print(f"   ✅ Mapped {len(target_sg_ids)} security groups to target VPC")
        else:
            print(f"   Using specified security groups: {', '.join(target_sg_ids)}")
        
        # Step 5: Launch instance
        print(f"\n🖥️  Step 5: Launching instance in target account...")
        
        if dry_run:
            print(f"   [DRY RUN] Would launch instance with:")
            print(f"      AMI: {source_custom_ami_id if source_custom_ami_id else 'custom-ami'} (will be copied)")
            print(f"      Type: {instance_info['instance_type']}")
            print(f"      VPC: {target_vpc_id}")
            print(f"      Subnet: {target_subnet_id}")
            print(f"      Security Groups: {target_sg_ids if target_sg_ids else 'default'}")
            key_to_use = target_key_pair if target_key_pair else instance_info['key_name']
            print(f"      Key Pair: {key_to_use} (must exist in target)")
            if instance_info['user_data']['exists']:
                print(f"      User Data: Yes ({instance_info['user_data']['length']} bytes)")
        else:
            try:
                # Filter out AWS-reserved tags (tags starting with 'aws:')
                user_tags = [tag for tag in instance_info['tags'] if not tag['Key'].startswith('aws:')]
                
                launch_params = {
                    'ImageId': target_ami_id,
                    'InstanceType': instance_info['instance_type'],
                    'SubnetId': target_subnet_id,
                    'MinCount': 1,
                    'MaxCount': 1,
                    'TagSpecifications': [{
                        'ResourceType': 'instance',
                        'Tags': user_tags + [
                            {'Key': 'MigratedFrom', 'Value': instance_id},
                            {'Key': 'MigrationDate', 'Value': datetime.now().isoformat()}
                        ]
                    }]
                }
                
                if target_sg_ids:
                    launch_params['SecurityGroupIds'] = target_sg_ids
                
                # Use target_key_pair if specified, otherwise use source key
                if target_key_pair:
                    launch_params['KeyName'] = target_key_pair
                elif instance_info['key_name']:
                    launch_params['KeyName'] = instance_info['key_name']
                
                if instance_info['user_data']['exists']:
                    launch_params['UserData'] = instance_info['user_data']['decoded']
                
                if instance_info['monitoring'] == 'enabled':
                    launch_params['Monitoring'] = {'Enabled': True}
                
                response = self.target_ec2.run_instances(**launch_params)
                new_instance_id = response['Instances'][0]['InstanceId']
                
                print(f"   ✅ Instance launched: {new_instance_id}")
                print(f"   ⏳ Waiting for instance to be running...")
                
                waiter = self.target_ec2.get_waiter('instance_running')
                waiter.wait(InstanceIds=[new_instance_id])
                
                print(f"   ✅ Instance is running!")
                
                # Get instance details
                new_instance = self.target_ec2.describe_instances(InstanceIds=[new_instance_id])
                new_private_ip = new_instance['Reservations'][0]['Instances'][0].get('PrivateIpAddress')
                print(f"   Private IP: {new_private_ip}")
                
            except Exception as e:
                print(f"   ❌ Error launching instance: {str(e)}")
                return
        
        # Step 6: Handle Elastic IP
        if instance_info['public_ip']:
            eip_info = self._check_elastic_ip(instance_id)
            if eip_info:
                print(f"\n🌐 Step 6: Allocating Elastic IP...")
                if dry_run:
                    print(f"   [DRY RUN] Would allocate new Elastic IP")
                    print(f"   [DRY RUN] Would associate with new instance")
                else:
                    try:
                        eip_response = self.target_ec2.allocate_address(Domain='vpc')
                        new_eip = eip_response['PublicIp']
                        allocation_id = eip_response['AllocationId']
                        
                        self.target_ec2.associate_address(
                            InstanceId=new_instance_id,
                            AllocationId=allocation_id
                        )
                        
                        print(f"   ✅ Elastic IP allocated: {new_eip}")
                    except Exception as e:
                        print(f"   ⚠️  Could not allocate Elastic IP: {str(e)}")
        
        # Summary
        print("\n" + "=" * 100)
        if dry_run:
            print("✅ DRY RUN COMPLETE")
            print("=" * 100)
            print("\n📝 Summary of what WOULD be done:")
            print(f"   1. Share and copy AMI {source_custom_ami_id}")
            print(f"   2. Create snapshots for {len(instance_info['block_device_mappings'])} volumes")
            print(f"   3. Create/map {len(instance_info['security_groups'])} security groups")
            print(f"   4. Launch new instance in {target_subnet_id}")
            if instance_info['public_ip']:
                print(f"   5. Allocate and associate Elastic IP")
            print("\n🚀 To execute the migration, run without --dry-run flag")
        else:
            print("✅ MIGRATION COMPLETE")
            print("=" * 100)
            print(f"\n📋 Migration Summary:")
            print(f"   Source Instance: {instance_id}")
            print(f"   New Instance: {new_instance_id}")
            print(f"   Private IP: {new_private_ip}")
            if 'new_eip' in locals():
                print(f"   Elastic IP: {new_eip}")
            print(f"\n📝 Next Steps:")
            print(f"   1. Verify instance is working correctly")
            print(f"   2. Test application functionality")
            print(f"   3. Update DNS/connection strings")
            print(f"   4. Stop/terminate source instance after verification")
        print("=" * 100)
    
    def migrate_single_rds_instance(self, db_instance_id: str, target_subnet_group: str,
                                   target_security_groups: List[str], target_kms_key: Optional[str] = None,
                                   dry_run: bool = True):
        """Migrate a single RDS instance"""
        print("\n" + "=" * 100)
        if dry_run:
            print(f"🧪 DRY RUN: RDS Instance Migration - {db_instance_id}")
        else:
            print(f"🚀 MIGRATING RDS Instance - {db_instance_id}")
        print("=" * 100)
        
        # Step 1: Analyze the RDS instance
        print(f"\n📊 Step 1: Analyzing RDS instance {db_instance_id}...")
        try:
            response = self.source_rds.describe_db_instances(DBInstanceIdentifier=db_instance_id)
            db_instance = response['DBInstances'][0]
            db_info = self._get_rds_details(db_instance)
        except Exception as e:
            print(f"❌ Error: RDS instance {db_instance_id} not found or cannot be accessed")
            print(f"   {str(e)}")
            return
        
        print(f"✅ RDS instance found:")
        print(f"   Engine: {db_info['engine']} {db_info['engine_version']}")
        print(f"   Class: {db_info['db_instance_class']}")
        print(f"   Storage: {db_info['allocated_storage']} GB ({db_info['storage_type']})")
        print(f"   Encrypted: {'Yes' if db_info['storage_encrypted'] else 'No'}")
        if db_info['storage_encrypted']:
            print(f"   KMS Key: {db_info['kms_key_id']}")
        print(f"   Multi-AZ: {'Yes' if db_info['multi_az'] else 'No'}")
        
        # Step 2: Handle KMS key if encrypted
        if db_info['storage_encrypted']:
            print(f"\n🔐 Step 2: Handling KMS encryption...")
            
            # Check if source uses AWS-managed key
            is_aws_managed = db_info.get('kms_key_details', {}).get('is_aws_managed', False)
            
            if target_kms_key:
                print(f"   Using specified KMS key: {target_kms_key}")
            elif is_aws_managed:
                # For AWS-managed keys, use AWS-managed key in target too
                target_kms_key = 'alias/aws/rds'
                print(f"   Source uses AWS-managed RDS key")
                print(f"   Using AWS-managed RDS key in target: {target_kms_key}")
            else:
                if dry_run:
                    print(f"   [DRY RUN] Would create KMS key in target account")
                    print(f"   [DRY RUN] Key alias: alias/rds-migration")
                else:
                    # Create KMS key in target account
                    print(f"   Creating KMS key in target account...")
                    try:
                        # Check if key already exists
                        try:
                            existing_key = self.target_kms.describe_key(KeyId='alias/rds-migration')
                            target_kms_key = existing_key['KeyMetadata']['KeyId']
                            print(f"   ℹ️  Using existing KMS key: {target_kms_key}")
                        except:
                            # Create new KMS key
                            key_response = self.target_kms.create_key(
                                Description='KMS key for migrated RDS databases',
                                KeyUsage='ENCRYPT_DECRYPT',
                                Origin='AWS_KMS',
                                MultiRegion=False
                            )
                            target_kms_key = key_response['KeyMetadata']['KeyId']
                            print(f"   ✅ Created KMS key: {target_kms_key}")
                            
                            # Create alias
                            try:
                                self.target_kms.create_alias(
                                    AliasName='alias/rds-migration',
                                    TargetKeyId=target_kms_key
                                )
                                print(f"   ✅ Created alias: alias/rds-migration")
                            except Exception as e:
                                print(f"   ⚠️  Could not create alias: {str(e)}")
                    except Exception as e:
                        print(f"   ⚠️  Error creating KMS key: {str(e)}")
                        print(f"   Falling back to AWS-managed RDS key")
                        target_kms_key = 'alias/aws/rds'
            
            # Grant KMS key access to target account for snapshot copying
            # Skip this for AWS-managed keys as they don't allow direct grants
            source_kms_key_id = db_info.get('kms_key_id')
            is_aws_managed = db_info.get('kms_key_details', {}).get('is_aws_managed', False)
            
            if source_kms_key_id and not is_aws_managed:
                print(f"\n🔑 Step 2b: Granting KMS key access to target account...")
                
                if dry_run:
                    print(f"   [DRY RUN] Would create KMS grant for target account {self.target_account_id}")
                    print(f"   [DRY RUN] Would update KMS key policy to allow target account access")
                    print(f"   [DRY RUN] This allows target account to decrypt the snapshot")
                else:
                    try:
                        # Create a grant that allows the target account to use the key
                        grant_response = self.source_kms.create_grant(
                            KeyId=source_kms_key_id,
                            GranteePrincipal=f"arn:aws:iam::{self.target_account_id}:root",
                            Operations=[
                                'Decrypt',
                                'DescribeKey',
                                'CreateGrant',
                                'RetireGrant'
                            ]
                        )
                        print(f"   ✅ KMS grant created: {grant_response['GrantId']}")
                        print(f"   ℹ️  Target account can now decrypt snapshots encrypted with this key")
                    except Exception as e:
                        print(f"   ⚠️  Warning: Could not create KMS grant: {str(e)}")
                        print(f"   ℹ️  Attempting to update key policy instead...")
                        
                        # Try to update key policy as fallback
                        try:
                            # Get current key policy
                            policy_response = self.source_kms.get_key_policy(
                                KeyId=source_kms_key_id,
                                PolicyName='default'
                            )
                            policy = json.loads(policy_response['Policy'])
                            
                            # Add statement for target account if not exists
                            target_statement = {
                                "Sid": f"Allow-Target-Account-{self.target_account_id}",
                                "Effect": "Allow",
                                "Principal": {
                                    "AWS": f"arn:aws:iam::{self.target_account_id}:root"
                                },
                                "Action": [
                                    "kms:Decrypt",
                                    "kms:DescribeKey",
                                    "kms:CreateGrant"
                                ],
                                "Resource": "*"
                            }
                            
                            # Check if statement already exists
                            statement_exists = False
                            for stmt in policy.get('Statement', []):
                                if stmt.get('Sid') == target_statement['Sid']:
                                    statement_exists = True
                                    break
                            
                            if not statement_exists:
                                policy['Statement'].append(target_statement)
                                
                                # Update the key policy
                                self.source_kms.put_key_policy(
                                    KeyId=source_kms_key_id,
                                    PolicyName='default',
                                    Policy=json.dumps(policy)
                                )
                                print(f"   ✅ KMS key policy updated to allow target account access")
                            else:
                                print(f"   ℹ️  Target account already has access in key policy")
                        
                        except Exception as e:
                            print(f"   ⚠️  Warning: Could not update key policy: {str(e)}")
                            print(f"   ℹ️  The grant should still work, but you may need to update the key policy manually")
                        
                        print(f"   ℹ️  Target account can now decrypt snapshots encrypted with this key")
                    except Exception as e:
                        print(f"   ⚠️  Warning: Could not create KMS grant: {str(e)}")
                        print(f"   ℹ️  You may need to manually grant access or update key policy")
                        print(f"   ℹ️  Without KMS access, snapshot copy will fail")
        
        # Step 3: Create snapshot
        print(f"\n💾 Step 3: Creating RDS snapshot...")
        snapshot_id = f"{db_instance_id}-migration-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        
        if dry_run:
            print(f"   [DRY RUN] Would create snapshot: {snapshot_id}")
            print(f"   [DRY RUN] Would wait for snapshot to complete")
        else:
            try:
                print(f"   Creating snapshot: {snapshot_id}")
                self.source_rds.create_db_snapshot(
                    DBSnapshotIdentifier=snapshot_id,
                    DBInstanceIdentifier=db_instance_id,
                    Tags=[
                        {'Key': 'MigrationSnapshot', 'Value': 'true'},
                        {'Key': 'SourceDB', 'Value': db_instance_id}
                    ]
                )
                
                print(f"   ⏳ Waiting for snapshot to complete (this may take several minutes)...")
                waiter = self.source_rds.get_waiter('db_snapshot_completed')
                waiter.wait(DBSnapshotIdentifier=snapshot_id)
                
                print(f"   ✅ Snapshot completed: {snapshot_id}")
            except Exception as e:
                print(f"   ❌ Error creating snapshot: {str(e)}")
                return
        
        # Step 3b: If source uses AWS-managed key, copy snapshot with customer-managed key in source account
        is_aws_managed = db_info.get('kms_key_details', {}).get('is_aws_managed', False)
        if db_info['storage_encrypted'] and is_aws_managed:
            print(f"\n🔄 Step 3b: Re-encrypting snapshot with customer-managed key in source account...")
            print(f"   (AWS-managed keys cannot be used for cross-account sharing)")
            
            # Create a customer-managed key in source account for sharing
            source_share_snapshot_id = f"{snapshot_id}-share"
            
            if dry_run:
                print(f"   [DRY RUN] Would copy snapshot with customer-managed key")
                print(f"   [DRY RUN] Share snapshot: {source_share_snapshot_id}")
            else:
                try:
                    # Check if we already have a migration key in source account
                    try:
                        source_key = self.source_kms.describe_key(KeyId='alias/rds-migration-source')
                        source_migration_key = source_key['KeyMetadata']['KeyId']
                        print(f"   ℹ️  Using existing source migration key: {source_migration_key}")
                    except:
                        # Create new KMS key in source account for sharing
                        key_response = self.source_kms.create_key(
                            Description='KMS key for sharing RDS snapshots across accounts',
                            KeyUsage='ENCRYPT_DECRYPT',
                            Origin='AWS_KMS',
                            MultiRegion=False
                        )
                        source_migration_key = key_response['KeyMetadata']['KeyId']
                        print(f"   ✅ Created source migration key: {source_migration_key}")
                        
                        # Create alias
                        try:
                            self.source_kms.create_alias(
                                AliasName='alias/rds-migration-source',
                                TargetKeyId=source_migration_key
                            )
                            print(f"   ✅ Created alias: alias/rds-migration-source")
                        except Exception as e:
                            print(f"   ⚠️  Could not create alias: {str(e)}")
                        
                        # Update key policy to allow target account access
                        try:
                            policy = {
                                "Version": "2012-10-17",
                                "Statement": [
                                    {
                                        "Sid": "Enable IAM User Permissions",
                                        "Effect": "Allow",
                                        "Principal": {
                                            "AWS": f"arn:aws:iam::{self.source_account_id}:root"
                                        },
                                        "Action": "kms:*",
                                        "Resource": "*"
                                    },
                                    {
                                        "Sid": "Allow Target Account",
                                        "Effect": "Allow",
                                        "Principal": {
                                            "AWS": f"arn:aws:iam::{self.target_account_id}:root"
                                        },
                                        "Action": [
                                            "kms:Decrypt",
                                            "kms:DescribeKey",
                                            "kms:CreateGrant"
                                        ],
                                        "Resource": "*"
                                    }
                                ]
                            }
                            self.source_kms.put_key_policy(
                                KeyId=source_migration_key,
                                PolicyName='default',
                                Policy=json.dumps(policy)
                            )
                            print(f"   ✅ Updated key policy to allow target account access")
                        except Exception as e:
                            print(f"   ⚠️  Warning: Could not update key policy: {str(e)}")
                    
                    # Copy snapshot with new key
                    print(f"   Copying snapshot with customer-managed key...")
                    self.source_rds.copy_db_snapshot(
                        SourceDBSnapshotIdentifier=snapshot_id,
                        TargetDBSnapshotIdentifier=source_share_snapshot_id,
                        KmsKeyId=source_migration_key
                    )
                    
                    print(f"   ⏳ Waiting for snapshot copy to complete...")
                    waiter = self.source_rds.get_waiter('db_snapshot_completed')
                    waiter.wait(DBSnapshotIdentifier=source_share_snapshot_id)
                    
                    print(f"   ✅ Snapshot re-encrypted: {source_share_snapshot_id}")
                    
                    # Use the re-encrypted snapshot for sharing
                    snapshot_id = source_share_snapshot_id
                    
                except Exception as e:
                    print(f"   ❌ Error re-encrypting snapshot: {str(e)}")
                    return
        
        # Step 4: Share snapshot with target account
        print(f"\n🔗 Step 4: Sharing snapshot with target account...")
        
        if dry_run:
            print(f"   [DRY RUN] Would share snapshot with account {self.target_account_id}")
        else:
            try:
                self.source_rds.modify_db_snapshot_attribute(
                    DBSnapshotIdentifier=snapshot_id,
                    AttributeName='restore',
                    ValuesToAdd=[self.target_account_id]
                )
                print(f"   ✅ Snapshot shared with target account")
            except Exception as e:
                print(f"   ❌ Error sharing snapshot: {str(e)}")
                return
        
        # Step 5: Copy and re-encrypt snapshot in target account (if encrypted)
        target_snapshot_id = snapshot_id
        if db_info['storage_encrypted']:
            print(f"\n📋 Step 5: Copying and re-encrypting snapshot in target account...")
            target_snapshot_id = f"{snapshot_id}-target"
            
            if dry_run:
                print(f"   [DRY RUN] Would copy snapshot with re-encryption")
                print(f"   [DRY RUN] Target snapshot: {target_snapshot_id}")
                print(f"   [DRY RUN] Target KMS key: {target_kms_key if target_kms_key else 'default'}")
            else:
                try:
                    source_snapshot_arn = f"arn:aws:rds:{self.source_session.region_name}:{self.source_account_id}:snapshot:{snapshot_id}"
                    
                    copy_params = {
                        'SourceDBSnapshotIdentifier': source_snapshot_arn,
                        'TargetDBSnapshotIdentifier': target_snapshot_id
                    }
                    
                    # Don't copy tags for shared snapshots - AWS doesn't allow it
                    # Tags will be applied separately after restore if needed
                    
                    if target_kms_key:
                        copy_params['KmsKeyId'] = target_kms_key
                    
                    self.target_rds.copy_db_snapshot(**copy_params)
                    
                    print(f"   ⏳ Waiting for snapshot copy to complete...")
                    waiter = self.target_rds.get_waiter('db_snapshot_completed')
                    waiter.wait(DBSnapshotIdentifier=target_snapshot_id)
                    
                    print(f"   ✅ Snapshot copied and re-encrypted: {target_snapshot_id}")
                except Exception as e:
                    print(f"   ❌ Error copying snapshot: {str(e)}")
                    return
        
        # Step 6: Restore RDS instance in target account
        print(f"\n🔄 Step 6: Restoring RDS instance in target account...")
        new_db_instance_id = f"{db_instance_id}-migrated"
        
        if dry_run:
            print(f"   [DRY RUN] Would restore RDS instance: {new_db_instance_id}")
            print(f"   [DRY RUN] From snapshot: {target_snapshot_id}")
            print(f"   [DRY RUN] Instance class: {db_info['db_instance_class']}")
            print(f"   [DRY RUN] Subnet group: {target_subnet_group}")
            print(f"   [DRY RUN] Security groups: {target_security_groups}")
            print(f"   [DRY RUN] Multi-AZ: {db_info['multi_az']}")
        else:
            try:
                restore_params = {
                    'DBInstanceIdentifier': new_db_instance_id,
                    'DBSnapshotIdentifier': target_snapshot_id,
                    'DBInstanceClass': db_info['db_instance_class'],
                    'DBSubnetGroupName': target_subnet_group,
                    'MultiAZ': db_info['multi_az'],
                    'PubliclyAccessible': db_info['publicly_accessible'],
                    'AutoMinorVersionUpgrade': db_info['auto_minor_version_upgrade'],
                    'DeletionProtection': db_info['deletion_protection'],
                    'Tags': db_info['tags'] + [
                        {'Key': 'MigratedFrom', 'Value': db_instance_id},
                        {'Key': 'MigrationDate', 'Value': datetime.now().isoformat()}
                    ]
                }
                
                if target_security_groups:
                    restore_params['VpcSecurityGroupIds'] = target_security_groups
                
                # Remove None values
                restore_params = {k: v for k, v in restore_params.items() if v is not None}
                
                self.target_rds.restore_db_instance_from_db_snapshot(**restore_params)
                
                print(f"   ⏳ Waiting for RDS instance to become available (this may take 10-20 minutes)...")
                waiter = self.target_rds.get_waiter('db_instance_available')
                waiter.wait(DBInstanceIdentifier=new_db_instance_id)
                
                print(f"   ✅ RDS instance restored: {new_db_instance_id}")
                
                # Get endpoint
                new_instance = self.target_rds.describe_db_instances(DBInstanceIdentifier=new_db_instance_id)
                endpoint = new_instance['DBInstances'][0].get('Endpoint', {})
                if endpoint:
                    print(f"   Endpoint: {endpoint.get('Address')}:{endpoint.get('Port')}")
                
            except Exception as e:
                print(f"   ❌ Error restoring RDS instance: {str(e)}")
                return
        
        # Summary
        print("\n" + "=" * 100)
        if dry_run:
            print("✅ DRY RUN COMPLETE")
            print("=" * 100)
            print("\n📝 Summary of what WOULD be done:")
            print(f"   1. Create snapshot of {db_instance_id}")
            print(f"   2. Share snapshot with target account")
            if db_info['storage_encrypted']:
                print(f"   3. Copy and re-encrypt snapshot with target KMS key")
            print(f"   4. Restore as {new_db_instance_id} in target account")
            print(f"   5. Configure subnet group: {target_subnet_group}")
            if target_security_groups:
                print(f"   6. Apply security groups: {', '.join(target_security_groups)}")
            print("\n⚠️  IMPORTANT:")
            print("   - This process can take 30+ minutes")
            print("   - Source database remains running")
            print("   - Test the new database before cutover")
            if db_info['storage_encrypted'] and not target_kms_key:
                print("   - Specify --target-kms-key for encrypted databases")
            print("\n🚀 To execute the migration, run without --dry-run flag")
        else:
            print("✅ MIGRATION COMPLETE")
            print("=" * 100)
            print(f"\n📋 Migration Summary:")
            print(f"   Source DB: {db_instance_id}")
            print(f"   New DB: {new_db_instance_id}")
            if 'endpoint' in locals() and endpoint:
                print(f"   Endpoint: {endpoint.get('Address')}:{endpoint.get('Port')}")
            print(f"\n📝 Next Steps:")
            print(f"   1. Test database connectivity")
            print(f"   2. Verify data integrity")
            print(f"   3. Update application connection strings")
            print(f"   4. Run application tests")
            print(f"   5. Plan cutover from source to target database")
            print(f"   6. Keep source database running as backup initially")
        print("=" * 100)
    
    def migrate_vpc(self, source_vpc_id: str, target_vpc_id: str = None, dry_run: bool = True):
        """
        Migrate VPC components to an existing target VPC
        
        Args:
            source_vpc_id: Source VPC ID to migrate from
            target_vpc_id: Target VPC ID to migrate to (required for actual migration)
            dry_run: If True, show what would be done without making changes
        """
        print("\n" + "=" * 100)
        if dry_run:
            print(f"🧪 DRY RUN: VPC Migration - {source_vpc_id}")
        else:
            print(f"🚀 VPC Migration - {source_vpc_id}")
        print("=" * 100)
        
        # Step 1: Analyze source VPC
        print("\n[Step 1/8] 📊 Analyzing source VPC...")
        try:
            vpc_response = self.source_ec2.describe_vpcs(VpcIds=[source_vpc_id])
            if not vpc_response['Vpcs']:
                raise ValueError(f"VPC {source_vpc_id} not found")
            
            source_vpc = vpc_response['Vpcs'][0]
            source_cidr = source_vpc['CidrBlock']
            
            # Get VPC attributes
            dns_support = self.source_ec2.describe_vpc_attribute(
                VpcId=source_vpc_id, Attribute='enableDnsSupport'
            )['EnableDnsSupport']['Value']
            
            dns_hostnames = self.source_ec2.describe_vpc_attribute(
                VpcId=source_vpc_id, Attribute='enableDnsHostnames'
            )['EnableDnsHostnames']['Value']
            
            vpc_name = next((tag['Value'] for tag in source_vpc.get('Tags', []) if tag['Key'] == 'Name'), 'UnnamedVPC')
            
            print(f"   ✅ Source VPC found: {vpc_name}")
            print(f"   CIDR: {source_cidr}")
            print(f"   DNS Support: {dns_support}")
            print(f"   DNS Hostnames: {dns_hostnames}")
            
            # Verify target VPC if not dry-run
            if not dry_run:
                if not target_vpc_id:
                    raise ValueError("Target VPC ID is required for actual migration. Use --target-vpc parameter.")
                
                target_vpc_response = self.target_ec2.describe_vpcs(VpcIds=[target_vpc_id])
                if not target_vpc_response['Vpcs']:
                    raise ValueError(f"Target VPC {target_vpc_id} not found in target account")
                
                target_vpc = target_vpc_response['Vpcs'][0]
                target_cidr = target_vpc['CidrBlock']
                target_vpc_name = next((tag['Value'] for tag in target_vpc.get('Tags', []) if tag['Key'] == 'Name'), 'UnnamedVPC')
                
                print(f"\n   ✅ Target VPC found: {target_vpc_name}")
                print(f"   Target VPC ID: {target_vpc_id}")
                print(f"   Target CIDR: {target_cidr}")
                print(f"   ℹ️  Will migrate components to existing VPC")
                
        except Exception as e:
            print(f"   ❌ Error: {str(e)}")
            return
        
        # Step 2: Get subnets
        print("\n[Step 2/8] 📊 Analyzing subnets...")
        try:
            subnets = self.source_ec2.describe_subnets(
                Filters=[{'Name': 'vpc-id', 'Values': [source_vpc_id]}]
            )['Subnets']
            
            print(f"   ✅ Found {len(subnets)} subnets:")
            subnet_mapping = {}
            for subnet in subnets:
                subnet_name = next((tag['Value'] for tag in subnet.get('Tags', []) if tag['Key'] == 'Name'), subnet['SubnetId'])
                print(f"      - {subnet_name}: {subnet['CidrBlock']} in {subnet['AvailabilityZone']}")
                subnet_mapping[subnet['SubnetId']] = {
                    'cidr': subnet['CidrBlock'],
                    'az': subnet['AvailabilityZone'],
                    'name': subnet_name,
                    'map_public_ip': subnet.get('MapPublicIpOnLaunch', False),
                    'tags': subnet.get('Tags', [])
                }
        except Exception as e:
            print(f"   ⚠️  Error: {str(e)}")
            subnets = []
            subnet_mapping = {}
        
        # Step 3: Get Internet Gateway
        print("\n[Step 3/8] 📊 Analyzing Internet Gateway...")
        try:
            igws = self.source_ec2.describe_internet_gateways(
                Filters=[{'Name': 'attachment.vpc-id', 'Values': [source_vpc_id]}]
            )['InternetGateways']
            
            has_igw = len(igws) > 0
            print(f"   {'✅' if has_igw else 'ℹ️ '} Internet Gateway: {'Yes' if has_igw else 'No'}")
        except Exception as e:
            print(f"   ⚠️  Error: {str(e)}")
            has_igw = False
        
        # Step 4: Get NAT Gateways
        print("\n[Step 4/8] 📊 Analyzing NAT Gateways...")
        try:
            nat_gws = self.source_ec2.describe_nat_gateways(
                Filters=[{'Name': 'vpc-id', 'Values': [source_vpc_id]}]
            )['NatGateways']
            
            active_nat_gws = [nat for nat in nat_gws if nat['State'] == 'available']
            print(f"   ✅ Found {len(active_nat_gws)} NAT Gateway(s)")
            nat_gateway_mapping = {}
            for nat in active_nat_gws:
                nat_name = next((tag['Value'] for tag in nat.get('Tags', []) if tag['Key'] == 'Name'), nat['NatGatewayId'])
                print(f"      - {nat_name}: {nat['NatGatewayId']} in subnet {nat['SubnetId']}")
                nat_gateway_mapping[nat['NatGatewayId']] = {
                    'subnet_id': nat['SubnetId'],
                    'name': nat_name,
                    'tags': nat.get('Tags', [])
                }
        except Exception as e:
            print(f"   ⚠️  Error: {str(e)}")
            nat_gateway_mapping = {}
        
        # Step 5: Get Route Tables
        print("\n[Step 5/8] 📊 Analyzing Route Tables...")
        try:
            route_tables = self.source_ec2.describe_route_tables(
                Filters=[{'Name': 'vpc-id', 'Values': [source_vpc_id]}]
            )['RouteTables']
            
            print(f"   ✅ Found {len(route_tables)} route table(s):")
            route_table_mapping = {}
            for rt in route_tables:
                is_main = any(assoc.get('Main', False) for assoc in rt.get('Associations', []))
                rt_name = next((tag['Value'] for tag in rt.get('Tags', []) if tag['Key'] == 'Name'), 
                              'Main' if is_main else rt['RouteTableId'])
                print(f"      - {rt_name}: {len(rt['Routes'])} routes")
                route_table_mapping[rt['RouteTableId']] = {
                    'routes': rt['Routes'],
                    'associations': rt.get('Associations', []),
                    'is_main': is_main,
                    'name': rt_name,
                    'tags': rt.get('Tags', [])
                }
        except Exception as e:
            print(f"   ⚠️  Error: {str(e)}")
            route_table_mapping = {}
        
        # Step 6: Get Security Groups
        print("\n[Step 6/8] 📊 Analyzing Security Groups...")
        try:
            security_groups = self.source_ec2.describe_security_groups(
                Filters=[{'Name': 'vpc-id', 'Values': [source_vpc_id]}]
            )['SecurityGroups']
            
            # Exclude default security group
            custom_sgs = [sg for sg in security_groups if sg['GroupName'] != 'default']
            print(f"   ✅ Found {len(custom_sgs)} custom security group(s):")
            sg_mapping = {}
            for sg in custom_sgs:
                print(f"      - {sg['GroupName']}: {sg['Description']}")
                sg_mapping[sg['GroupId']] = {
                    'name': sg['GroupName'],
                    'description': sg['Description'],
                    'ingress_rules': sg.get('IpPermissions', []),
                    'egress_rules': sg.get('IpPermissionsEgress', []),
                    'tags': sg.get('Tags', [])
                }
        except Exception as e:
            print(f"   ⚠️  Error: {str(e)}")
            sg_mapping = {}
        
        # Step 7: Get Network ACLs
        print("\n[Step 7/8] 📊 Analyzing Network ACLs...")
        try:
            nacls = self.source_ec2.describe_network_acls(
                Filters=[{'Name': 'vpc-id', 'Values': [source_vpc_id]}]
            )['NetworkAcls']
            
            custom_nacls = [nacl for nacl in nacls if not nacl['IsDefault']]
            print(f"   ✅ Found {len(custom_nacls)} custom Network ACL(s)")
            nacl_mapping = {}
            for nacl in custom_nacls:
                nacl_name = next((tag['Value'] for tag in nacl.get('Tags', []) if tag['Key'] == 'Name'), nacl['NetworkAclId'])
                print(f"      - {nacl_name}: {len(nacl['Entries'])} rules")
                nacl_mapping[nacl['NetworkAclId']] = {
                    'entries': nacl['Entries'],
                    'associations': nacl.get('Associations', []),
                    'name': nacl_name,
                    'tags': nacl.get('Tags', [])
                }
        except Exception as e:
            print(f"   ⚠️  Error: {str(e)}")
            nacl_mapping = {}
        
        # Step 8: Create migration plan or execute
        print("\n[Step 8/8] 📝 Creating migration plan...")
        
        if dry_run:
            print("\n" + "=" * 100)
            print("📋 DRY RUN - MIGRATION PLAN")
            print("=" * 100)
            
            print("\n1️⃣  CREATE VPC:")
            print(f"   - CIDR: {source_cidr}")
            print(f"   - DNS Support: {dns_support}")
            print(f"   - DNS Hostnames: {dns_hostnames}")
            print(f"   - Tags: Name={vpc_name}")
            
            print(f"\n2️⃣  CREATE {len(subnets)} SUBNETS:")
            for subnet_id, subnet_info in subnet_mapping.items():
                print(f"   - {subnet_info['name']}: {subnet_info['cidr']} in {subnet_info['az']}")
                if subnet_info['map_public_ip']:
                    print(f"     → Auto-assign public IP: Yes")
            
            if has_igw:
                print("\n3️⃣  CREATE INTERNET GATEWAY:")
                print(f"   - Attach to new VPC")
            
            if nat_gateway_mapping:
                print(f"\n4️⃣  CREATE {len(nat_gateway_mapping)} NAT GATEWAY(S):")
                for nat_id, nat_info in nat_gateway_mapping.items():
                    print(f"   - {nat_info['name']} in subnet (will be mapped)")
                    print(f"     → Allocate Elastic IP")
            
            print(f"\n5️⃣  CREATE {len(custom_sgs)} SECURITY GROUP(S):")
            for sg_id, sg_info in sg_mapping.items():
                print(f"   - {sg_info['name']}: {sg_info['description']}")
                print(f"     → Ingress rules: {len(sg_info['ingress_rules'])}")
                print(f"     → Egress rules: {len(sg_info['egress_rules'])}")
            
            print(f"\n6️⃣  CREATE {len(route_table_mapping)} ROUTE TABLE(S):")
            for rt_id, rt_info in route_table_mapping.items():
                if rt_info['is_main']:
                    print(f"   - {rt_info['name']} (Main): {len(rt_info['routes'])} routes")
                else:
                    print(f"   - {rt_info['name']}: {len(rt_info['routes'])} routes")
                for route in rt_info['routes']:
                    if 'GatewayId' in route and route['GatewayId'] == 'local':
                        continue
                    dest = route.get('DestinationCidrBlock', route.get('DestinationIpv6CidrBlock', 'Unknown'))
                    if 'GatewayId' in route and route['GatewayId'].startswith('igw-'):
                        print(f"     → {dest} → Internet Gateway")
                    elif 'NatGatewayId' in route:
                        print(f"     → {dest} → NAT Gateway (will be mapped)")
                    elif 'NetworkInterfaceId' in route:
                        print(f"     → {dest} → ENI (needs manual configuration)")
            
            if custom_nacls:
                print(f"\n7️⃣  CREATE {len(custom_nacls)} NETWORK ACL(S):")
                for nacl_id, nacl_info in nacl_mapping.items():
                    print(f"   - {nacl_info['name']}: {len(nacl_info['entries'])} rules")
            
            print("\n⏱️  ESTIMATED TIME: 10-15 minutes")
            print("\n⚠️  IMPORTANT NOTES:")
            print("   - Requires existing VPC in target account (use --target-vpc parameter)")
            print("   - VPC Peering connections will NOT be migrated (requires manual setup)")
            print("   - VPN connections will NOT be migrated (requires manual setup)")
            print("   - Transit Gateway attachments will NOT be migrated (requires manual setup)")
            print("   - VPC Endpoints will need to be recreated manually")
            print("   - Elastic IPs for NAT Gateways will be new (different IPs)")
            print("   - Update any hardcoded IPs in applications")
            
            print("\n🚀 To execute the migration:")
            print(f"   python aws_migration.py --migrate-vpc {source_vpc_id} --target-vpc vpc-xxx")
            print("=" * 100)
            
        else:
            # Execute actual migration
            print("\n🚀 EXECUTING MIGRATION...")
            
            if not target_vpc_id:
                print("❌ ERROR: --target-vpc is required for VPC migration")
                print("   The tool no longer creates new VPCs. You must specify an existing target VPC.")
                print(f"   Example: --migrate-vpc {source_vpc_id} --target-vpc vpc-xxx")
                return
            
            migration_result = {
                'source_vpc_id': source_vpc_id,
                'target_vpc_id': target_vpc_id,
                'vpc_reused': True,
                'subnet_mapping': {},
                'sg_mapping': {},
                'nat_gateway_mapping': {},
                'route_table_mapping': {}
            }
            
            try:
                print(f"\n[Using existing target VPC: {target_vpc_id}]")
                
                # Create or reuse subnets
                print(f"\n[Processing {len(subnets)} subnets...]")
                for source_subnet_id, subnet_info in subnet_mapping.items():
                    try:
                        # Map AZ (might need adjustment for cross-region)
                        target_az = subnet_info['az']
                        if self.source_session.region_name != self.target_session.region_name:
                            # Try to use same AZ suffix (e.g., us-east-1a -> us-west-2a)
                            az_suffix = subnet_info['az'][-1]
                            target_az = f"{self.target_session.region_name}{az_suffix}"
                        
                        # Check for existing subnet with same CIDR in the target VPC
                        existing_subnets = self.target_ec2.describe_subnets(
                            Filters=[
                                {'Name': 'vpc-id', 'Values': [target_vpc_id]},
                                {'Name': 'cidr-block', 'Values': [subnet_info['cidr']]}
                            ]
                        )['Subnets']
                        
                        if existing_subnets:
                            target_subnet_id = existing_subnets[0]['SubnetId']
                            migration_result['subnet_mapping'][source_subnet_id] = target_subnet_id
                            existing_subnet_name = next((tag['Value'] for tag in existing_subnets[0].get('Tags', []) if tag['Key'] == 'Name'), target_subnet_id)
                            print(f"   ✅ Reusing existing subnet: {subnet_info['name']} → {target_subnet_id} ({existing_subnet_name})")
                        else:
                            # Create new subnet
                            target_subnet = self.target_ec2.create_subnet(
                                VpcId=target_vpc_id,
                                CidrBlock=subnet_info['cidr'],
                                AvailabilityZone=target_az
                            )
                            target_subnet_id = target_subnet['Subnet']['SubnetId']
                            migration_result['subnet_mapping'][source_subnet_id] = target_subnet_id
                            
                            # Tag subnet
                            self.target_ec2.create_tags(
                                Resources=[target_subnet_id],
                                Tags=[{'Key': 'Name', 'Value': f"{subnet_info['name']}-migrated"}] + 
                                     [tag for tag in subnet_info['tags'] if tag['Key'] != 'Name']
                            )
                            
                            print(f"   ✅ Created subnet: {subnet_info['name']} → {target_subnet_id}")
                        
                        # Set map public IP if needed
                        if subnet_info['map_public_ip']:
                            self.target_ec2.modify_subnet_attribute(
                                SubnetId=target_subnet_id,
                                MapPublicIpOnLaunch={'Value': True}
                            )
                        
                        print(f"   ✅ Created subnet: {subnet_info['name']} → {target_subnet_id}")
                    except Exception as e:
                        print(f"   ⚠️  Error creating subnet {subnet_info['name']}: {str(e)}")
                
                # Create or reuse Internet Gateway
                if has_igw:
                    print("\n[Processing Internet Gateway...]")
                    try:
                        # Check if target VPC already has an Internet Gateway
                        existing_igws = self.target_ec2.describe_internet_gateways(
                            Filters=[{'Name': 'attachment.vpc-id', 'Values': [target_vpc_id]}]
                        )['InternetGateways']
                        
                        if existing_igws:
                            target_igw_id = existing_igws[0]['InternetGatewayId']
                            migration_result['igw_id'] = target_igw_id
                            print(f"   ✅ Reusing existing Internet Gateway: {target_igw_id}")
                        else:
                            # Create new Internet Gateway
                            target_igw = self.target_ec2.create_internet_gateway()
                            target_igw_id = target_igw['InternetGateway']['InternetGatewayId']
                            self.target_ec2.attach_internet_gateway(
                                InternetGatewayId=target_igw_id,
                                VpcId=target_vpc_id
                            )
                            migration_result['igw_id'] = target_igw_id
                            print(f"   ✅ Created and attached IGW: {target_igw_id}")
                    except Exception as e:
                        print(f"   ⚠️  Error processing IGW: {str(e)}")
                
                # Create or reuse Security Groups (two-pass: create first, then add rules)
                print(f"\n[Processing {len(custom_sgs)} security groups...]")
                for source_sg_id, sg_info in sg_mapping.items():
                    try:
                        # Check for existing security group with same name in the target VPC
                        existing_sgs = self.target_ec2.describe_security_groups(
                            Filters=[
                                {'Name': 'vpc-id', 'Values': [target_vpc_id]},
                                {'Name': 'group-name', 'Values': [sg_info['name'], f"{sg_info['name']}-migrated"]}
                            ]
                        )['SecurityGroups']
                        
                        if existing_sgs:
                            target_sg_id = existing_sgs[0]['GroupId']
                            migration_result['sg_mapping'][source_sg_id] = target_sg_id
                            print(f"   ✅ Reusing existing security group: {sg_info['name']} → {target_sg_id}")
                        else:
                            # Create new security group
                            target_sg = self.target_ec2.create_security_group(
                                GroupName=f"{sg_info['name']}-migrated",
                                Description=sg_info['description'] or 'Migrated security group',
                                VpcId=target_vpc_id
                            )
                            target_sg_id = target_sg['GroupId']
                            migration_result['sg_mapping'][source_sg_id] = target_sg_id
                            
                            # Tag security group
                            if sg_info['tags']:
                                self.target_ec2.create_tags(
                                    Resources=[target_sg_id],
                                    Tags=sg_info['tags']
                                )
                            
                            print(f"   ✅ Created security group: {sg_info['name']} → {target_sg_id}")
                    except Exception as e:
                        print(f"   ⚠️  Error processing SG {sg_info['name']}: {str(e)}")
                
                # Add security group rules
                print("\n[Adding security group rules...]")
                for source_sg_id, sg_info in sg_mapping.items():
                    if source_sg_id not in migration_result['sg_mapping']:
                        continue
                    
                    target_sg_id = migration_result['sg_mapping'][source_sg_id]
                    
                    # Add ingress rules
                    for rule in sg_info['ingress_rules']:
                        try:
                            # Map source security groups
                            for user_id_group_pair in rule.get('UserIdGroupPairs', []):
                                if user_id_group_pair['GroupId'] in migration_result['sg_mapping']:
                                    user_id_group_pair['GroupId'] = migration_result['sg_mapping'][user_id_group_pair['GroupId']]
                            
                            self.target_ec2.authorize_security_group_ingress(
                                GroupId=target_sg_id,
                                IpPermissions=[rule]
                            )
                        except Exception as e:
                            if 'Duplicate' not in str(e):
                                print(f"   ⚠️  Error adding ingress rule: {str(e)}")
                
                # Create NAT Gateways
                if nat_gateway_mapping:
                    print(f"\n[Creating {len(nat_gateway_mapping)} NAT Gateway(s)...]")
                    for source_nat_id, nat_info in nat_gateway_mapping.items():
                        try:
                            # Map source subnet to target subnet
                            if nat_info['subnet_id'] not in migration_result['subnet_mapping']:
                                print(f"   ⚠️  Cannot create NAT Gateway: subnet {nat_info['subnet_id']} not found")
                                continue
                            
                            target_subnet_id = migration_result['subnet_mapping'][nat_info['subnet_id']]
                            
                            # Allocate Elastic IP
                            eip = self.target_ec2.allocate_address(Domain='vpc')
                            allocation_id = eip['AllocationId']
                            
                            # Create NAT Gateway
                            nat_gw = self.target_ec2.create_nat_gateway(
                                SubnetId=target_subnet_id,
                                AllocationId=allocation_id
                            )
                            target_nat_id = nat_gw['NatGateway']['NatGatewayId']
                            migration_result['nat_gateway_mapping'][source_nat_id] = target_nat_id
                            
                            print(f"   ✅ Created NAT Gateway: {nat_info['name']} → {target_nat_id}")
                            print(f"      EIP: {eip['PublicIp']}")
                        except Exception as e:
                            print(f"   ⚠️  Error creating NAT Gateway: {str(e)}")
                    
                    # Wait for NAT Gateways to be available
                    if migration_result['nat_gateway_mapping']:
                        print("   ⏳ Waiting for NAT Gateways to be available (2-5 minutes)...")
                        time.sleep(30)
                
                # Create Route Tables
                print(f"\n[Creating route tables...]")
                for source_rt_id, rt_info in route_table_mapping.items():
                    if rt_info['is_main']:
                        # Use the main route table
                        main_rt = self.target_ec2.describe_route_tables(
                            Filters=[
                                {'Name': 'vpc-id', 'Values': [target_vpc_id]},
                                {'Name': 'association.main', 'Values': ['true']}
                            ]
                        )['RouteTables'][0]
                        target_rt_id = main_rt['RouteTableId']
                        migration_result['route_table_mapping'][source_rt_id] = target_rt_id
                        print(f"   ✅ Using main route table: {target_rt_id}")
                    else:
                        # Create custom route table
                        try:
                            target_rt = self.target_ec2.create_route_table(VpcId=target_vpc_id)
                            target_rt_id = target_rt['RouteTable']['RouteTableId']
                            migration_result['route_table_mapping'][source_rt_id] = target_rt_id
                            
                            # Tag route table
                            self.target_ec2.create_tags(
                                Resources=[target_rt_id],
                                Tags=[{'Key': 'Name', 'Value': f"{rt_info['name']}-migrated"}] + 
                                     [tag for tag in rt_info['tags'] if tag['Key'] != 'Name']
                            )
                            
                            print(f"   ✅ Created route table: {rt_info['name']} → {target_rt_id}")
                        except Exception as e:
                            print(f"   ⚠️  Error creating route table: {str(e)}")
                            continue
                    
                    # Add routes
                    for route in rt_info['routes']:
                        try:
                            if route.get('GatewayId') == 'local':
                                continue  # Skip local routes
                            
                            route_params = {'RouteTableId': target_rt_id}
                            
                            if 'DestinationCidrBlock' in route:
                                route_params['DestinationCidrBlock'] = route['DestinationCidrBlock']
                            elif 'DestinationIpv6CidrBlock' in route:
                                route_params['DestinationIpv6CidrBlock'] = route['DestinationIpv6CidrBlock']
                            else:
                                continue
                            
                            if 'GatewayId' in route and route['GatewayId'].startswith('igw-'):
                                if 'igw_id' in migration_result:
                                    route_params['GatewayId'] = migration_result['igw_id']
                            elif 'NatGatewayId' in route:
                                if route['NatGatewayId'] in migration_result['nat_gateway_mapping']:
                                    route_params['NatGatewayId'] = migration_result['nat_gateway_mapping'][route['NatGatewayId']]
                                else:
                                    continue
                            else:
                                continue  # Skip other route types (ENI, peering, etc.)
                            
                            self.target_ec2.create_route(**route_params)
                        except Exception as e:
                            if 'RouteAlreadyExists' not in str(e):
                                print(f"   ⚠️  Error adding route: {str(e)}")
                    
                    # Associate route table with subnets
                    for association in rt_info['associations']:
                        if 'SubnetId' in association:
                            source_subnet_id = association['SubnetId']
                            if source_subnet_id in migration_result['subnet_mapping']:
                                target_subnet_id = migration_result['subnet_mapping'][source_subnet_id]
                                try:
                                    self.target_ec2.associate_route_table(
                                        RouteTableId=target_rt_id,
                                        SubnetId=target_subnet_id
                                    )
                                except Exception as e:
                                    print(f"   ⚠️  Error associating route table: {str(e)}")
                
                print("\n" + "=" * 100)
                print("✅ VPC MIGRATION COMPLETE")
                print("=" * 100)
                print(f"\n📋 Migration Summary:")
                print(f"   Source VPC: {source_vpc_id}")
                print(f"   Target VPC: {target_vpc_id}")
                print(f"   Subnets migrated: {len(migration_result['subnet_mapping'])}")
                print(f"   Security groups migrated: {len(migration_result['sg_mapping'])}")
                print(f"   NAT Gateways created: {len(migration_result['nat_gateway_mapping'])}")
                
                print(f"\n📝 Resource Mapping:")
                print(f"\n   Subnets:")
                for src, tgt in migration_result['subnet_mapping'].items():
                    print(f"      {src} → {tgt}")
                
                print(f"\n   Security Groups:")
                for src, tgt in migration_result['sg_mapping'].items():
                    print(f"      {src} → {tgt}")
                
                print(f"\n⚠️  IMPORTANT NEXT STEPS:")
                print(f"   1. Test network connectivity in new VPC")
                print(f"   2. VPC Peering: Recreate manually if needed")
                print(f"   3. VPN Connections: Recreate manually")
                print(f"   4. VPC Endpoints: Recreate for AWS services")
                print(f"   5. Update references to old subnet/SG IDs in applications")
                print(f"   6. Now you can migrate EC2/RDS instances to this VPC")
                print("=" * 100)
                
                # Save mapping to file
                mapping_file = '/output/vpc_migration_mapping.json'
                with open(mapping_file, 'w') as f:
                    json.dump(migration_result, f, indent=2)
                print(f"\n💾 Resource mapping saved to: {mapping_file}")
                
            except Exception as e:
                print(f"\n❌ MIGRATION FAILED: {str(e)}")
                import traceback
                traceback.print_exc()
                print("\n⚠️  Partial migration may have occurred. Check target account.")


def main():
    parser = argparse.ArgumentParser(
        description='AWS Cross-Account Migration Tool',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Setup IAM policies (dry-run first)
  python aws_migration.py --setup-policies --dry-run

  # Actually create IAM policies
  python aws_migration.py --setup-policies

  # Generate migration report (dry-run analysis)
  python aws_migration.py --report

  # Specify custom region
  python aws_migration.py --report --source-region us-west-2 --target-region us-west-2

  # Filter by specific EC2 instances
  python aws_migration.py --report --ec2-instances i-abc123,i-def456

  # Migrate entire VPC (dry-run first) - requires existing target VPC
  python aws_migration.py --migrate-vpc vpc-abc123 --target-vpc vpc-xyz789 --dry-run

  # Actually migrate VPC components to existing target VPC
  python aws_migration.py --migrate-vpc vpc-abc123 --target-vpc vpc-xyz789

  # Migrate specific EC2 instance (dry-run first)
  python aws_migration.py --migrate-ec2 i-abc123 --target-vpc vpc-xxx --target-subnet subnet-xxx --dry-run

  # Actually migrate EC2 instance
  python aws_migration.py --migrate-ec2 i-abc123 --target-vpc vpc-xxx --target-subnet subnet-xxx

  # Migrate specific RDS instance (dry-run)
  python aws_migration.py --migrate-rds mydb --target-subnet-group my-subnet-group --dry-run

  # Actually migrate RDS instance
  python aws_migration.py --migrate-rds mydb --target-subnet-group my-subnet-group
        """
    )
    
    # Connection arguments
    parser.add_argument('--source-profile', default='source_acc',
                       help='AWS CLI profile for source account (default: source_acc)')
    parser.add_argument('--target-profile', default='target_acc',
                       help='AWS CLI profile for target account (default: target_acc)')
    parser.add_argument('--source-region', default='us-east-1',
                       help='AWS region for source account (default: us-east-1)')
    parser.add_argument('--target-region', default='us-east-1',
                       help='AWS region for target account (default: us-east-1)')
    
    # Action arguments
    parser.add_argument('--setup-policies', action='store_true',
                       help='Setup required IAM policies in both source and target accounts')
    parser.add_argument('--report', action='store_true',
                       help='Generate migration report (analysis only)')
    parser.add_argument('--migrate-ec2', type=str, metavar='INSTANCE_ID',
                       help='Migrate a single EC2 instance by ID')
    parser.add_argument('--migrate-rds', type=str, metavar='DB_INSTANCE_ID',
                       help='Migrate a single RDS instance by ID')
    parser.add_argument('--migrate-vpc', type=str, metavar='VPC_ID',
                       help='Migrate an entire VPC and its components')
    parser.add_argument('--dry-run', action='store_true',
                       help='Perform dry-run (show what would be done without making changes)')
    
    # Filter arguments
    parser.add_argument('--ec2-instances', type=str,
                       help='Comma-separated list of EC2 instance IDs to analyze')
    parser.add_argument('--rds-instances', type=str,
                       help='Comma-separated list of RDS instance IDs to analyze')
    
    # Target environment arguments (for migration)
    parser.add_argument('--target-vpc', type=str,
                       help='Target VPC ID for EC2 migration')
    parser.add_argument('--target-subnet', type=str,
                       help='Target subnet ID for EC2 migration')
    parser.add_argument('--target-security-groups', type=str,
                       help='Comma-separated target security group IDs')
    parser.add_argument('--target-key-pair', type=str,
                       help='Target key pair name (if different from source)')
    parser.add_argument('--target-subnet-group', type=str,
                       help='Target DB subnet group name for RDS migration')
    parser.add_argument('--target-kms-key', type=str,
                       help='Target KMS key ID for re-encryption (optional)')
    
    args = parser.parse_args()
    
    # Parse instance lists
    ec2_instance_ids = args.ec2_instances.split(',') if args.ec2_instances else None
    rds_instance_ids = args.rds_instances.split(',') if args.rds_instances else None
    target_security_groups = args.target_security_groups.split(',') if args.target_security_groups else []
    
    try:
        # Initialize orchestrator with state file in /output for persistence
        orchestrator = AWSMigrationOrchestrator(
            args.source_profile,
            args.target_profile,
            args.source_region,
            args.target_region,
            state_file="/output/migration_state.json"
        )
        
        if args.setup_policies:
            # Setup IAM policies
            print("\n🔐 SETTING UP IAM POLICIES...")
            orchestrator.setup_iam_policies(dry_run=args.dry_run)
            
        elif args.report:
            # Report generation mode
            print("\n📊 GENERATING MIGRATION REPORT...")
            orchestrator.generate_complete_migration_report(ec2_instance_ids, rds_instance_ids)
            orchestrator.save_migration_report()
            orchestrator.generate_ssh_keys_script()
            
            print("\n" + "=" * 100)
            print("✅ REPORT GENERATION COMPLETE")
            print("=" * 100)
            print("📄 Review the following files in /output directory:")
            print("   - migration_report.json")
            print("   - user_data_backup.json (if instances have user data)")
            print("   - generate_ssh_keys.sh")
            print("\n📝 Next steps:")
            print("   1. Review the migration report")
            print("   2. Plan your maintenance window")
            print("   3. Use --migrate-ec2 or --migrate-rds to migrate resources")
            print("   4. Always use --dry-run first to see what will happen")
            print("=" * 100)
            
        elif args.migrate_ec2:
            # Migrate single EC2 instance
            if not args.target_vpc or not args.target_subnet:
                print("❌ ERROR: --target-vpc and --target-subnet are required for EC2 migration")
                sys.exit(1)
            
            orchestrator.migrate_single_ec2_instance(
                instance_id=args.migrate_ec2,
                target_vpc_id=args.target_vpc,
                target_subnet_id=args.target_subnet,
                target_security_groups=target_security_groups,
                target_key_pair=args.target_key_pair,
                dry_run=args.dry_run
            )
            
        elif args.migrate_rds:
            # Migrate single RDS instance
            if not args.target_subnet_group:
                print("❌ ERROR: --target-subnet-group is required for RDS migration")
                sys.exit(1)
            
            orchestrator.migrate_single_rds_instance(
                db_instance_id=args.migrate_rds,
                target_subnet_group=args.target_subnet_group,
                target_security_groups=target_security_groups,
                target_kms_key=args.target_kms_key,
                dry_run=args.dry_run
            )
        
        elif args.migrate_vpc:
            # Migrate VPC components to existing target VPC
            orchestrator.migrate_vpc(
                source_vpc_id=args.migrate_vpc,
                target_vpc_id=args.target_vpc,
                dry_run=args.dry_run
            )
            
        else:
            parser.print_help()
    
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
