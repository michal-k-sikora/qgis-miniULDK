from dataclasses import dataclass


@dataclass(frozen=True)
class OperationResult:
    geometry: object
    success: bool
    added: bool
    saved_to_file: bool
    added_to_project: bool
    message: str