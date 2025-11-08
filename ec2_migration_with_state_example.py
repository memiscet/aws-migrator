"""
Example: EC2 Migration with State Management Integration

This shows how to integrate the state manager into the EC2 migration flow.
"""

def migrate_ec2_with_state(self, instance_id: str, target_vpc_id: str, 
                           target_subnet_id: str, target_security_groups: List[str] = None):
    """
    Migrate EC2 instance with state management for resume capability
    
    This method wraps the migration logic with state tracking, enabling:
    - Resume from failure point
    - Skip already completed steps
    - Track all created resources
    """
    
    # Initialize migration in state
    migration_id = self.state_manager.initialize_migration(
        ResourceType.EC2_INSTANCE,
        instance_id,
        source_metadata={"target_vpc": target_vpc_id, "target_subnet": target_subnet_id}
    )
    
    try:
        # Update overall status to in-progress
        self.state_manager.update_migration_status(migration_id, MigrationStatus.IN_PROGRESS)
        
        print(f"\n{'='*100}")
        print(f"🚀 MIGRATING EC2 Instance - {instance_id}")
        print(f"   Migration ID: {migration_id}")
        
        # Check existing state
        existing_state = self.state_manager.get_migration_info(migration_id)
        if existing_state and existing_state['status'] == MigrationStatus.COMPLETED.value:
            print(f"✅ Migration already completed!")
            print(f"   Target Instance: {existing_state.get('target_id')}")
            self.state_manager.print_migration_summary(migration_id)
            return
        
        print(f"{'='*100}\n")
        
        # STEP 1: Analyze Instance
        step_name = "analyze_instance"
        if not self.state_manager.is_step_completed(migration_id, step_name):
            self.state_manager.add_step(migration_id, step_name, "Analyze source instance")
            self.state_manager.update_step_status(migration_id, step_name, MigrationStatus.IN_PROGRESS)
            
            print(f"📊 Step 1: Analyzing instance {instance_id}...")
            try:
                response = self.source_ec2.describe_instances(InstanceIds=[instance_id])
                instance = response['Reservations'][0]['Instances'][0]
                instance_info = self._get_instance_details(instance)
                
                self.state_manager.update_step_status(
                    migration_id, step_name, MigrationStatus.COMPLETED,
                    data=instance_info
                )
                print(f"✅ Instance analyzed successfully")
            except Exception as e:
                error_msg = f"Failed to analyze instance: {str(e)}"
                self.state_manager.update_step_status(migration_id, step_name, MigrationStatus.FAILED, error=error_msg)
                raise
        else:
            print(f"⏭️  Step 1: Instance analysis already completed (skipping)")
            instance_info = self.state_manager.get_step_data(migration_id, step_name)
        
        # STEP 2: Create Custom AMI
        step_name = "create_ami"
        if not self.state_manager.is_step_completed(migration_id, step_name):
            self.state_manager.add_step(migration_id, step_name, "Create custom AMI from instance")
            self.state_manager.update_step_status(migration_id, step_name, MigrationStatus.IN_PROGRESS)
            
            print(f"\n📦 Step 2: Creating custom AMI from instance...")
            try:
                ami_name = f"migration-{instance_id}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
                create_image_response = self.source_ec2.create_image(
                    InstanceId=instance_id,
                    Name=ami_name,
                    Description=f"Migration snapshot of {instance_id}",
                    NoReboot=True
                )
                source_ami_id = create_image_response['ImageId']
                
                # Track created resource
                self.state_manager.add_created_resource(
                    migration_id, "ami", source_ami_id,
                    {"name": ami_name, "account": "source"}
                )
                
                self.state_manager.update_step_status(
                    migration_id, step_name, MigrationStatus.COMPLETED,
                    data={"source_ami_id": source_ami_id, "ami_name": ami_name}
                )
                print(f"✅ Custom AMI created: {source_ami_id}")
            except Exception as e:
                error_msg = f"Failed to create AMI: {str(e)}"
                self.state_manager.update_step_status(migration_id, step_name, MigrationStatus.FAILED, error=error_msg)
                raise
        else:
            print(f"⏭️  Step 2: AMI creation already completed (skipping)")
            ami_data = self.state_manager.get_step_data(migration_id, step_name)
            source_ami_id = ami_data['source_ami_id']
            print(f"   Using existing AMI: {source_ami_id}")
        
        # STEP 3: Wait for Source AMI
        step_name = "wait_source_ami"
        if not self.state_manager.is_step_completed(migration_id, step_name):
            self.state_manager.add_step(migration_id, step_name, "Wait for source AMI to become available")
            self.state_manager.update_step_status(migration_id, step_name, MigrationStatus.IN_PROGRESS)
            
            print(f"\n⏳ Step 3: Waiting for AMI to become available...")
            try:
                waiter = self.source_ec2.get_waiter('image_available')
                waiter_config = {'Delay': 15, 'MaxAttempts': 80}
                waiter.wait(ImageIds=[source_ami_id], WaiterConfig=waiter_config)
                
                self.state_manager.update_step_status(migration_id, step_name, MigrationStatus.COMPLETED)
                print(f"✅ AMI is available")
            except Exception as e:
                error_msg = f"Timeout waiting for AMI: {str(e)}"
                self.state_manager.update_step_status(migration_id, step_name, MigrationStatus.FAILED, error=error_msg)
                raise
        else:
            print(f"⏭️  Step 3: Source AMI wait already completed (skipping)")
        
        # STEP 4: Grant Snapshot Permissions
        step_name = "grant_snapshot_permissions"
        if not self.state_manager.is_step_completed(migration_id, step_name):
            self.state_manager.add_step(migration_id, step_name, "Grant snapshot permissions to target account")
            self.state_manager.update_step_status(migration_id, step_name, MigrationStatus.IN_PROGRESS)
            
            print(f"\n🔓 Step 4: Granting snapshot permissions...")
            try:
                ami_details = self.source_ec2.describe_images(ImageIds=[source_ami_id])['Images'][0]
                snapshot_ids = []
                for bdm in ami_details.get('BlockDeviceMappings', []):
                    if 'Ebs' in bdm and 'SnapshotId' in bdm['Ebs']:
                        snapshot_id = bdm['Ebs']['SnapshotId']
                        self.source_ec2.modify_snapshot_attribute(
                            SnapshotId=snapshot_id,
                            Attribute='createVolumePermission',
                            OperationType='add',
                            UserIds=[self.target_account_id]
                        )
                        snapshot_ids.append(snapshot_id)
                
                self.state_manager.update_step_status(
                    migration_id, step_name, MigrationStatus.COMPLETED,
                    data={"snapshot_ids": snapshot_ids}
                )
                print(f"✅ Granted permissions for {len(snapshot_ids)} snapshots")
            except Exception as e:
                error_msg = f"Failed to grant snapshot permissions: {str(e)}"
                self.state_manager.update_step_status(migration_id, step_name, MigrationStatus.FAILED, error=error_msg)
                raise
        else:
            print(f"⏭️  Step 4: Snapshot permissions already granted (skipping)")
        
        # STEP 5: Share AMI
        step_name = "share_ami"
        if not self.state_manager.is_step_completed(migration_id, step_name):
            self.state_manager.add_step(migration_id, step_name, "Share AMI with target account")
            self.state_manager.update_step_status(migration_id, step_name, MigrationStatus.IN_PROGRESS)
            
            print(f"\n🔗 Step 5: Sharing AMI with target account...")
            try:
                self.source_ec2.modify_image_attribute(
                    ImageId=source_ami_id,
                    LaunchPermission={'Add': [{'UserId': self.target_account_id}]}
                )
                
                self.state_manager.update_step_status(migration_id, step_name, MigrationStatus.COMPLETED)
                print(f"✅ AMI shared successfully")
            except Exception as e:
                error_msg = f"Failed to share AMI: {str(e)}"
                self.state_manager.update_step_status(migration_id, step_name, MigrationStatus.FAILED, error=error_msg)
                raise
        else:
            print(f"⏭️  Step 5: AMI sharing already completed (skipping)")
        
        # STEP 6: Copy AMI to Target
        step_name = "copy_ami"
        if not self.state_manager.is_step_completed(migration_id, step_name):
            self.state_manager.add_step(migration_id, step_name, "Copy AMI to target account")
            self.state_manager.update_step_status(migration_id, step_name, MigrationStatus.IN_PROGRESS)
            
            print(f"\n📋 Step 6: Copying AMI to target account...")
            try:
                target_ami_name = f"migrated-{instance_id}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
                copy_response = self.target_ec2.copy_image(
                    SourceImageId=source_ami_id,
                    SourceRegion=self.source_session.region_name,
                    Name=target_ami_name,
                    Description=f"Migrated from instance {instance_id}"
                )
                target_ami_id = copy_response['ImageId']
                
                # Track created resource
                self.state_manager.add_created_resource(
                    migration_id, "ami", target_ami_id,
                    {"name": target_ami_name, "account": "target"}
                )
                
                self.state_manager.update_step_status(
                    migration_id, step_name, MigrationStatus.COMPLETED,
                    data={"target_ami_id": target_ami_id, "target_ami_name": target_ami_name}
                )
                print(f"✅ AMI copied: {target_ami_id}")
            except Exception as e:
                error_msg = f"Failed to copy AMI: {str(e)}"
                self.state_manager.update_step_status(migration_id, step_name, MigrationStatus.FAILED, error=error_msg)
                raise
        else:
            print(f"⏭️  Step 6: AMI copy already completed (skipping)")
            copy_data = self.state_manager.get_step_data(migration_id, step_name)
            target_ami_id = copy_data['target_ami_id']
            print(f"   Using existing target AMI: {target_ami_id}")
        
        # STEP 7: Wait for Target AMI
        step_name = "wait_target_ami"
        if not self.state_manager.is_step_completed(migration_id, step_name):
            self.state_manager.add_step(migration_id, step_name, "Wait for target AMI to become available")
            self.state_manager.update_step_status(migration_id, step_name, MigrationStatus.IN_PROGRESS)
            
            print(f"\n⏳ Step 7: Waiting for target AMI to become available...")
            try:
                target_waiter = self.target_ec2.get_waiter('image_available')
                waiter_config = {'Delay': 15, 'MaxAttempts': 80}
                target_waiter.wait(ImageIds=[target_ami_id], WaiterConfig=waiter_config)
                
                self.state_manager.update_step_status(migration_id, step_name, MigrationStatus.COMPLETED)
                print(f"✅ Target AMI is available")
            except Exception as e:
                error_msg = f"Timeout waiting for target AMI: {str(e)}"
                self.state_manager.update_step_status(migration_id, step_name, MigrationStatus.FAILED, error=error_msg)
                raise
        else:
            print(f"⏭️  Step 7: Target AMI wait already completed (skipping)")
        
        # STEP 8: Replicate Security Groups
        step_name = "replicate_security_groups"
        if not self.state_manager.is_step_completed(migration_id, step_name):
            self.state_manager.add_step(migration_id, step_name, "Replicate security groups")
            self.state_manager.update_step_status(migration_id, step_name, MigrationStatus.IN_PROGRESS)
            
            print(f"\n🔒 Step 8: Replicating security groups...")
            try:
                # Get source security groups
                source_sg_ids = [sg['GroupId'] for sg in instance_info['security_groups']]
                
                # Replicate or get existing security groups
                sg_mapping = {}
                for source_sg_id in source_sg_ids:
                    target_sg_id = self._replicate_or_get_security_group(
                        source_sg_id, target_vpc_id
                    )
                    sg_mapping[source_sg_id] = target_sg_id
                
                self.state_manager.update_step_status(
                    migration_id, step_name, MigrationStatus.COMPLETED,
                    data={"sg_mapping": sg_mapping}
                )
                print(f"✅ Security groups replicated")
            except Exception as e:
                error_msg = f"Failed to replicate security groups: {str(e)}"
                self.state_manager.update_step_status(migration_id, step_name, MigrationStatus.FAILED, error=error_msg)
                raise
        else:
            print(f"⏭️  Step 8: Security groups already replicated (skipping)")
            sg_data = self.state_manager.get_step_data(migration_id, step_name)
            sg_mapping = sg_data['sg_mapping']
        
        # STEP 9: Launch Instance
        step_name = "launch_instance"
        if not self.state_manager.is_step_completed(migration_id, step_name):
            self.state_manager.add_step(migration_id, step_name, "Launch instance in target account")
            self.state_manager.update_step_status(migration_id, step_name, MigrationStatus.IN_PROGRESS)
            
            print(f"\n🚀 Step 9: Launching instance in target account...")
            try:
                target_sg_ids = list(sg_mapping.values())
                
                launch_params = {
                    'ImageId': target_ami_id,
                    'InstanceType': instance_info['instance_type'],
                    'SubnetId': target_subnet_id,
                    'SecurityGroupIds': target_sg_ids,
                    'KeyName': instance_info.get('key_name'),
                    'MinCount': 1,
                    'MaxCount': 1,
                    'TagSpecifications': [{
                        'ResourceType': 'instance',
                        'Tags': instance_info.get('tags', [])
                    }]
                }
                
                if instance_info['user_data']['exists']:
                    launch_params['UserData'] = instance_info['user_data']['data']
                
                launch_response = self.target_ec2.run_instances(**launch_params)
                target_instance_id = launch_response['Instances'][0]['InstanceId']
                
                # Track created resource
                self.state_manager.add_created_resource(
                    migration_id, "ec2_instance", target_instance_id,
                    {"account": "target", "vpc": target_vpc_id}
                )
                
                # Set target resource
                self.state_manager.set_target_resource(migration_id, target_instance_id)
                
                self.state_manager.update_step_status(
                    migration_id, step_name, MigrationStatus.COMPLETED,
                    data={"target_instance_id": target_instance_id}
                )
                print(f"✅ Instance launched: {target_instance_id}")
            except Exception as e:
                error_msg = f"Failed to launch instance: {str(e)}"
                self.state_manager.update_step_status(migration_id, step_name, MigrationStatus.FAILED, error=error_msg)
                raise
        else:
            print(f"⏭️  Step 9: Instance launch already completed (skipping)")
            launch_data = self.state_manager.get_step_data(migration_id, step_name)
            target_instance_id = launch_data['target_instance_id']
            print(f"   Using existing target instance: {target_instance_id}")
        
        # STEP 10: Wait for Instance
        step_name = "wait_instance"
        if not self.state_manager.is_step_completed(migration_id, step_name):
            self.state_manager.add_step(migration_id, step_name, "Wait for instance to be running")
            self.state_manager.update_step_status(migration_id, step_name, MigrationStatus.IN_PROGRESS)
            
            print(f"\n⏳ Step 10: Waiting for instance to be running...")
            try:
                waiter = self.target_ec2.get_waiter('instance_running')
                waiter.wait(InstanceIds=[target_instance_id])
                
                # Get instance details
                response = self.target_ec2.describe_instances(InstanceIds=[target_instance_id])
                instance = response['Reservations'][0]['Instances'][0]
                private_ip = instance.get('PrivateIpAddress')
                
                self.state_manager.update_step_status(
                    migration_id, step_name, MigrationStatus.COMPLETED,
                    data={"private_ip": private_ip, "state": "running"}
                )
                print(f"✅ Instance is running!")
                print(f"   Private IP: {private_ip}")
            except Exception as e:
                error_msg = f"Timeout waiting for instance: {str(e)}"
                self.state_manager.update_step_status(migration_id, step_name, MigrationStatus.FAILED, error=error_msg)
                raise
        else:
            print(f"⏭️  Step 10: Instance already running (skipping)")
            instance_data = self.state_manager.get_step_data(migration_id, step_name)
            print(f"   Private IP: {instance_data.get('private_ip')}")
        
        # Mark migration as completed
        self.state_manager.update_migration_status(migration_id, MigrationStatus.COMPLETED)
        
        print(f"\n✅ MIGRATION COMPLETE!")
        print(f"   Source Instance: {instance_id}")
        print(f"   Target Instance: {target_instance_id}")
        
        # Print summary
        self.state_manager.print_migration_summary(migration_id)
        
    except Exception as e:
        print(f"\n❌ Migration failed: {str(e)}")
        self.state_manager.update_migration_status(
            migration_id,
            MigrationStatus.FAILED,
            error=str(e)
        )
        self.state_manager.print_migration_summary(migration_id)
        raise
