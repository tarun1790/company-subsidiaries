import os
import json
import re
from typing import Dict, List, Any
from app.agents.state import AgentState
from app.core.logging import logger

def load_config() -> Dict[str, Any]:
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "core", "loop_config.json")
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        # Fallback default values
        return {
            "max_iterations": 2,
            "max_depth": 2,
            "no_new_entities_streak_threshold": 1,
            "coverage_threshold": 0.90,
            "source_priorities": {
                "SEC Filings": 1.0,
                "Authoritative Registry": 0.95,
                "Annual Reports": 0.9,
                "Official Website": 0.85,
                "Press Releases": 0.8,
                "Web Research": 0.6,
                "Wikipedia": 0.2
            }
        }

async def loop_coordinator_agent(state: AgentState) -> AgentState:
    """
    Agent 15: Adaptive Loop Coordinator.
    Reviews the current consolidated subsidiaries, extracts new targets, 
    tracks iterations/streaks, and compiles the execution summary.
    """
    logs = state.get("logs") or []
    subs = state.get("subsidiaries") or []
    
    current_iter = state.get("current_iteration") or 1
    explored = state.get("explored_entities") or []
    pending = state.get("pending_targets") or []
    
    logs.append(f"--- Completed Discovery Loop Iteration {current_iter} ---")
    logger.info(f"Loop Coordinator: Completed Iteration {current_iter}.")
    
    config = load_config()
    source_priorities = config.get("source_priorities", {})
    
    # 1. Identify newly discovered entities to queue as search targets
    # (Entities that have not been explored yet)
    new_targets = []
    suffixes = {"inc", "llc", "ltd", "corp", "co", "plc", "gmbh", "ag", "sa", "bv", "nv", "sarl", "as", "pvt", "private", "limited", "company"}
    for sub in subs:
        name = sub.get("name")
        if not name:
            continue
        name_clean = name.strip()
        
        # Avoid exploring duplicates or already explored targets
        if name_clean in explored:
            continue
            
        # Safeguard: skip pure legal suffixes or very short/invalid names
        name_lower = re.sub(r'[^\w\s]', '', name_clean).strip().lower()
        if name_lower in suffixes or len(name_lower) < 3:
            continue
            
        # Only queue verified and high-confidence entities (confidence >= 80%) for recursive discovery
        confidence = sub.get("confidence", 0.0)
        if confidence < 0.80:
            continue
            
        # Determine priority based on discovery source weights
        priority = 0.5 # Default priority
        evidences = sub.get("evidences", [])
        if evidences:
            source_types = [ev.get("source_type") for ev in evidences if ev.get("source_type")]
            # Get maximum priority among supporting sources
            priority = max((source_priorities.get(st, 0.5) for st in source_types), default=0.5)
            
        # Determine depth from current target state or default to depth of parent + 1
        current_depth = state.get("company_info", {}).get("depth") or 1
        
        new_targets.append({
            "legal_name": name_clean,
            "domain": sub.get("domain") or "",
            "country": sub.get("country") or "Global",
            "priority": priority,
            "depth": current_depth + 1,
            "discovered_from": state.get("query")
        })
        
    # Append to pending if not already queued, keeping highest priority
    pending_dict = {p["legal_name"]: p for p in pending}
    added_count = 0
    for target in new_targets:
        name = target["legal_name"]
        if name not in pending_dict:
            pending.append(target)
            pending_dict[name] = target
            added_count += 1
        else:
            # Update priority if the new evidence path is stronger
            if target["priority"] > pending_dict[name]["priority"]:
                pending_dict[name]["priority"] = target["priority"]
                
    # Sort pending targets by priority descending (Best-First Search)
    pending.sort(key=lambda x: x["priority"], reverse=True)
    
    # 2. Update streak tracking
    if added_count == 0:
        streak = state.get("no_new_entities_streak", 0) + 1
    else:
        streak = 0
        
    logs.append(f"Discovered {added_count} new potential targets. Total pending queue: {len(pending)}. Streak: {streak}")
    
    # Compile execution summary info
    summary = state.get("execution_summary") or {
        "iterations_run": 0,
        "successful_strategies": [],
        "sources_with_data": set(),
        "unseen_entities_count": 0
    }
    summary["iterations_run"] = current_iter
    summary["unseen_entities_count"] += added_count
    
    # Track sources with data
    for sub in subs:
        for ev in sub.get("evidences", []):
            if isinstance(summary["sources_with_data"], list):
                summary["sources_with_data"] = set(summary["sources_with_data"])
            summary["sources_with_data"].add(ev["source_type"])
            
    summary["sources_with_data"] = list(summary["sources_with_data"])
    
    return {
        **state,
        "current_iteration": current_iter,
        "no_new_entities_streak": streak,
        "pending_targets": pending,
        "execution_summary": summary,
        "logs": logs
    }

