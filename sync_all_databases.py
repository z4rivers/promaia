#!/usr/bin/env python3
"""
Minimal sync script for promaia databases - designed for cron job execution.

This script syncs all enabled databases in promaia and logs the results.
"""
import os
import sys
import subprocess
import logging
from datetime import datetime
from pathlib import Path

# Configure logging
LOG_FILE = Path(__file__).parent / "sync_cron.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()  # Also output to console for debugging
    ]
)
logger = logging.getLogger(__name__)

def run_sync():
    """Run the database sync using the maia CLI."""
    try:
        # Get the project directory
        project_dir = Path(__file__).parent.absolute()
        
        # Activate virtual environment and run sync
        venv_python = project_dir / "venv" / "bin" / "python"
        
        # Check if virtual environment exists
        if not venv_python.exists():
            # Fallback to system python3
            python_cmd = "python3"
            logger.warning(f"Virtual environment not found at {venv_python}, using system python3")
        else:
            python_cmd = str(venv_python)
            logger.info(f"Using virtual environment: {venv_python}")
        
        # Change to project directory
        os.chdir(project_dir)
        
        # Run the sync command
        logger.info("Starting database sync...")
        
        # Use the maia sync command which syncs all enabled databases
        cmd = [python_cmd, "-m", "promaia", "sync"]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=1800  # 30 minute timeout
        )
        
        # Log the results
        if result.returncode == 0:
            logger.info("Database sync completed successfully")
            if result.stdout:
                logger.info(f"Sync output:\n{result.stdout}")
        else:
            logger.error(f"Database sync failed with return code {result.returncode}")
            if result.stderr:
                logger.error(f"Error output:\n{result.stderr}")
            if result.stdout:
                logger.error(f"Standard output:\n{result.stdout}")
            
        return result.returncode == 0
        
    except subprocess.TimeoutExpired:
        logger.error("Database sync timed out after 30 minutes")
        return False
    except Exception as e:
        logger.error(f"Error running database sync: {e}")
        return False

def main():
    """Main entry point for the sync script."""
    logger.info("=" * 60)
    logger.info("PROMAIA DATABASE SYNC STARTED")
    logger.info(f"Timestamp: {datetime.now().isoformat()}")
    logger.info("=" * 60)
    
    try:
        success = run_sync()
        
        if success:
            logger.info("Database sync completed successfully")
            exit_code = 0
        else:
            logger.error("Database sync failed")
            exit_code = 1
            
    except KeyboardInterrupt:
        logger.warning("Database sync interrupted by user")
        exit_code = 130
    except Exception as e:
        logger.error(f"Unexpected error during sync: {e}")
        exit_code = 1
    
    logger.info("=" * 60)
    logger.info("PROMAIA DATABASE SYNC FINISHED")
    logger.info(f"Exit code: {exit_code}")
    logger.info("=" * 60)
    
    sys.exit(exit_code)

if __name__ == "__main__":
    main()

