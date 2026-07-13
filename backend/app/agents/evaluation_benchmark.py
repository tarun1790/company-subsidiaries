import os
import json
import re
from app.agents.state import AgentState
from app.core.logging import logger

def get_clean_normalized_set(names: list) -> set:
    normalized = set()
    for name in names:
        n = name.lower().strip()
        n = re.sub(r"[^\w]", "", n)
        if n:
            normalized.add(n)
    return normalized

async def evaluation_benchmark_agent(state: AgentState) -> AgentState:
    """Agent 15: Benchmark evaluation agent comparing discovered entities with ground truth."""
    subs = state.get("subsidiaries", [])
    logs = state.get("logs", [])
    query = state["query"].lower().strip()
    
    clean_query = re.sub(r"[^\w]", "", query)
    
    benchmark_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "benchmarks")
    benchmark_path = os.path.join(benchmark_dir, f"{clean_query}.json")
    
    logs.append("Running Evaluation & Benchmark Agent...")
    logger.info(f"Evaluation & Benchmark Agent checking for ground truth file: {benchmark_path}")
    
    if not os.path.exists(benchmark_path):
        logs.append(f"No ground truth benchmark dataset found at '{clean_query}.json'. Skipping evaluation metrics.")
        return state
        
    try:
        with open(benchmark_path, "r") as f:
            ground_truth = json.load(f)
            
        gt_list = ground_truth.get("subsidiaries", [])
        logs.append(f"Ground truth file loaded: {len(gt_list)} expected subsidiaries.")
        
        gt_set = get_clean_normalized_set(gt_list)
        discovered_set = get_clean_normalized_set([s["name"] for s in subs if s.get("confidence", 0) >= 0.80])
        
        true_positives = gt_set.intersection(discovered_set)
        false_positives = discovered_set - gt_set
        false_negatives = gt_set - discovered_set
        
        tp = len(true_positives)
        fp = len(false_positives)
        fn = len(false_negatives)
        
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        
        missed_names = []
        for gt in gt_list:
            clean_gt = re.sub(r"[^\w]", "", gt.lower().strip())
            if clean_gt in false_negatives:
                missed_names.append(gt)
                
        fp_names = []
        for s in subs:
            clean_name = re.sub(r"[^\w]", "", s["name"].lower().strip())
            if clean_name in false_positives:
                fp_names.append(s["name"])
                
        metrics = {
            "precision": round(precision * 100, 1),
            "recall": round(recall * 100, 1),
            "f1_score": round(f1 * 100, 1),
            "true_positives_count": tp,
            "false_positives_count": fp,
            "false_negatives_count": fn,
            "missed_entities": missed_names,
            "false_positive_entities": fp_names
        }
        
        logs.append(
            f"Evaluation Metrics calculated: Precision={metrics['precision']}%, "
            f"Recall={metrics['recall']}%, F1={metrics['f1_score']}%."
        )
        
        meta = state["company_info"].get("metadata_fields") or {}
        if not isinstance(meta, dict):
            meta = {}
        meta["evaluation_metrics"] = metrics
        
        updated_company_info = {
            **state["company_info"],
            "metadata_fields": meta
        }
        
        return {
            **state,
            "company_info": updated_company_info,
            "logs": logs
        }
    except Exception as e:
        logger.error(f"Error executing benchmark evaluation: {str(e)}")
        logs.append(f"Benchmark evaluation error: {str(e)}")
        return state
