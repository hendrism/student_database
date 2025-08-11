#!/usr/bin/env python3
"""
Student Database Management Script for macOS
Handles setup, backups, and maintenance tasks.
"""

import os
import sys
import shutil
import sqlite3
import subprocess
from datetime import datetime
from pathlib import Path
import argparse
import json

class StudentDBManager:
    def __init__(self):
        self.app_dir = Path(__file__).parent.absolute()
        self.instance_dir = self.app_dir / "instance"
        self.backup_dir = self.app_dir / "backups"
        self.venv_dir = self.app_dir / "venv"
        self.db_path = self.instance_dir / "student_database.db"
        
    def setup(self):
        """Complete setup for macOS."""
        print("🏥 Setting up Student Database on macOS...")
        
        # Create directories
        self.instance_dir.mkdir(exist_ok=True)
        self.backup_dir.mkdir(exist_ok=True)
        
        # Set secure permissions
        os.chmod(self.instance_dir, 0o700)
        os.chmod(self.backup_dir, 0o700)
        
        # Create virtual environment
        if not self.venv_dir.exists():
            print("📦 Creating virtual environment...")
            subprocess.run([sys.executable, "-m", "venv", str(self.venv_dir)])
        
        # Activate venv and install requirements
        pip_path = self.venv_dir / "bin" / "pip"
        if not pip_path.exists():
            print("❌ Failed to create virtual environment")
            return False
            
        print("📥 Installing dependencies...")
        subprocess.run([str(pip_path), "install", "-r", "requirements.txt"])
        
        # Create environment file
        env_file = self.app_dir / ".env"
        if not env_file.exists():
            print("⚙️  Creating environment configuration...")
            with open(env_file, 'w') as f:
                f.write(f"""# Student Database Configuration
FLASK_ENV=development
SECRET_KEY={self._generate_secret_key()}
DATABASE_URL=sqlite:///{self.db_path}
""")
            os.chmod(env_file, 0o600)
        
        # Initialize database
        python_path = self.venv_dir / "bin" / "python"
        print("🗄️  Initializing database...")
        env = os.environ.copy()
        env['FLASK_APP'] = 'app.py'
        subprocess.run([str(python_path), "-m", "flask", "db", "upgrade"], env=env)
        
        # Create launch script
        self._create_launch_script()
        
        print("✅ Setup complete!")
        print(f"📍 Database location: {self.db_path}")
        print(f"📁 Backup location: {self.backup_dir}")
        print("🚀 Run './launch.sh' to start the application")
        
        return True
    
    def backup(self):
        """Create encrypted backup of the database."""
        if not self.db_path.exists():
            print("❌ No database found to backup")
            return False
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"student_db_backup_{timestamp}.db"
        backup_path = self.backup_dir / backup_name
        
        print(f"💾 Creating backup: {backup_name}")
        
        # Create backup using sqlite3 backup API (safer than file copy)
        try:
            # Connect to source database
            source = sqlite3.connect(str(self.db_path))
            
            # Create backup
            with sqlite3.connect(str(backup_path)) as backup:
                source.backup(backup)
            
            source.close()
            
            # Secure permissions
            os.chmod(backup_path, 0o600)
            
            # Keep only last 10 backups
            self._cleanup_old_backups()
            
            print(f"✅ Backup created: {backup_path}")
            return True
            
        except Exception as e:
            print(f"❌ Backup failed: {e}")
            return False
    
    def restore(self, backup_file):
        """Restore from backup."""
        backup_path = Path(backup_file)
        if not backup_path.exists():
            backup_path = self.backup_dir / backup_file
            
        if not backup_path.exists():
            print(f"❌ Backup file not found: {backup_file}")
            return False
            
        print(f"🔄 Restoring from: {backup_path}")
        
        # Create backup of current database first
        if self.db_path.exists():
            current_backup = self.db_path.with_suffix(f".db.pre_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
            shutil.copy2(self.db_path, current_backup)
            print(f"💾 Current database backed up to: {current_backup}")
        
        try:
            shutil.copy2(backup_path, self.db_path)
            os.chmod(self.db_path, 0o600)
            print("✅ Database restored successfully")
            return True
        except Exception as e:
            print(f"❌ Restore failed: {e}")
            return False
    
    def status(self):
        """Show system status."""
        print("🏥 Student Database Status")
        print("=" * 40)
        
        print(f"📍 Application Directory: {self.app_dir}")
        print(f"🗄️  Database Path: {self.db_path}")
        print(f"📊 Database Exists: {'Yes' if self.db_path.exists() else 'No'}")
        
        if self.db_path.exists():
            stat = self.db_path.stat()
            print(f"📏 Database Size: {stat.st_size / 1024 / 1024:.1f} MB")
            print(f"🕒 Last Modified: {datetime.fromtimestamp(stat.st_mtime)}")
            
        print(f"🔧 Virtual Environment: {'Yes' if self.venv_dir.exists() else 'No'}")
        
        # List recent backups
        if self.backup_dir.exists():
            backups = sorted(self.backup_dir.glob("student_db_backup_*.db"), reverse=True)[:5]
            print(f"💾 Recent Backups ({len(backups)}):")
            for backup in backups:
                size = backup.stat().st_size / 1024 / 1024
                date = datetime.fromtimestamp(backup.stat().st_mtime)
                print(f"   • {backup.name} ({size:.1f}MB, {date.strftime('%Y-%m-%d %H:%M')})")
    
    def _generate_secret_key(self):
        """Generate a secure secret key."""
        import secrets
        return secrets.token_hex(32)
    
    def _cleanup_old_backups(self, keep=10):
        """Keep only the most recent backups."""
        backups = sorted(self.backup_dir.glob("student_db_backup_*.db"))
        if len(backups) > keep:
            for backup in backups[:-keep]:
                backup.unlink()
                print(f"🗑️  Removed old backup: {backup.name}")
    
    def _create_launch_script(self):
        """Create macOS launch script."""
        launch_script = self.app_dir / "launch.sh"
        python_path = self.venv_dir / "bin" / "python"
        
        script_content = f"""#!/bin/bash
# Student Database Launcher for macOS

cd "{self.app_dir}"
source "{self.venv_dir}/bin/activate"

echo "🏥 Starting Student Database..."
echo "📍 Access at: http://127.0.0.1:5000"
echo "⏹️  Press Ctrl+C to stop"
echo ""

export FLASK_ENV=development
export FLASK_APP=app.py

"{python_path}" app.py
"""
        
        with open(launch_script, 'w') as f:
            f.write(script_content)
        
        os.chmod(launch_script, 0o755)

def main():
    parser = argparse.ArgumentParser(description="Student Database Manager for macOS")
    parser.add_argument('command', choices=['setup', 'backup', 'restore', 'status'], 
                       help='Command to execute')
    parser.add_argument('--file', help='Backup file for restore command')
    
    args = parser.parse_args()
    manager = StudentDBManager()
    
    if args.command == 'setup':
        manager.setup()
    elif args.command == 'backup':
        manager.backup()
    elif args.command == 'restore':
        if not args.file:
            print("❌ Please specify backup file with --file")
            sys.exit(1)
        manager.restore(args.file)
    elif args.command == 'status':
        manager.status()

if __name__ == "__main__":
    main()