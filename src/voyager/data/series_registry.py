"""
Series Registry for V3 thesis validation.

Maps concepts (e.g., "real yields") to concrete data series (e.g., "DFII10").
"""
from dataclasses import dataclass
from typing import Optional, List
import json
from pathlib import Path


@dataclass
class SeriesEntry:
    """A single series in the registry"""
    id: str
    source: str  # "FRED" | "TwelveData"
    name: str
    category: str  # "rates" | "fx" | "commodity" | "equity" | "volatility"
    aliases: List[str]
    frequency: str  # "daily" | "weekly" | "monthly"
    return_type: str  # "pct_change" | "diff" | "level" | "none"


class SeriesRegistry:
    """
    Registry of available data series with concept-to-series mapping.
    
    Usage:
        registry = SeriesRegistry()
        candidates = registry.search_by_concept("real yields")
        # Returns [SeriesEntry(id="DFII10", ...)]
    """
    
    def __init__(self, path: Path = None):
        """Load registry from JSON file"""
        if path is None:
            path = Path(__file__).parent / "series_registry.json"
        
        with open(path) as f:
            data = json.load(f)
        
        self._entries: dict[str, SeriesEntry] = {}
        for s in data["series"]:
            self._entries[s["id"]] = SeriesEntry(
                id=s["id"],
                source=s["source"],
                name=s["name"],
                category=s["category"],
                aliases=s["aliases"],
                frequency=s["frequency"],
                return_type=s.get("return_type", "level")  # Default to "level" for backward compatibility
            )
        
        self._alias_index = self._build_alias_index()
    
    def _build_alias_index(self) -> dict[str, List[str]]:
        """Build index mapping lowercase aliases to series IDs"""
        index: dict[str, List[str]] = {}
        for series_id, entry in self._entries.items():
            for alias in entry.aliases:
                key = alias.lower()
                if key not in index:
                    index[key] = []
                index[key].append(series_id)
            # Also index the series ID itself
            index[series_id.lower()] = [series_id]
        return index
    
    def search_by_concept(self, concept: str) -> List[SeriesEntry]:
        """
        Find series matching a concept.
        
        Args:
            concept: Natural language concept (e.g., "real yields", "gold")
            
        Returns:
            List of matching SeriesEntry objects. Empty if no match.
        """
        concept_lower = concept.lower().strip()
        
        # Exact match first
        if concept_lower in self._alias_index:
            return [self._entries[sid] for sid in self._alias_index[concept_lower]]
        
        # Partial match fallback
        matches = set()
        for alias, series_ids in self._alias_index.items():
            # Check if concept contains alias or alias contains concept
            if concept_lower in alias or alias in concept_lower:
                matches.update(series_ids)
        
        return [self._entries[sid] for sid in matches]
    
    def get_by_id(self, series_id: str) -> Optional[SeriesEntry]:
        """Get series by exact ID"""
        return self._entries.get(series_id)
    
    def list_by_category(self, category: str) -> List[SeriesEntry]:
        """List all series in a category"""
        return [e for e in self._entries.values() if e.category == category]
    
    def list_all(self) -> List[SeriesEntry]:
        """List all series"""
        return list(self._entries.values())
    
    def list_categories(self) -> List[str]:
        """List all unique categories"""
        return list(set(e.category for e in self._entries.values()))
