from dataclasses import dataclass, asdict
from typing import List
import json

@dataclass
class ResumeData:
    info_hash: str
    bitfield: str
    piece_length: int
    total_pieces: int
    downloaded: int
    file_sizes: List[int]
    mtime: int
    verified_pieces: List[int]
    last_active: str

    def to_json(self, path: str)->None:
        with open(path, "w") as f:
            json.dump(asdict(self), f, indent=2)

    @classmethod
    def from_json(cls, path: str) -> "ResumeData":
        with open(path, "r") as f:
            data = json.load(f)
        return cls(**data)