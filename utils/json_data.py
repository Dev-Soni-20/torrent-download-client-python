from dataclasses import dataclass, asdict
from typing import List
import json

@dataclass
class ResumeData:
    info_hash: str
    bitfield: List[bool]
    piece_length: int
    total_pieces: int
    downloaded: int
    file_sizes: List[int]
    mtime: int
    verified_pieces: List[int]
    last_active: str

    def to_json(self, path: str) -> None:
        with open(path, "w") as f:
            json.dump(asdict(self), f, indent=2)

    @classmethod
    def from_json(cls, path: str) -> "ResumeData":
        with open(path, "r") as f:
            data = json.load(f)
        return cls(**data)
    
    def bitfield_to_bytes(bitfield: list[bool]) -> bytes:
        buf = bytearray()
        byte = 0

        for i, bit in enumerate(bitfield):
            byte = (byte << 1) | int(bit)
            if i % 8 == 7:
                buf.append(byte)
                byte = 0

        remaining = len(bitfield) % 8
        
        if remaining != 0:
            byte <<= (8 - remaining)
            buf.append(byte)
        
        return bytes(buf)