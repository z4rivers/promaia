"""
CLI module for Maia.
"""
from .database_commands import add_database_commands
from .conversion_commands import add_conversion_commands
# from .edit_commands import edit  # Using argparse handlers in main CLI instead

__all__ = ['add_database_commands', 'add_conversion_commands']