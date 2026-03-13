import json
import urllib.request
from typing import Any

from rich.console import Console

console = Console()

async def handle_status(args: Any):
    """
    Query the local FastAPI /api/health endpoint and print the results 
    in plain language to the terminal.
    """
    url = "http://localhost:8000/api/health"
    console.print("\n[bold]Checking Promaia System Status...[/bold]\n")
    
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Promaia-CLI'})
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status != 200:
                console.print(f"[bold red]❌ Web server responded with HTTP {response.status}[/bold red]")
                return
                
            data = json.loads(response.read().decode())
    except Exception as e:
        console.print("[bold red]❌ Could not connect to the Promaia web server.[/bold red]")
        console.print("   The system might be fully offline. (Try running 'promaia dev' first.)")
        console.print(f"   [dim]Error details: {e}[/dim]")
        return
        
    overall_status = data.get("status", "unknown")
    if overall_status == "healthy":
        console.print(f"Overall Status: [bold green]HEALTHY[/bold green]")
    else:
        console.print(f"Overall Status: [bold yellow]{overall_status.upper()}[/bold yellow]")
        
    components = data.get("components", {})
    if not components:
        console.print("[dim]No component telemetry available.[/dim]")
        return
        
    console.print()
    
    # 1. Database
    db_status = components.get("database", "unknown")
    if db_status == "connected":
        console.print("  [green]✅[/green] Database: OK (PostgreSQL connected)")
    else:
        console.print(f"  [red]❌[/red] Database: FAILED ({db_status})")
        
    # 2. MuninnDB
    muninn_status = components.get("muninn", "unknown")
    if muninn_status == "connected":
        console.print("  [green]✅[/green] Memory: OK (MuninnDB connected)")
    else:
        console.print(f"  [red]❌[/red] Memory: FAILED ({muninn_status})")
        
    # 3. Heartbeat
    hb_status = components.get("heartbeat", "unknown")
    if hb_status == "running":
        console.print("  [green]✅[/green] Background Tasks: OK (Scheduler heartbeat running)")
    else:
        console.print(f"  [yellow]⚠️[/yellow] Background Tasks: PAUSED ({hb_status})")
        
    # 4. LLM Keys
    keys_status = components.get("llm_keys", "unknown")
    if keys_status.startswith("available"):
        console.print(f"  [green]✅[/green] AI Keys: OK ({keys_status})")
    else:
        console.print(f"  [red]❌[/red] AI Keys: FAILED ({keys_status})")
        
    # 5. MCP
    mcp_status = components.get("mcp_config", "unknown")
    if "enabled" in mcp_status:
        console.print(f"  [green]✅[/green] Extensions: OK ({mcp_status})")
    else:
        console.print(f"  [yellow]⚠️[/yellow] Extensions: ISSUE ({mcp_status})")
        
    console.print("\n")
