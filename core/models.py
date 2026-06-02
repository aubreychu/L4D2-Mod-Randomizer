from dataclasses import dataclass, field
from typing import List

@dataclass
class ModEvaluation:
    model_slots: List[str] = field(default_factory=list)
    audio_slots: List[str] = field(default_factory=list)
    raw_paths: List[str] = field(default_factory=list)

@dataclass
class ModItem:
    id: str
    title: str
    tags: List[str]
    preview_url: str = ""
    theme_tag: str = "None"
    eval: ModEvaluation = field(default_factory=ModEvaluation)
    
    # New Steam Metadata Fields for Advanced Filtering
    subscriptions: int = 0
    views: int = 0
    favorited: int = 0
    time_created: int = 0  # Unix timestamp
    time_updated: int = 0  # Unix timestamp