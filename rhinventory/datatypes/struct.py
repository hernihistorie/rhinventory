from typing import Any
from msgspec import Struct, StructMeta

# Follows docs at https://jcristharif.com/msgspec/api.html#msgspec.StructMeta
class RHInventoryStructMeta(StructMeta):
    def __new__(mcls, *args: tuple[Any, ...], **kwargs: dict[Any, Any]):
        kwargs.setdefault("kw_only", True)
        kwargs.setdefault("frozen", True)
        kwargs.setdefault("tag_field", "type")
        kwargs.setdefault("tag", True)
        return super().__new__(mcls, *args, **kwargs)

class RHInventoryStruct(Struct, metaclass=RHInventoryStructMeta):
    '''
        Serializable and frozen structure usable in RHInventory events.
    '''
    pass
