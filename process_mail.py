#!/usr/bin/env python3
"""
Minimal mail processing script for promaia - designed for cron job execution.

This script processes pending emails in promaia and logs the results.
"""
import os
import sys
import subprocess
import logging
from datetime import datetime
from pathlib import Path

# Configure logging
LOG_FILE = Path(__file__).parent / "mail_cron.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()  # Also output to console for debugging
    ]
)
logger = logging.getLogger(__name__)

def run_mail_processing():
    """Run the mail processing using the maia CLI."""
    try:
        # Get the project directory
        project_dir = Path(__file__).parent.absolute()
        
        # Activate virtual environment and run mail processing
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
        
        # Run the mail processing command
        logger.info("Starting mail processing...")
        
        # Use the maia mail -p command to process pending emails
        cmd = [python_cmd, "-m", "promaia", "mail", "-p"]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=1800  # 30 minute timeout
        )
        
        # Log the results
        if result.returncode == 0:
            logger.info("Mail processing completed successfully")
            if result.stdout:
                logger.info(f"Processing output:\n{result.stdout}")
        else:
            logger.error(f"Mail processing failed with return code {result.returncode}")
            if result.stderr:
                logger.error(f"Error output:\n{result.stderr}")
            if result.stdout:
                logger.error(f"Standard output:\n{result.stdout}")
            
        return result.returncode == 0
        
    except subprocess.TimeoutExpired:
        logger.error("Mail processing timed out after 30 minutes")
        return False
    except Exception as e:
        logger.error(f"Error running mail processing: {e}")
        return False

def main():
    """Main entry point for the mail processing script."""
    logger.info("=" * 60)
    logger.info("PROMAIA MAIL PROCESSING STARTED")
    logger.info(f"Timestamp: {datetime.now().isoformat()}")
    logger.info("=" * 60)
    
    try:
        success = run_mail_processing()
        
        if success:
            logger.info("Mail processing completed successfully")
            exit_code = 0
        else:
            logger.error("Mail processing failed")
            exit_code = 1
            
    except KeyboardInterrupt:
        logger.warning("Mail processing interrupted by user")
        exit_code = 130
    except Exception as e:
        logger.error(f"Unexpected error during mail processing: {e}")
        exit_code = 1
    
    logger.info("=" * 60)
    logger.info("PROMAIA MAIL PROCESSING FINISHED")
    logger.info(f"Exit code: {exit_code}")
    logger.info("=" * 60)
    
    sys.exit(exit_code)

if __name__ == "__main__":
    main()



