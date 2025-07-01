"""
CLI Commands for JSON Editing and Syncing

Provides commands for safely editing local Notion JSON files and syncing changes back.
"""

import json
import click
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt, Confirm
from rich.tree import Tree
from datetime import datetime, timedelta

from promaia.storage.json_editor import NotionJSONEditor
from promaia.storage.notion_sync import NotionSyncer
from promaia.utils.config import get_config

console = Console(width=9999, soft_wrap=False)

@click.group()
def edit():
    """Commands for editing local JSON files and syncing with Notion"""
    pass

@edit.command()
@click.argument('content_type')
@click.option('--page-id', help='Specific page ID to edit')
@click.option('--title-filter', help='Filter pages by title')
def list_pages(content_type, page_id, title_filter):
    """List pages available for editing"""
    try:
        editor = NotionJSONEditor()
        content_dir = editor._get_content_type_dir(content_type)
        
        if not os.path.exists(content_dir):
            console.print(f"[red]No data found for content type: {content_type}[/red]")
            return
        
        table = Table(title=f"Pages in {content_type}")
        table.add_column("Title", style="cyan")
        table.add_column("Page ID", style="green")
        table.add_column("Last Modified", style="yellow")
        table.add_column("Sync Status", style="magenta")
        
        import os
        for filename in sorted(os.listdir(content_dir)):
            if filename.endswith('.json') and 'backup' not in filename:
                try:
                    with open(os.path.join(content_dir, filename), 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    title = data.get('title', 'Unknown')
                    page_id_val = data.get('page_id', 'Unknown')
                    saved_at = data.get('saved_at', 'Unknown')
                    last_synced = data.get('last_synced', 'Never')
                    
                    # Apply filters
                    if page_id and page_id not in page_id_val:
                        continue
                    if title_filter and title_filter.lower() not in title.lower():
                        continue
                    
                    # Determine sync status
                    if last_synced == 'Never':
                        sync_status = "[red]Not synced[/red]"
                    else:
                        saved_dt = datetime.fromisoformat(saved_at)
                        synced_dt = datetime.fromisoformat(last_synced)
                        if saved_dt > synced_dt:
                            sync_status = "[yellow]Modified[/yellow]"
                        else:
                            sync_status = "[green]Synced[/green]"
                    
                    table.add_row(title[:50], page_id_val, saved_at[:19], sync_status)
                    
                except Exception as e:
                    console.print(f"[red]Error reading {filename}: {e}[/red]")
        
        console.print(table)
        
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")

@edit.command()
@click.argument('content_type')
@click.argument('page_id')
@click.option('--title', help='New title for the page')
@click.option('--property', 'properties', multiple=True, help='Update property: --property "Name=Value"')
@click.option('--add-paragraph', help='Add a paragraph with this text')
@click.option('--add-heading', help='Add a heading with this text')
@click.option('--heading-level', default=1, help='Heading level (1-3)')
@click.option('--backup/--no-backup', default=True, help='Create backup before editing')
def update(content_type, page_id, title, properties, add_paragraph, add_heading, heading_level, backup):
    """Update a page's properties and content"""
    try:
        editor = NotionJSONEditor()
        
        # Load the page
        data = editor.load_page(content_type, page_id)
        console.print(f"[green]Loaded page: {data['title']}[/green]")
        
        # Update title if provided
        if title:
            data = editor.update_title(data, title)
            console.print(f"[cyan]Updated title to: {title}[/cyan]")
        
        # Update properties if provided
        for prop in properties:
            if '=' not in prop:
                console.print(f"[red]Invalid property format: {prop}. Use 'Name=Value'[/red]")
                continue
            
            prop_name, prop_value = prop.split('=', 1)
            
            # Handle different property types (simplified)
            if prop_name in data['notion_data']['properties']:
                prop_type = data['notion_data']['properties'][prop_name]['type']
                
                if prop_type == 'select':
                    prop_value = {"name": prop_value, "color": "default"}
                elif prop_type == 'rich_text':
                    prop_value = [{
                        "type": "text",
                        "text": {"content": prop_value},
                        "plain_text": prop_value
                    }]
            else:
                # Default to rich_text for new properties
                prop_type = 'rich_text'
                prop_value = [{
                    "type": "text", 
                    "text": {"content": prop_value},
                    "plain_text": prop_value
                }]
            
            data = editor.update_property(data, prop_name, prop_value, prop_type)
            console.print(f"[cyan]Updated property {prop_name}: {str(prop_value)[:50]}[/cyan]")
        
        # Add content blocks if provided
        if add_paragraph:
            block = editor.create_paragraph_block(add_paragraph)
            data = editor.add_content_block(data, block)
            console.print(f"[cyan]Added paragraph: {add_paragraph[:50]}[/cyan]")
        
        if add_heading:
            block = editor.create_heading_block(add_heading, heading_level)
            data = editor.add_content_block(data, block)
            console.print(f"[cyan]Added heading {heading_level}: {add_heading[:50]}[/cyan]")
        
        # Save the changes
        filepath = editor.save_page(data, backup=backup)
        console.print(f"[green]Saved changes to: {filepath}[/green]")
        
        # Show changes summary
        changes = editor.get_changes_summary()
        if changes:
            console.print("\n[bold]Changes made:[/bold]")
            for change in changes:
                console.print(f"  • {change['description']}")
        
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")

@edit.command()
@click.argument('content_type')
@click.argument('page_id')
def show(content_type, page_id):
    """Show detailed information about a page"""
    try:
        editor = NotionJSONEditor()
        data = editor.load_page(content_type, page_id)
        
        console.print(f"[bold cyan]Page: {data['title']}[/bold cyan]")
        console.print(f"[dim]ID: {data['page_id']}[/dim]")
        console.print(f"[dim]Type: {data['content_type']}[/dim]")
        console.print(f"[dim]Last saved: {data['saved_at']}[/dim]")
        console.print(f"[dim]Last synced: {data.get('last_synced', 'Never')}[/dim]")
        
        # Show properties
        console.print("\n[bold]Properties:[/bold]")
        props = data['notion_data']['properties']
        for name, prop in props.items():
            prop_type = prop.get('type', 'unknown')
            value = prop.get(prop_type, 'N/A')
            
            # Format value based on type
            if prop_type == 'title' and isinstance(value, list) and value:
                display_value = value[0].get('plain_text', 'N/A')
            elif prop_type == 'rich_text' and isinstance(value, list) and value:
                display_value = value[0].get('plain_text', 'N/A')
            elif prop_type == 'select' and isinstance(value, dict):
                display_value = value.get('name', 'N/A')
            elif prop_type == 'relation' and isinstance(value, list):
                display_value = f"{len(value)} related items"
            else:
                display_value = str(value)[:100]
            
            console.print(f"  [cyan]{name}[/cyan] ({prop_type}): {display_value}")
        
        # Show content summary
        content = data['notion_data']['content']
        console.print(f"\n[bold]Content blocks: {len(content)}[/bold]")
        
        if content:
            tree = Tree("Content Structure")
            for i, block in enumerate(content[:10]):  # Show first 10 blocks
                block_type = block.get('type', 'unknown')
                block_content = ""
                
                if block_type == 'paragraph' and 'paragraph' in block:
                    rich_text = block['paragraph'].get('rich_text', [])
                    if rich_text:
                        block_content = rich_text[0].get('plain_text', '')[:50]
                elif block_type.startswith('heading_') and block_type in block:
                    rich_text = block[block_type].get('rich_text', [])
                    if rich_text:
                        block_content = rich_text[0].get('plain_text', '')[:50]
                
                tree.add(f"[{i}] {block_type}: {block_content}")
            
            if len(content) > 10:
                tree.add(f"... and {len(content) - 10} more blocks")
            
            console.print(tree)
        
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")

@edit.command()
@click.argument('content_type', required=False)
@click.option('--page-id', help='Sync specific page only')
@click.option('--force', is_flag=True, help='Force sync even if conflicts detected')
@click.option('--dry-run', is_flag=True, help='Show what would be synced without actually syncing')
def sync(content_type, page_id, force, dry_run):
    """Sync local changes back to Notion"""
    try:
        syncer = NotionSyncer()
        
        if dry_run:
            console.print("[yellow]DRY RUN - No changes will be made[/yellow]\n")
            
            if content_type:
                plan = syncer.create_sync_plan(content_type)
            else:
                plan = syncer.create_sync_plan()
            
            if not plan:
                console.print("[green]No pages need syncing[/green]")
                return
            
            console.print("[bold]Sync Plan:[/bold]")
            for ct, pages in plan.items():
                console.print(f"\n[cyan]{ct}:[/cyan]")
                for page_id in pages:
                    console.print(f"  • {page_id}")
            return
        
        if page_id:
            # Sync single page
            if not content_type:
                console.print("[red]Content type required when syncing specific page[/red]")
                return
            
            console.print(f"[yellow]Syncing page {page_id} in {content_type}...[/yellow]")
            result = syncer.sync_page(content_type, page_id, force=force)
            
            if result.success:
                console.print(f"[green]✓ Successfully synced {result.changes_applied} changes[/green]")
            else:
                console.print(f"[red]✗ Sync failed[/red]")
                for error in result.errors:
                    console.print(f"  [red]Error: {error}[/red]")
                for conflict in result.conflicts:
                    console.print(f"  [yellow]Conflict: {conflict}[/yellow]")
        
        elif content_type:
            # Sync entire database
            console.print(f"[yellow]Syncing all pages in {content_type}...[/yellow]")
            results = syncer.sync_database(content_type, force=force)
            
            success_count = sum(1 for r in results if r.success)
            total_count = len(results)
            
            console.print(f"\n[bold]Sync Results: {success_count}/{total_count} successful[/bold]")
            
            for result in results:
                if result.success:
                    console.print(f"[green]✓ {result.page_id}: {result.changes_applied} changes[/green]")
                else:
                    console.print(f"[red]✗ {result.page_id}: Failed[/red]")
                    for error in result.errors[:2]:  # Show first 2 errors
                        console.print(f"    [red]{error}[/red]")
        
        else:
            # Sync all databases
            config = get_config()
            all_results = []
            
            for ct in config.keys():
                console.print(f"[yellow]Syncing {ct}...[/yellow]")
                results = syncer.sync_database(ct, force=force)
                all_results.extend(results)
            
            success_count = sum(1 for r in all_results if r.success)
            total_count = len(all_results)
            
            console.print(f"\n[bold]Total Sync Results: {success_count}/{total_count} successful[/bold]")
        
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")

@edit.command()
@click.argument('content_type', required=False)
def status(content_type):
    """Show sync status of local pages"""
    try:
        syncer = NotionSyncer()
        
        if content_type:
            content_types = [content_type]
        else:
            config = get_config()
            content_types = list(config.keys())
        
        table = Table(title="Sync Status")
        table.add_column("Database", style="cyan")
        table.add_column("Modified Pages", style="yellow")
        table.add_column("Status", style="green")
        
        for ct in content_types:
            modified = syncer.get_modified_pages(ct)
            if modified:
                status_text = f"[yellow]{len(modified)} need sync[/yellow]"
                pages_text = ", ".join(modified[:3])
                if len(modified) > 3:
                    pages_text += f" and {len(modified) - 3} more"
            else:
                status_text = "[green]All synced[/green]"
                pages_text = "None"
            
            table.add_row(ct, pages_text, status_text)
        
        console.print(table)
        
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")

if __name__ == '__main__':
    edit() 