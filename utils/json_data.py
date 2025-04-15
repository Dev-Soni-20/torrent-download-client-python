from dataclasses import dataclass, asdict, field
from typing import List, Set
import json
from asyncio import Lock

@dataclass
class ResumeData:
    info_hash: str
    piece_length: int
    total_pieces: int
    downloaded: int
    file_sizes: List[int]
    mtime: int
    verified_pieces: List[bool]
    last_active: str

    # These fields are excluded from serialization
    lock: Lock = field(init=False, repr=False, compare=False)
    claimed_pieces: Set[int] = field(default_factory=set, init=False, repr=False, compare=False)

    def __post_init__(self):
        self.lock = Lock()

    def to_json(self, path: str) -> None:
        data = asdict(self)
        data.pop('lock', None)
        data.pop('claimed_pieces', None) 
        with open(path, "w") as f:
            json.dump(data, f, indent=1)

    @classmethod
    def from_json(cls, path: str) -> "ResumeData":
        with open(path, "r") as f:
            data = json.load(f)
        obj = cls(**data)
        obj.lock = Lock()
        obj.claimed_pieces = set()
        return obj

    def verified_to_bytes(self) -> bytes:
        buf = bytearray()
        byte = 0

        for i, bit in enumerate(self.verified_pieces):
            byte = (byte << 1) | int(bit)
            if i % 8 == 7:
                buf.append(byte)
                byte = 0

        remaining = len(self.verified_pieces) % 8

        if remaining != 0:
            byte <<= (8 - remaining)
            buf.append(byte)

        return bytes(buf)