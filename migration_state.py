#!/usr/bin/env python3
"""
Migration State Management
Tracks migration progress and enables resume functionality
"""

import json
import os
from datetime import datetime
from typing import Dict, Any, Optional, List
from enum import Enum


class DateTimeEncoder(json.JSONEncoder):
    """Custom JSON encoder for datetime objects"""
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


class ResourceType(Enum):
    """Types of resources that can be migrated"""
    EC2_INSTANCE = "ec2_instance"
    RDS_DATABASE = "rds_database"
    VPC = "vpc"
    SUBNET = "subnet"
    SECURITY_GROUP = "security_group"
    AMI = "ami"
    SNAPSHOT = "snapshot"
    ELASTIC_IP = "elastic_ip"


class MigrationStatus(Enum):
    """Status of a migration step"""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class MigrationStateManager:
    """Manages migration state and enables resume functionality"""
    
    def __init__(self, state_file_path: str = "migration_state.json"):
        """
        Initialize the state manager
        
        Args:
            state_file_path: Path to the state file
        """
        self.state_file_path = state_file_path
        self.state = self._load_state()
    
    def _load_state(self) -> Dict[str, Any]:
        """Load state from file or create new state"""
        if os.path.exists(self.state_file_path):
            try:
                with open(self.state_file_path, 'r') as f:
                    state = json.load(f)
                    print(f"📂 Loaded existing migration state from {self.state_file_path}")
                    return state
            except Exception as e:
                print(f"⚠️  Error loading state file: {e}")
                print(f"   Creating new state file")
        
        # Create new state
        return {
            "version": "1.0",
            "created_at": datetime.now().isoformat(),
            "last_updated": datetime.now().isoformat(),
            "migrations": {}
        }
    
    def _save_state(self):
        """Save state to file"""
        try:
            self.state["last_updated"] = datetime.now().isoformat()
            
            # Create backup of existing state
            if os.path.exists(self.state_file_path):
                backup_path = f"{self.state_file_path}.backup"
                with open(self.state_file_path, 'r') as f:
                    backup_data = f.read()
                with open(backup_path, 'w') as f:
                    f.write(backup_data)
            
            # Write new state
            with open(self.state_file_path, 'w') as f:
                json.dump(self.state, f, indent=2, cls=DateTimeEncoder)
            
        except Exception as e:
            print(f"❌ Error saving state file: {e}")
            raise
    
    def get_migration_id(self, resource_type: ResourceType, source_id: str) -> str:
        """Generate a unique migration ID"""
        return f"{resource_type.value}:{source_id}"
    
    def initialize_migration(
        self,
        resource_type: ResourceType,
        source_id: str,
        source_metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Initialize a new migration or return existing migration ID
        
        Args:
            resource_type: Type of resource being migrated
            source_id: Source resource identifier
            source_metadata: Additional metadata about the source resource
            
        Returns:
            Migration ID
        """
        migration_id = self.get_migration_id(resource_type, source_id)
        
        if migration_id not in self.state["migrations"]:
            self.state["migrations"][migration_id] = {
                "resource_type": resource_type.value,
                "source_id": source_id,
                "source_metadata": source_metadata or {},
                "target_id": None,
                "status": MigrationStatus.NOT_STARTED.value,
                "steps": {},
                "created_at": datetime.now().isoformat(),
                "started_at": None,
                "completed_at": None,
                "error": None,
                "resources_created": []
            }
            self._save_state()
            print(f"📝 Initialized migration: {migration_id}")
        else:
            print(f"📝 Found existing migration state: {migration_id}")
        
        return migration_id
    
    def update_migration_status(
        self,
        migration_id: str,
        status: MigrationStatus,
        error: Optional[str] = None
    ):
        """Update the overall migration status"""
        if migration_id not in self.state["migrations"]:
            raise ValueError(f"Migration {migration_id} not found")
        
        migration = self.state["migrations"][migration_id]
        migration["status"] = status.value
        
        if status == MigrationStatus.IN_PROGRESS and not migration["started_at"]:
            migration["started_at"] = datetime.now().isoformat()
        
        if status == MigrationStatus.COMPLETED:
            migration["completed_at"] = datetime.now().isoformat()
        
        if error:
            migration["error"] = error
        
        self._save_state()
    
    def add_step(
        self,
        migration_id: str,
        step_name: str,
        step_description: str
    ):
        """Add a new step to the migration"""
        if migration_id not in self.state["migrations"]:
            raise ValueError(f"Migration {migration_id} not found")
        
        migration = self.state["migrations"][migration_id]
        
        if step_name not in migration["steps"]:
            migration["steps"][step_name] = {
                "description": step_description,
                "status": MigrationStatus.NOT_STARTED.value,
                "started_at": None,
                "completed_at": None,
                "data": {},
                "error": None
            }
            self._save_state()
    
    def update_step_status(
        self,
        migration_id: str,
        step_name: str,
        status: MigrationStatus,
        data: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None
    ):
        """Update the status of a migration step"""
        if migration_id not in self.state["migrations"]:
            raise ValueError(f"Migration {migration_id} not found")
        
        migration = self.state["migrations"][migration_id]
        
        # Auto-create step if it doesn't exist
        if step_name not in migration["steps"]:
            migration["steps"][step_name] = {
                "description": step_name,
                "status": MigrationStatus.NOT_STARTED.value,
                "started_at": None,
                "completed_at": None,
                "data": {},
                "error": None
            }
        
        step = migration["steps"][step_name]
        step["status"] = status.value
        
        if status == MigrationStatus.IN_PROGRESS and not step["started_at"]:
            step["started_at"] = datetime.now().isoformat()
        
        if status in [MigrationStatus.COMPLETED, MigrationStatus.FAILED]:
            step["completed_at"] = datetime.now().isoformat()
        
        if data:
            step["data"].update(data)
        
        if error:
            step["error"] = error
        
        self._save_state()
    
    def get_step_status(self, migration_id: str, step_name: str) -> Optional[MigrationStatus]:
        """Get the status of a specific step"""
        if migration_id not in self.state["migrations"]:
            return None
        
        migration = self.state["migrations"][migration_id]
        
        if step_name not in migration["steps"]:
            return None
        
        status_value = migration["steps"][step_name]["status"]
        return MigrationStatus(status_value)
    
    def get_step_data(self, migration_id: str, step_name: str) -> Dict[str, Any]:
        """Get the data stored for a specific step"""
        if migration_id not in self.state["migrations"]:
            return {}
        
        migration = self.state["migrations"][migration_id]
        
        if step_name not in migration["steps"]:
            return {}
        
        return migration["steps"][step_name].get("data", {})
    
    def is_step_completed(self, migration_id: str, step_name: str) -> bool:
        """Check if a step is already completed"""
        status = self.get_step_status(migration_id, step_name)
        return status == MigrationStatus.COMPLETED
    
    def add_created_resource(
        self,
        migration_id: str,
        resource_type,  # Can be str or ResourceType
        resource_id: str,
        resource_metadata: Optional[Dict[str, Any]] = None
    ):
        """Track a resource created during migration for cleanup if needed"""
        if migration_id not in self.state["migrations"]:
            raise ValueError(f"Migration {migration_id} not found")
        
        migration = self.state["migrations"][migration_id]
        
        # Handle ResourceType enum or string
        resource_type_str = resource_type.value if isinstance(resource_type, ResourceType) else resource_type
        
        resource_entry = {
            "type": resource_type_str,
            "id": resource_id,
            "created_at": datetime.now().isoformat(),
            "metadata": resource_metadata or {}
        }
        
        migration["resources_created"].append(resource_entry)
        self._save_state()
    
    def set_target_resource(self, migration_id: str, target_id: str):
        """Set the target resource ID"""
        if migration_id not in self.state["migrations"]:
            raise ValueError(f"Migration {migration_id} not found")
        
        self.state["migrations"][migration_id]["target_id"] = target_id
        self._save_state()
    
    def get_migration_info(self, migration_id: str) -> Optional[Dict[str, Any]]:
        """Get complete migration information"""
        return self.state["migrations"].get(migration_id)
    
    def get_all_migrations(self) -> Dict[str, Any]:
        """Get all migrations"""
        return self.state["migrations"]
    
    def get_migrations_by_status(self, status: MigrationStatus) -> List[Dict[str, Any]]:
        """Get all migrations with a specific status"""
        return [
            {"id": mid, **mdata}
            for mid, mdata in self.state["migrations"].items()
            if mdata["status"] == status.value
        ]
    
    def get_incomplete_migrations(self, resource_type: ResourceType, source_id: str) -> List[str]:
        """Get incomplete migrations for a specific resource"""
        incomplete_migrations = []
        for mid, mdata in self.state["migrations"].items():
            if (mdata.get("source_id") == source_id and 
                mdata.get("resource_type") == resource_type.value and
                mdata.get("status") in [MigrationStatus.IN_PROGRESS.value, MigrationStatus.FAILED.value]):
                incomplete_migrations.append(mid)
        return incomplete_migrations
    
    def print_migration_summary(self, migration_id: Optional[str] = None):
        """Print a summary of migration(s)"""
        if migration_id:
            migrations = {migration_id: self.state["migrations"].get(migration_id)}
        else:
            migrations = self.state["migrations"]
        
        print("\n" + "="*80)
        print("MIGRATION STATE SUMMARY")
        print("="*80)
        
        for mid, mdata in migrations.items():
            if mdata is None:
                continue
                
            print(f"\nMigration: {mid}")
            print(f"  Status: {mdata['status']}")
            print(f"  Source: {mdata['source_id']}")
            print(f"  Target: {mdata.get('target_id', 'Not set')}")
            print(f"  Created: {mdata['created_at']}")
            
            if mdata.get('completed_at'):
                print(f"  Completed: {mdata['completed_at']}")
            
            if mdata.get('error'):
                print(f"  Error: {mdata['error']}")
            
            print(f"\n  Steps ({len(mdata['steps'])} total):")
            for step_name, step_data in mdata['steps'].items():
                status_icon = {
                    MigrationStatus.NOT_STARTED.value: "⏸️",
                    MigrationStatus.IN_PROGRESS.value: "⏳",
                    MigrationStatus.COMPLETED.value: "✅",
                    MigrationStatus.FAILED.value: "❌",
                    MigrationStatus.SKIPPED.value: "⏭️"
                }.get(step_data['status'], "❓")
                
                print(f"    {status_icon} {step_name}: {step_data['status']}")
                if step_data.get('error'):
                    print(f"       Error: {step_data['error']}")
            
            if mdata['resources_created']:
                print(f"\n  Resources Created ({len(mdata['resources_created'])}):")
                for resource in mdata['resources_created']:
                    print(f"    • {resource['type']}: {resource['id']}")
        
        print("\n" + "="*80 + "\n")
    
    def clean_completed_migrations(self, older_than_days: int = 7):
        """Remove completed migrations older than specified days"""
        from datetime import timedelta
        
        cutoff_date = datetime.now() - timedelta(days=older_than_days)
        migrations_to_remove = []
        
        for mid, mdata in self.state["migrations"].items():
            if mdata["status"] == MigrationStatus.COMPLETED.value:
                completed_at = datetime.fromisoformat(mdata.get("completed_at", mdata["created_at"]))
                if completed_at < cutoff_date:
                    migrations_to_remove.append(mid)
        
        for mid in migrations_to_remove:
            del self.state["migrations"][mid]
        
        if migrations_to_remove:
            self._save_state()
            print(f"🧹 Cleaned up {len(migrations_to_remove)} completed migrations")
        
        return len(migrations_to_remove)
