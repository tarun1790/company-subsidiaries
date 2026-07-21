import hashlib
from typing import Dict, List, Any, Tuple
from app.core.logging import logger

class IncrementalAuditor:
    """Incremental Auditing Engine: Detects changes between previous corporate audit snapshots
    and new filings, allowing delta processing to eliminate duplicate computation."""

    @classmethod
    def compute_filing_hash(cls, filing_data: str) -> str:
        """Computes SHA-256 hash of raw filing text or table content."""
        return hashlib.sha256(filing_data.encode('utf-8')).hexdigest()

    @classmethod
    def detect_audit_delta(
        cls, 
        previous_subs: List[Dict[str, Any]], 
        current_candidates: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Compares previous audit snapshot against current candidates.
        Returns: (new_entities, retained_entities, removed_entities)"""
        
        prev_map = {s["name"].lower().strip(): s for s in previous_subs if "name" in s}
        curr_map = {s["name"].lower().strip(): s for s in current_candidates if "name" in s}
        
        new_entities = []
        retained_entities = []
        removed_entities = []
        
        for name_key, curr_item in curr_map.items():
            if name_key not in prev_map:
                curr_item["audit_status"] = "New / Discovered in Latest Audit"
                new_entities.append(curr_item)
            else:
                retained_item = prev_map[name_key]
                retained_item["audit_status"] = "Retained / Verified"
                retained_entities.append(retained_item)

        for name_key, prev_item in prev_map.items():
            if name_key not in curr_map:
                prev_item["audit_status"] = "Historical / Divested"
                removed_entities.append(prev_item)

        logger.info(
            f"[IncrementalAuditor] Delta Analysis Complete: "
            f"New={len(new_entities)} | Retained={len(retained_entities)} | Divested/Removed={len(removed_entities)}"
        )
        return new_entities, retained_entities, removed_entities
