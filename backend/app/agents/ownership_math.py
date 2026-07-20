import math
from typing import List, Dict, Any, Tuple, Optional
from app.core.logging import logger

def calculate_direct_ownership(edge_data: Dict[str, Any]) -> Optional[float]:
    """Extracts direct ownership float percentage (0.0 to 1.0) from edge data."""
    raw = edge_data.get("ownership") or edge_data.get("direct_ownership_pct")
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return max(0.0, min(1.0, float(raw) / 100.0 if float(raw) > 1.0 else float(raw)))
    if isinstance(raw, str):
        import re
        match = re.search(r"(\d+(?:\.\d+)?)%", raw)
        if match:
            val = float(match.group(1)) / 100.0
            return max(0.0, min(1.0, val))
        if "wholly" in raw.lower() or "100" in raw:
            return 1.0
        if "majority" in raw.lower():
            return 0.51
    return None

def calculate_effective_ownership_path(path_edges: List[Dict[str, Any]]) -> Tuple[Optional[float], bool]:
    """Calculates effective ownership along a single chain of edges: E_path = product(D_i).
    
    Returns (effective_percentage, has_unspecified_control).
    """
    if not path_edges:
        return (1.0, False)
        
    product = 1.0
    has_unspecified = False
    
    for edge in path_edges:
        direct = calculate_direct_ownership(edge)
        if direct is not None:
            product *= direct
        else:
            has_unspecified = True
            
    return (round(product, 4) if not has_unspecified else None, has_unspecified)

def calculate_total_effective_ownership(parallel_paths: List[List[Dict[str, Any]]]) -> Tuple[Optional[float], bool]:
    """Calculates total effective ownership across multiple parallel paths: E_total = sum(E_path_j)."""
    if not parallel_paths:
        return (0.0, False)
        
    total_effective = 0.0
    any_unspecified = False
    
    for path in parallel_paths:
        eff, unspecified = calculate_effective_ownership_path(path)
        if eff is not None:
            total_effective += eff
        if unspecified:
            any_unspecified = True
            
    total_effective = min(1.0, round(total_effective, 4))
    return (total_effective if total_effective > 0.0 else None, any_unspecified)

def detect_tarjan_cycles(nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]]) -> List[List[str]]:
    """Detects circular ownership loops using Tarjan's strongly connected components algorithm."""
    adj: Dict[str, List[str]] = {n["id"]: [] for n in nodes if "id" in n}
    for e in edges:
        src = e.get("source")
        tgt = e.get("target")
        if src in adj and tgt in adj:
            adj[src].append(tgt)
            
    index = 0
    stack: List[str] = []
    indices: Dict[str, int] = {}
    lowlink: Dict[str, int] = {}
    on_stack: Dict[str, bool] = {}
    sccs: List[List[str]] = []

    def strongconnect(node: str):
        nonlocal index
        indices[node] = index
        lowlink[node] = index
        index += 1
        stack.append(node)
        on_stack[node] = True

        for neighbor in adj.get(node, []):
            if neighbor not in indices:
                strongconnect(neighbor)
                lowlink[node] = min(lowlink[node], lowlink[neighbor])
            elif on_stack.get(neighbor, False):
                lowlink[node] = min(lowlink[node], indices[neighbor])

        if lowlink[node] == indices[node]:
            scc = []
            while True:
                w = stack.pop()
                on_stack[w] = False
                scc.append(w)
                if w == node:
                    break
            if len(scc) > 1:
                sccs.append(scc)

    for node in adj:
        if node not in indices:
            strongconnect(node)

    return sccs
