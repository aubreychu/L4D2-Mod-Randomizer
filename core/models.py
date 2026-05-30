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
    file_url: str = ""
    preview_url: str = ""
    theme_tag: str = "None"
    eval: ModEvaluation = field(default_factory=ModEvaluation)