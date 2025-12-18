from typing import NewType

from rhinventory.datatypes.struct import RHInventoryStruct


MD5Hash = NewType('MD5Hash', bytes)
SHA256Hash = NewType('SHA256Hash', bytes)
BLAKE3Hash = NewType('BLAKE3Hash', bytes)

class Hashes(RHInventoryStruct):
    md5: MD5Hash
    sha256: SHA256Hash
    blake3: BLAKE3Hash
