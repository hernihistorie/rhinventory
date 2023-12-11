from enum import Enum

class Privacy(Enum):
    private_implicit = 1
    private = 2
    unlinked = 10
    public = 20

HIDDEN_STATUSES = [Privacy.private, Privacy.unlinked]
