from enum import Enum

class Privacy(Enum):
    private_implicit = 1
    private = 2
    unlinked = 10
    public = 20

HIDDEN_PRIVACIES = [Privacy.private_implicit, Privacy.private, Privacy.unlinked]
PUBLIC_PRIVACIES = [Privacy.public]
