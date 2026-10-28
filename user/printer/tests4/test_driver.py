import pprint

from ..hhprint4 import AbstractPrinterDriver, PrinterDriverFactory, AvailablePrinter, PrintQuery
from io import BytesIO
import pytest


class MockDriverMixin:

    def __init__(
            self,
    ):
        self._output: str = ''

    def print(self, printer: AvailablePrinter, query: PrintQuery, image: BytesIO) -> None:
        self._output = self._output \
                       + 'PRINT CODE: ' + image.getvalue().decode('utf-8') + '\n' \
                       + 'label: ' + query.label + '\n' \
                       + 'link: ' + printer.link + '\n' \
                       + 'backend: ' + printer.backend + '\n' \
                       + '---\n'

    def get_output(self) -> str:
        return self._output

    def clear(self) -> None:
        self._output = ''


class MockDriver(MockDriverMixin, AbstractPrinterDriver):

    instance = None

    def __new__(
            cls,
    ):
        # singleton during run - data was not changed
        if cls.instance is None:
            cls.instance = super().__new__(cls)
        return cls.instance


class MockDriverFactory(PrinterDriverFactory):

    def __init__(
            self,
    ):
        MockDriver.instance = None # reset singleton here
        self._mock_connection: AbstractPrinterDriver | None = None

    def get_driver(self, printer: AvailablePrinter) -> AbstractPrinterDriver:
        if not self._mock_connection:
            self._mock_connection = MockDriver()
        assert self._mock_connection
        return self._mock_connection

    def get_anyway(self) -> AbstractPrinterDriver | None:
        return self._mock_connection

    def clear(self) -> None:
        self._mock_connection = None


class TestDriver:

    def test_run(self) -> None:
        test_print = AvailablePrinter.from_tuple(('driver', 'somewhere', 'TEST-1', 'lp990',))
        test_query = PrintQuery.from_tuple((['abc', 'def'], 'my label', 'testing',))
        lib = MockDriverFactory().get_driver(test_print)
        assert isinstance(lib, MockDriver)
        lib.print(test_print, test_query, BytesIO(b'ABC'))
        output_1 = 'PRINT CODE: ABC\n' \
                   + 'label: my label\n' \
                   + 'link: lp990\n' \
                   + 'backend: \n' \
                   + '---\n'
        assert output_1 == lib.get_output()
        lib.clear()
        test_print_2 = AvailablePrinter.from_tuple(('driver', 'somewhere', 'TEST-1', 'lp999',), 'spec')
        assert isinstance(lib, MockDriver)
        lib.print(test_print_2, test_query, BytesIO(b'DEF'))
        output_2 = 'PRINT CODE: DEF\n' \
                   + 'label: my label\n' \
                   + 'link: lp999\n' \
                   + 'backend: spec\n' \
                   + '---\n'
        assert output_2 == lib.get_output()
        lib.clear()

    def test_factory_unknown(self) -> None:
        test_print = AvailablePrinter.from_tuple(('driver', 'somewhere', 'TEST-1', 'lp990',))
        lib = PrinterDriverFactory()
        with pytest.raises(FileNotFoundError):
            lib.get_driver(test_print)
