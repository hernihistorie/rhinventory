from ..hhprint4 import AbstractImageSource, Code
from io import BytesIO
import asyncio


class MockImageSource(AbstractImageSource):

    async def get_image(self, code: Code) -> BytesIO:
        return BytesIO(code.code.encode())


class TestImageSource:

    def test_simple(self) -> None:
        assert b'foo' == asyncio.run(MockImageSource().get_image(Code.from_str('foo'))).getvalue()
