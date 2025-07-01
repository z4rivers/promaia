"""
Test utilities to handle common test setup and cleanup issues.
"""
import os
import shutil
import glob
import re
from pathlib import Path


def cleanup_numbered_data_directories(project_root=None):
    """
    Clean up any numbered data directories that may have been created due to filesystem conflicts.
    
    This function looks for directories like 'data 2', 'data 3', etc. and removes them
    after optionally backing up their content.
    
    Args:
        project_root: Path to project root. If None, uses current directory.
        
    Returns:
        list: Paths of directories that were cleaned up
    """
    if project_root is None:
        project_root = Path.cwd()
    else:
        project_root = Path(project_root)
    
    # Pattern to match numbered data directories
    data_pattern = project_root / "data *"
    numbered_dirs = list(project_root.glob("data [0-9]*"))
    
    cleaned_up = []
    
    for numbered_dir in numbered_dirs:
        if numbered_dir.is_dir():
            print(f"Found numbered data directory: {numbered_dir}")
            
            # Check if main data directory exists
            main_data = project_root / "data"
            
            if not main_data.exists():
                # If no main data directory, rename this one
                print(f"No main data directory found. Renaming {numbered_dir} to data")
                numbered_dir.rename(main_data)
                cleaned_up.append(str(numbered_dir))
            else:
                # Main data exists, check which has more content
                try:
                    main_files = len(list(main_data.rglob("*"))) if main_data.exists() else 0
                    numbered_files = len(list(numbered_dir.rglob("*")))
                    
                    if numbered_files > main_files:
                        print(f"Numbered directory has more files ({numbered_files} vs {main_files})")
                        print(f"Backing up main data and replacing with {numbered_dir}")
                        
                        # Backup main data
                        backup_name = main_data.parent / f"data_backup_{numbered_dir.name.replace(' ', '_')}"
                        if main_data.exists():
                            shutil.move(str(main_data), str(backup_name))
                        
                        # Move numbered to main
                        numbered_dir.rename(main_data)
                        print(f"Original data backed up as: {backup_name}")
                    else:
                        print(f"Main data has more files ({main_files} vs {numbered_files}), removing numbered directory")
                        shutil.rmtree(numbered_dir)
                    
                    cleaned_up.append(str(numbered_dir))
                    
                except Exception as e:
                    print(f"Error processing {numbered_dir}: {e}")
    
    return cleaned_up


def ensure_single_data_directory(project_root=None):
    """
    Ensure there's only one data directory and clean up any numbered variants.
    
    Args:
        project_root: Path to project root. If None, uses current directory.
        
    Returns:
        str: Path to the final data directory
    """
    if project_root is None:
        project_root = Path.cwd()
    else:
        project_root = Path(project_root)
    
    main_data = project_root / "data"
    
    # First, clean up numbered directories
    cleaned_up = cleanup_numbered_data_directories(project_root)
    
    if cleaned_up:
        print(f"Cleaned up {len(cleaned_up)} numbered data directories")
    
    # Verify we have a main data directory
    if not main_data.exists():
        print("Warning: No data directory found after cleanup")
        return None
    
    return str(main_data)


def robust_directory_restore(source_path, target_path, max_retries=3):
    """
    Robustly restore a directory from backup, handling filesystem conflicts.
    
    Args:
        source_path: Path to source directory (backup)
        target_path: Path to target directory
        max_retries: Maximum number of retry attempts
        
    Returns:
        bool: True if successful, False otherwise
    """
    import time
    
    source_path = Path(source_path)
    target_path = Path(target_path)
    
    if not source_path.exists():
        print(f"Source path does not exist: {source_path}")
        return False
    
    for attempt in range(max_retries):
        try:
            # Remove target if it exists
            if target_path.exists():
                if target_path.is_dir():
                    shutil.rmtree(target_path)
                else:
                    target_path.unlink()
            
            # Copy source to target
            shutil.copytree(str(source_path), str(target_path))
            
            # Verify copy was successful
            if target_path.exists():
                return True
            
        except (OSError, IOError) as e:
            if attempt < max_retries - 1:
                print(f"Attempt {attempt + 1} failed: {e}. Retrying in 0.5 seconds...")
                time.sleep(0.5)
            else:
                print(f"Failed to restore directory after {max_retries} attempts: {e}")
                return False 