async def next_target_preparer_agent(state: AgentState) -> AgentState:
    pending = state.get("pending_targets") or []
    explored = state.get("explored_entities") or []
    logs = state.get("logs") or []
    
    if not pending:
        return state
        
    next_target = pending.pop(0)
    explored.append(next_target["legal_name"])
    
    logs.append(f"Looping to search next priority target: '{next_target['legal_name']}' (Priority: {next_target['priority']}, Depth: {next_target['depth']})...")
    logger.info(f"Loop Coordinator: Switching target to: {next_target['legal_name']}.")
    
    # Update current query & company_info for the next iteration
    new_company_info = {
        "canonical_company": next_target["legal_name"],
        "legal_name": next_target["legal_name"],
        "domain": next_target.get("domain") or "",
        "country": next_target.get("country") or "Global",
        "depth": next_target.get("depth") or 2,
        "status": "success"
    }
    
    return {
        **state,
        "query": next_target["legal_name"],
        "company_info": new_company_info,
        "explored_entities": explored,
        "pending_targets": pending,
        "current_iteration": (state.get("current_iteration") or 1) + 1,
        "logs": logs
    }

def route_discovery_loop(state: AgentState) -> List[str]:
    current_iter = state.get("current_iteration") or 1
    streak = state.get("no_new_entities_streak") or 0
    pending = state.get("pending_targets") or []
    coverage = state.get("coverage_score") or {}
    
    config = load_config()
    active_mode = state.get("execution_summary", {}).get("mode", config.get("default_mode", "enterprise_audit"))
    mode_settings = config.get("modes", {}).get(active_mode, {})
    
    max_iter = mode_settings.get("max_iterations", 10)
    max_depth_limit = mode_settings.get("max_depth", 6)
    streak_limit = mode_settings.get("no_new_entities_streak_threshold", 3)
    cov_threshold = config.get("coverage_threshold", 0.95)
    
    overall_cov = coverage.get("overall", 0.0)
    
    # Stop conditions:
    if overall_cov >= cov_threshold:
        state["logs"].append(f"Stop condition met: Overall Coverage {overall_cov * 100:.1f}% >= threshold {cov_threshold * 100:.1f}%.")
        return ["__end__"]
    if streak >= streak_limit:
        state["logs"].append(f"Stop condition met: No new entities streak reached {streak}.")
        return ["__end__"]
    if current_iter >= max_iter:
        state["logs"].append(f"Stop condition met: Max iterations limit ({max_iter}) reached in mode {active_mode}.")
        return ["__end__"]
    if not pending:
        state["logs"].append("Stop condition met: Pending targets queue is empty.")
        return ["__end__"]
        
    # Check if next target exceeds maximum recursion depth
    if pending[0]["depth"] > max_depth_limit:
        state["logs"].append(f"Stop condition met: Next target '{pending[0]['legal_name']}' depth ({pending[0]['depth']}) exceeds mode {active_mode} limit {max_depth_limit}.")
        return ["__end__"]
        
    return ["next_target_preparer"]
