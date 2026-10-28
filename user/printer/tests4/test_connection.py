from ..hhprint4 import AbstractConnection, ConnectionFactory, AbstractSystemActions, AvailablePrinter, ConnectedLocally, ConnectedViaNetwork
import urllib.parse
import pytest


class MockSystemActions(AbstractSystemActions):

    def is_connected_locally(self, printer: AvailablePrinter) -> bool:
        return 'mock' == printer.link

    def is_known(self, printer: AvailablePrinter) -> bool:
        return 'mock' == printer.backend


class MockConnection(AbstractConnection):

    def can(self) -> bool:
        return 'mock' == self._printer.location


class MockConnectionFactory(ConnectionFactory):

    def get_location(self, printer: AvailablePrinter) -> AbstractConnection:
        return MockConnection(printer)


class MockViaNetwork(ConnectedViaNetwork):

    def _ping_available_network(self, address: urllib.parse.ParseResult) -> bool:
        return 'pass' == address.scheme


class TestConnections:

    def test_connect_local_ok(self) -> None:
        test_print = AvailablePrinter.from_tuple(('driver', 'somewhere', 'TEST-1', 'mock',), 'mock')
        lib = ConnectedLocally(test_print, MockSystemActions())
        assert lib.can(), 'The connection config say ok, but the result is not'

    def test_connect_local_fail(self) -> None:
        test_print = AvailablePrinter.from_tuple(('driver', 'somewhere', 'TEST-1', 'nope',))
        lib = ConnectedLocally(test_print, MockSystemActions())
        assert not lib.can(), 'The connection config say no, but the result passes'

    def test_connect_network_ok(self) -> None:
        test_print = AvailablePrinter.from_tuple(('driver', 'somewhere', 'TEST-1', 'pass://xx.yy.z',))
        lib = MockViaNetwork(test_print)
        assert lib.can(), 'The connection config say ok, but the result is not'

    def test_connect_network_fail(self) -> None:
        test_print = AvailablePrinter.from_tuple(('driver', 'somewhere', 'TEST-1', 'nope://xx.yy.z',))
        lib = MockViaNetwork(test_print)
        assert not lib.can(), 'The connection config say no, but the result passes'

    def test_factory_unknown(self) -> None:
        test_print = AvailablePrinter.from_tuple(('driver', 'somewhere', 'TEST-1', 'lp990',))
        lib = ConnectionFactory()
        with pytest.raises(FileNotFoundError):
            lib.get_location(test_print)
