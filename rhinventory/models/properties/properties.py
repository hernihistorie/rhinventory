import uuid

from rhinventory.models.properties.property import Property


redump_url = Property(
    id=uuid.UUID('019e3775-dee2-7560-8489-17aa7b68ff7a'),
    name='Redump URL'
)

cs_speccy_url = Property(
    id=uuid.UUID('019e3777-8c2f-7e30-a6e4-c51753bc6879'),
    name='cs.speccy.org URL'
)

properties = [
    redump_url,
    cs_speccy_url
]

properties_by_id = {prop.id: prop for prop in properties}