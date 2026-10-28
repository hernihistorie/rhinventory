import pprint
import asyncio

from ..hhprint4 import Printing, PrintQuery, AbstractLogger, Code
from .test_connection import MockConnectionFactory
from .test_image_source import MockImageSource
from .test_driver import MockDriverFactory, MockDriverMixin, MockDriver, AbstractPrinterDriver, AvailablePrinter, PrinterDriverFactory
from io import BytesIO


class MockLogger(AbstractLogger):

    def __init__(self):
        self._output: str = ''

    def log(self, what: str):
        self._output = self._output + what + '\n'

    def struct_log(self, what: object):
        self._output = self._output + pprint.pformat(what) + '\n'

    def get_output(self) -> str:
        return self._output


class MockDriverLimited(MockDriverMixin, AbstractPrinterDriver):

    def __init__(
            self,
    ):
        super().__init__()
        self._used: list[str] = []

    def print(self, printer: AvailablePrinter, query: PrintQuery, image: BytesIO) -> None:
        if printer.model in self._used:
            raise Exception('Too much for one')
        super().print(printer, query, image)
        self._used.append(printer.model)

    def clear(self) -> None:
        super().clear()
        self._used = []


class MockDriverFactoryLimited(PrinterDriverFactory):

    def __init__(
            self,
    ):
        # MockDriverLimited.instance = None # reset singleton here
        self._mock_connection: AbstractPrinterDriver | None = None

    def get_driver(self, printer: AvailablePrinter) -> AbstractPrinterDriver:
        if not self._mock_connection:
            self._mock_connection = MockDriverLimited()
        assert self._mock_connection
        return self._mock_connection

    def get_anyway(self) -> AbstractPrinterDriver | None:
        return self._mock_connection

    def clear(self) -> None:
        self._mock_connection = None


class TestPrinting:

    def test_simple(self) -> None:
        query = PrintQuery()
        query.codes = [Code.from_str('foo')]
        output = MockLogger()
        driver = MockDriverFactory()
        driver.clear()
        lib = Printing(
            [
                ('kind 1', 'skip', 'name 1', 'is_local'),
                ('kind 2', 'mock', 'name 2', 'is_remote'),
            ],
            MockConnectionFactory(),
            MockImageSource(),
            driver,
            output,
        )
        result = asyncio.run(lib.run(query))
        print_class = driver.get_anyway()
        assert isinstance(print_class, MockDriver), 'Result must be in mock printer'
        try:
            assert '' == output.get_output(), 'Log not empty!'
            assert 0 == result, 'Something happened when nothing expected!'
            assert 'PRINT CODE: foo\nlabel: \nlink: is_remote\nbackend: \n---\n' == print_class.get_output()
        finally:
            print_class.clear()

    def test_more_printers(self) -> None:
        query = PrintQuery()
        query.codes = [Code.from_str('foo'), Code.from_str('bar')]
        output = MockLogger()
        driver = MockDriverFactoryLimited()
        driver.clear()
        lib = Printing(
            [
                ('kind 1', 'mock', 'name 1', 'is_local'),
                ('kind 2', 'mock', 'name 2', 'is_remote'),
            ],
            MockConnectionFactory(),
            MockImageSource(),
            driver,
            output,
        )
        result = asyncio.run(lib.run(query))
        print_class = driver.get_anyway()
        assert isinstance(print_class, MockDriverLimited), 'Result must be in mock printer'
        try:
            assert 'Error during work with printer *name 1*\nException(\'Too much for one\')\n' == output.get_output(), 'Log must not be empty!'
            assert 0 == result, 'Something happened when nothing expected!'
            # in fact - that mock passes just one printer, so the result is in one output
            assert 'PRINT CODE: foo\nlabel: \nlink: is_local\nbackend: \n---\nPRINT CODE: bar\nlabel: \nlink: is_remote\nbackend: \n---\n' == print_class.get_output()
        finally:
            print_class.clear()

    def test_not_enough_printers(self) -> None:
        query = PrintQuery()
        query.codes = [Code.from_str('foo'), Code.from_str('bar')]
        output = MockLogger()
        driver = MockDriverFactoryLimited()
        driver.clear()
        lib = Printing(
            [
                ('kind 1', 'skip', 'name 1', 'is_local'),
                ('kind 2', 'mock', 'name 2', 'is_remote'),
            ],
            MockConnectionFactory(),
            MockImageSource(),
            driver,
            output,
        )
        result = asyncio.run(lib.run(query))
        print_class = driver.get_anyway()
        assert isinstance(print_class, MockDriverLimited), 'Result must be in mock printer'
        try:
            assert 'Error during work with printer *name 2*\nException(\'Too much for one\')\nCodes still left:\n[\'bar\']\n' == output.get_output(), 'Log must not be empty!'
            assert 1 == result, 'Something happened when nothing expected!'
            assert 'PRINT CODE: foo\nlabel: \nlink: is_remote\nbackend: \n---\n' == print_class.get_output()
        finally:
            print_class.clear()

    def test_print_code_twice(self) -> None:
        query = PrintQuery()
        query.codes = [Code.from_str('foo'), Code.from_str('foo')]
        output = MockLogger()
        driver = MockDriverFactory()
        driver.clear()
        lib = Printing(
            [
                ('kind 1', 'mock', 'name 1', 'is_local'),
                ('kind 2', 'skip', 'name 2', 'is_remote'),
            ],
            MockConnectionFactory(),
            MockImageSource(),
            driver,
            output,
        )
        result = asyncio.run(lib.run(query))
        print_class = driver.get_anyway()
        assert isinstance(print_class, MockDriver), 'Result must be in mock printer'
        try:
            assert '' == output.get_output(), 'Log must be empty!'
            assert 0 == result, 'Something happened when nothing expected!'
            assert 'PRINT CODE: foo\nlabel: \nlink: is_local\nbackend: \n---\nPRINT CODE: foo\nlabel: \nlink: is_local\nbackend: \n---\n' == print_class.get_output()
        finally:
            print_class.clear()
