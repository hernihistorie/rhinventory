import uuid
from dataclasses import dataclass

type PropertyID = uuid.UUID

@dataclass
class Property:
    id: PropertyID
    name: str