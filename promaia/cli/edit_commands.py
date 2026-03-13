"""
CLI Commands for JSON Editing and Syncing

Provides handlers for safely editing local Notion JSON files and syncing changes back.
"""
import os
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.tree import Tree

from promaia.storage.json_editor import NotionJSONEditor
from promaia.storage.notion_sync import NotionSyncer
from promaia.utils.config import get_config


def handle_edit_list_pages(args):
    """Handle edit list-pages command"""
    console = Console(width=9999, soft_wrap=False)
    
    try:
        editor = NotionJSONEditor()
        pages = editor.list_pages(args.content_type, args.title_filter)
        
        if not pages:
            console.print(f"[red]No data found for content type: {args.content_type}[/red]")
            return
        
        table = Table(title=f"Pages in {args.content_type}")
        table.add_column("Title", style="cyan")
        table.add_column("Page ID", style="green")
        table.add_column("Last Modified", style="yellow")
        table.add_column("Sync Status", style="magenta")
        
        for page in pages:
            title = page.get('title', 'Unknown')
            page_id_val = page.get('page_id', 'Unknown')
            saved_at = page.get('saved_at', 'Unknown')
            last_synced = page.get('last_synced', 'Never')
            
            # Apply filters
            if args.page_id and args.page_id not in page_id_val:
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
        
        console.print(table)
        
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")

def handle_edit_update(args):
    """Handle edit update command"""
    console = Console(width=9999, soft_wrap=False)
    
    try:
        editor = NotionJSONEditor()
        
        # Load the page
        data = editor.load_page(args.content_type, args.page_id)
        console.print(f"[green]Loaded page: {data['title']}[/green]")
        
        # Update title if provided
        if args.title:
            data = editor.update_title(data, args.title)
            console.print(f"[cyan]Updated title to: {args.title}[/cyan]")
        
        # Update properties if provided
        if args.property:
            for prop in args.property:
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
        if args.add_paragraph:
            block = editor.create_paragraph_block(args.add_paragraph)
            data = editor.add_content_block(data, block)
            console.print(f"[cyan]Added paragraph: {args.add_paragraph[:50]}[/cyan]")
        
        if args.add_heading:
            block = editor.create_heading_block(args.add_heading, args.heading_level)
            data = editor.add_content_block(data, block)
            console.print(f"[cyan]Added heading {args.heading_level}: {args.add_heading[:50]}[/cyan]")
        
        # Save the changes
        filepath = editor.save_page(data, backup=not args.no_backup)
        console.print(f"[green]Saved changes to: {filepath}[/green]")
        
        # Show changes summary
        changes = editor.get_changes_summary()
        if changes:
            console.print("\n[bold]Changes made:[/bold]")
            for change in changes:
                console.print(f"  • {change['description']}")
        
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")

def handle_edit_show(args):
    """Handle edit show command"""
    console = Console(width=9999, soft_wrap=False)
    
    try:
        editor = NotionJSONEditor()
        data = editor.load_page(args.content_type, args.page_id)
        
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

def handle_edit_sync(args):
    """Handle edit sync command"""
    console = Console(width=9999, soft_wrap=False)
    
    try:
        syncer = NotionSyncer()
        
        if args.dry_run:
            console.print("[yellow]DRY RUN - No changes will be made[/yellow]\n")
            
            if args.content_type:
                plan = syncer.create_sync_plan(args.content_type)
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
        
        if args.page_id:
            # Sync single page
            if not args.content_type:
                console.print("[red]Content type required when syncing specific page[/red]")
                return
            
            console.print(f"[yellow]Syncing page {args.page_id} in {args.content_type}...[/yellow]")
            result = syncer.sync_page(args.content_type, args.page_id, force=args.force)
            
            if result.success:
                console.print(f"[green]✓ Successfully synced {result.changes_applied} changes[/green]")
            else:
                console.print(f"[red]✗ Sync failed[/red]")
                for error in result.errors:
                    console.print(f"  [red]Error: {error}[/red]")
                for conflict in result.conflicts:
                    console.print(f"  [yellow]Conflict: {conflict}[/yellow]")
        
        elif args.content_type:
            # Sync entire database
            console.print(f"[yellow]Syncing all pages in {args.content_type}...[/yellow]")
            results = syncer.sync_database(args.content_type, force=args.force)
            
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
                results = syncer.sync_database(ct, force=args.force)
                all_results.extend(results)
            
            success_count = sum(1 for r in all_results if r.success)
            total_count = len(all_results)
            
            console.print(f"\n[bold]Total Sync Results: {success_count}/{total_count} successful[/bold]")
        
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")

def handle_edit_status(args):
    """Handle edit status command"""
    console = Console(width=9999, soft_wrap=False)
    
    try:
        syncer = NotionSyncer()
        
        if args.content_type:
            content_types = [args.content_type]
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