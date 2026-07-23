from typing import Dict, List, Any, Set
from app.agents.state import AgentState, emit_node_telemetry
import time
from app.core.logging import logger

def detect_cycles(edges: List[Dict[str, Any]]) -> List[List[str]]:
    graph = {}
    for edge in edges:
        parent = edge.get("parent")
        child = edge.get("child")
        if parent and child:
            graph.setdefault(parent, []).append(child)

    visited = set()
    stack = set()
    cycles = []

    def dfs(node: str, path: List[str]):
        if node in stack:
            cycle_start = path.index(node)
            cycles.append(path[cycle_start:] + [node])
            return

        if node in visited:
            return

        visited.add(node)
        stack.add(node)

        for child in graph.get(node, []):
            dfs(child, path + [child])

        stack.remove(node)

    for node in graph:
        dfs(node, [node])

    return cycles

async def graph_validation_agent(state: AgentState) -> AgentState:
    """Agent: Validates graph structure, detects cycles, and identifies orphans."""
    start_time = time.time()
    logs = state.get("logs", [])
    warnings = state.get("warnings", [])
    
    subs = state.get("subsidiaries", [])
    legal_name = state.get("company_info", {}).get("legal_name") or state.get("query")
    
    edges = []
    nodes = set([legal_name])
    
    for sub in subs:
        name = sub.get("name")
        parent = sub.get("parent")
        if name:
            nodes.add(name)
        if parent:
            nodes.add(parent)
        if name and parent:
            edges.append({"parent": parent, "child": name})
            
    cycles = detect_cycles(edges)
    
    orphan_nodes = []
    for sub in subs:
        if not sub.get("parent"):
            orphan_nodes.append({"entity_name": sub.get("name"), "reason": "No parent explicitly stated"})
            
    graph_validation = {
        "graph_valid": len(cycles) == 0,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "cycles_detected": [{"cycle_path": c, "severity": "High", "requires_review": True} for c in cycles],
        "orphan_nodes": orphan_nodes,
        "warnings": []
    }
    
    if cycles:
        msg = f"Graph validation detected {len(cycles)} ownership cycles."
        logs.append(msg)
        warnings.append({"stage": "graph_validation", "code": "CYCLES_DETECTED", "message": msg})
        
    state["knowledge_graph"]["graph_validation"] = graph_validation
    
    emit_node_telemetry("graph_validation", state, start_time, "success")
    return {
        **state,
        "logs": logs,
        "warnings": warnings,
        "knowledge_graph": state["knowledge_graph"]
    }
