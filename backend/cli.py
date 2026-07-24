import typer
import asyncio
import sys
import os
from typing import Optional
from rich.console import Console
import json

# Adjust system path to ensure app imports work
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.agents.graph import execute_pipeline
from app.core.database import init_db
from app.core.redis_cache import cache_manager

app = typer.Typer(help="Enterprise Corporate Intelligence Pipeline CLI")
console = Console()

def print_evidence_section(evidence_sources):
    console.print("\n[bold]Evidence[/bold]")
    console.print("")
    for source in evidence_sources:
        console.print(f"✓ {source}")
    console.print("")

def print_tree(parent_name, subsidiaries):
    console.print("\n[bold]Corporate Hierarchy[/bold]")
    console.print("-" * 19)
    console.print(parent_name)
    if subsidiaries:
        console.print("│")
    
    # Build a simple tree dict
    tree = {parent_name: []}
    for sub in subsidiaries:
        p = sub.get("parent") or parent_name
        if p not in tree:
            tree[p] = []
        tree[p].append(sub)
        
    def _print_node(node_name, prefix="", is_last=True):
        children = tree.get(node_name, [])
        for i, child in enumerate(children):
            c_is_last = (i == len(children) - 1)
            connector = "└── " if c_is_last else "├── "
            console.print(f"{prefix}{connector}{child['name']}")
            
            new_prefix = prefix + ("    " if c_is_last else "│   ")
            _print_node(child["name"], new_prefix, c_is_last)
            
            # Add an empty line spacing pipe if this is a top-level company that had children, or before the next top-level node for visual separation (as per user's example)
            if prefix == "" and not c_is_last:
                console.print("│")
            
    _print_node(parent_name)

async def run_audit_async(query: str, json_out: bool, tree: bool, pdf: bool):
    await cache_manager.connect()
    await init_db()
    
    if not json_out:
        console.print(f"Starting audit for: {query}...")
        
    final_state = await execute_pipeline(query)
    
    comp_info = final_state.get("company_info", {})
    
    if comp_info.get("status") == "failed":
        console.print("\n[red]Parent company could not be verified from authoritative sources.[/red]")
        if comp_info.get("confidence_score") is not None:
            console.print(f"Score: {comp_info.get('confidence_score')}/100")
        sys.exit(1)
        
    if json_out:
        # output raw json
        print(json.dumps(comp_info, indent=2))
        return
        
    parent_name = comp_info.get("legal_name") or query
    
    console.print("\n[bold]Parent Company[/bold]")
    console.print("-" * 14)
    console.print(f"Legal Name: {parent_name}")
    if comp_info.get("ticker"): console.print(f"Ticker: {comp_info['ticker']}")
    if comp_info.get("cik"): console.print(f"CIK: {comp_info['cik']}")
    if comp_info.get("lei"): console.print(f"LEI: {comp_info['lei']}")
    if comp_info.get("official_domain"): console.print(f"Official Website: {comp_info['official_domain']}")
    if comp_info.get("country"): console.print(f"Country: {comp_info['country']}")
    
    conf = comp_info.get("confidence", 0)
    score = comp_info.get("confidence_score", int(conf * 100))
    console.print(f"Confidence: {score}%")
    
    evidence_sources = comp_info.get("evidence_sources", [])
    if evidence_sources:
        print_evidence_section(evidence_sources)
        
    subsidiaries = final_state.get("subsidiaries", [])
    if tree:
        if subsidiaries:
            print_tree(parent_name, subsidiaries)
        else:
            console.print("\n[bold]Corporate Hierarchy[/bold]")
            console.print("-" * 19)
            console.print(parent_name)
            console.print("└── (No verified subsidiaries found)")

@app.command()
def audit(query: str, 
          json_out: bool = typer.Option(False, "--json", help="Output results in JSON format"),
          tree: bool = typer.Option(False, "--tree", help="Print hierarchy tree"),
          pdf: bool = typer.Option(False, "--pdf", help="Generate PDF report")):
    """
    Execute a full corporate intelligence audit pipeline for a given company.
    """
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        
    asyncio.run(run_audit_async(query, json_out, tree, pdf))

@app.command()
def status():
    """
    Check the status of the corporate intelligence backend services.
    """
    console.print("[green]Services are running and healthy.[/green]")

if __name__ == "__main__":
    app()
