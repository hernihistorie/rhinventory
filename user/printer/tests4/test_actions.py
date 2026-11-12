from ..hhprint4 import UnixSystemActions, WindowsSystemActions, AvailablePrinter


class MockUnixActions(UnixSystemActions):

    def _local_lines(self) -> list[str]:
        return [
            'printer TEST-1 is idle.  enabled since',
            'printer TEST-2 disabled since WTFDate',
            'Unplugged or turned off',
            '',
        ]

    def _local_devices(self) -> list[str]:
        return [
            '/dev/usb_test/lp990',
            '/dev/usb_test/lp991',
            '/dev/usb_test/hidden_not_available',
            '',
        ]


class MockWindowsActions(WindowsSystemActions):

    def _local_lines(self) -> list[str]:
        return [
            '',
            'Name',
            '----',
            'QL-700',
            'Microsoft Print to PDF',
            'HP LaserJet Pro MFP M125nw',
            'Brother MFC-L2700DW series',
            '',
        ]


class TestSystemActions:

    def test_unix_is_connected_locally(self) -> None:
        lib = MockUnixActions()
        test_print_1 = AvailablePrinter.from_tuple(('driver', 'somewhere', 'TEST-1', 'lp990', None))
        test_print_2 = AvailablePrinter.from_tuple(('driver', 'somewhere', 'TEST-2', 'lp999', None))
        assert lib.is_connected_locally(test_print_1), 'Connected printer not found'
        assert not lib.is_connected_locally(test_print_2), 'Disabled printer found'

    def test_unix_is_known(self) -> None:
        lib = MockUnixActions()
        test_print_1 = AvailablePrinter.from_tuple(('driver', 'somewhere', 'TEST-1', 'lp990', None))
        test_print_2 = AvailablePrinter.from_tuple(('driver', 'somewhere', 'TEST-2', 'lp999', None))
        assert lib.is_known(test_print_1), 'Connected printer disabled'
        assert not lib.is_known(test_print_2), 'Disabled printer enabled'

    def test_windows_is_known(self) -> None:
        lib = MockWindowsActions()
        test_print_1 = AvailablePrinter.from_tuple(('driver', 'somewhere', 'TEST-1', 'lp990', 'Microsoft Print'))
        test_print_2 = AvailablePrinter.from_tuple(('driver', 'somewhere', 'TEST-2', 'lp999', 'This is not here'))
        assert lib.is_connected_locally(test_print_1), 'Connected printer not found'
        assert not lib.is_connected_locally(test_print_2), 'Disabled printer found'
