from dataclasses import dataclass


@dataclass(frozen=True)
class Confirmation:
    operator_ref: str
    replayed: bool