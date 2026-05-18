from uuid import UUID

from rhinventory.models.properties.property import Property


properties = [
    Property(
        id=UUID('019e3775-dee2-7560-8489-17aa7b68ff7a'),
        name='Redump URL'
    ),
    Property(
        id=UUID('019e3777-8c2f-7e30-a6e4-c51753bc6879'),
        name='cs.speccy.org URL'
    ),
    Property(
        id=UUID('019e3cca-da43-7689-9cc9-1fa96e3d4ab1'),
        name='Visiongame URL'
    ),
    Property(
        id=UUID('019e3ccb-a0e9-79a6-823c-f5c9abb99714'),
        name="Oldgames.sk URL"
    ),
    Property(
        id=UUID('019e3ccc-2ce1-7a3b-8e53-c040d5b72638'),
        name="Databáze her URL"
    ),
    Property(
        id=UUID('019e3ccc-5c79-700b-a5ed-5c2e1154b362'),
        name="Mobygames URL"
    ),
    Property(
        id=UUID('019e3ccc-716d-79f1-9abb-96ed384a4512'),
        name="Wikidata URL"
    ),
    Property(
        id=UUID('019e3cce-7dc4-706b-8261-f3763dd81403'),
        name="The Retro Web URL"
    ),
    Property(
        id=UUID('019e3cce-26eb-7744-bf0f-bbfeacd82ed2'),
        name="vgamuseum.info URL"
    ),
]

properties_by_id = {prop.id: prop for prop in properties}

# assert no duplicate IDs
assert len(properties_by_id) == len(properties), "Duplicate property ID detected"
