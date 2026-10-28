#!/usr/bin/python3
import pprint
import subprocess
import asyncio
from io import BytesIO
import socket
import sys
import urllib.parse

try:
    from brother_ql.conversion import convert
    from brother_ql.backends.helpers import send
    from brother_ql.raster import BrotherQLRaster
except ModuleNotFoundError:
    print("Please install brother_ql:")
    print("pip install brother_ql")
    exit(1)

try:
    import aiohttp
except ModuleNotFoundError:
    print("Please install aiohttp:")
    print("pip install aiohttp[speedups]")
    exit(1)


LABEL_URL = "https://inventory.herniarchiv.cz/label/asset/"
KEY = "Zu2eebo9oNgeequee6ie"

print("hhprint v3.0")


class AvailableTargets:
    """
    Where can be printer located
    """

    DEV = 'device' # directly on device
    NET = 'network' # somewhere in network

    @staticmethod
    def get_local(conf: tuple[str,str,str,str]) -> bool:
        return AvailableTargets.DEV == conf[1]

    @staticmethod
    def get_network(conf: tuple[str,str,str,str]) -> bool:
        return AvailableTargets.NET == conf[1]


class AvailablePrinters:
    """
    What printers are available and set here
    """

    BROTHER_LABEL = 'brother_label'


# configuration of printers
# it's in tuples, each printer has own definition
# what printer group, target (dev, net), printer name - model to find, path to where it will be sent
available_printers: list[tuple[str,str,str,str]] = [
    (AvailablePrinters.BROTHER_LABEL, AvailableTargets.DEV, 'QL-700', '/dev/usb/lp0'), # strahov cerna
    (AvailablePrinters.BROTHER_LABEL, AvailableTargets.DEV, 'QL-700', '/dev/usb/lp1'),
    (AvailablePrinters.BROTHER_LABEL, AvailableTargets.DEV, 'QL-700', '/dev/usb/lp2'),
    (AvailablePrinters.BROTHER_LABEL, AvailableTargets.DEV, 'QL-700', '/dev/usb/lp3'),
    (AvailablePrinters.BROTHER_LABEL, AvailableTargets.DEV, 'QL-600', '/dev/usb/lp0'), # strahov modra
    (AvailablePrinters.BROTHER_LABEL, AvailableTargets.DEV, 'QL-600', '/dev/usb/lp1'),
    (AvailablePrinters.BROTHER_LABEL, AvailableTargets.DEV, 'QL-600', '/dev/usb/lp2'),
    (AvailablePrinters.BROTHER_LABEL, AvailableTargets.DEV, 'QL-600', '/dev/usb/lp3'),
    (AvailablePrinters.BROTHER_LABEL, AvailableTargets.NET, 'QL-700', 'tcp://10.8.1.252:9100'), # vrsky cerna na stole s tiskarnama
]


class PrintQuery:
    """
    Query data incoming from remote source
    """

    codes: list[str] = []
    label: str = ''
    path: str = ''


class AvailablePrinter:
    """
    Info about each available printer
    """

    group: str = ''
    target: str = ''
    model: str = ''
    link: str = ''
    backend: str = ''

    @staticmethod
    def from_tuple(data: tuple[str,str,str,str], backend: str = '') -> 'AvailablePrinter':
        use_printer = AvailablePrinter()
        use_printer.group = data[0]
        use_printer.target = data[1]
        use_printer.model = data[2]
        use_printer.link = data[3]
        use_printer.backend = backend
        return use_printer


class AbstractSystemActions:

    def get_locally_known(self) -> list[AvailablePrinter]:
        raise NotImplementedError('Must be implemented first!')

    def ping_available_network(self, address: urllib.parse.ParseResult) -> bool:
        """
        Ping remote source

        Original variant without need of "ping" command
        """
        try:
            socket.setdefaulttimeout(3)
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((address.hostname, address.port))
        except OSError:
            return False
        else:
            s.close()
            return True

    def get_network_known(self) -> list[AvailablePrinter]:
        remote_printers = filter(AvailableTargets.get_network, available_printers)
        use_printers: list[AvailablePrinter] = []
        for remote_printer in remote_printers:
            remote_printer_class = AvailablePrinter.from_tuple(remote_printer, 'network')
            if self.ping_available_network(AbstractSystemActions._parse_address_for_ping(remote_printer_class)):
                use_printers.append(remote_printer_class)
        return use_printers

    @staticmethod
    def _parse_address_for_ping(addr: AvailablePrinter) -> urllib.parse.ParseResult:
        return urllib.parse.urlparse(addr.link)


class UnixSystemActions(AbstractSystemActions):
    """
    Work over *nix systems where the CLI commands are the usual way to get info
    """

    def get_locally_known(self) -> list[AvailablePrinter]:
        local_devices = UnixSystemActions._local_devices()
        local_printers = filter(AvailableTargets.get_local, available_printers)
        locally_known_printers = UnixSystemActions._local_lines()
        use_printers: list[AvailablePrinter] = []
        for local_printer in local_printers:
            local_printer_class = AvailablePrinter.from_tuple(local_printer)
            for locally_known_printer in locally_known_printers:
                locally_known_printer = locally_known_printer.strip()
                if '' == locally_known_printer:
                    # skip empty string
                    continue

                if local_printer_class.model in locally_known_printer:
                    # we got the printer
                    if 'disabled' in locally_known_printer:
                        # this printer is now disabled - choose another one
                        continue
                    if local_printer_class.link not in local_devices:
                        # skip for unknown locations in /dev/usb/*
                        continue

                    # printer is OK - add to list
                    use_printers.append(local_printer_class)
        return use_printers

    @staticmethod
    def _local_lines() -> list[str]:
        locally_known_printers = subprocess.run(['lpstat', '-p'], capture_output=True)
        return locally_known_printers.stdout.decode().split('\n')

    @staticmethod
    def _local_devices() -> list[str]:
        locally_known_printers = subprocess.run(['ls', '/dev/usb'], capture_output=True)
        paths = locally_known_printers.stdout.decode().split('\n')
        all_known: list[str] = []
        for path in paths:
            if 'lp' in path:
                all_known.append('/dev/usb/' + path)
        return all_known


class WindowsSystemActions(AbstractSystemActions):
    """
    Work over Windows OS, where is PowerShell to get info about connected printers and their drivers
    """

    def get_locally_known(self) -> list[AvailablePrinter]:
        # todo: dopsat podle windows spec; pripadne prihodit dalsi parametry do konfiguracni tuply
        raise NotImplementedError('TBA')

    @staticmethod
    def _local_lines() -> list[str]:
        locally_known_printers = subprocess.run(['powershell', '-Command', 'Get-Printer | Format-Table Name, Type, DriverName, PortName, Shared'], capture_output=True)
        return locally_known_printers.stdout.decode().split('\n')


class SystemActionFactory:
    """
    Actions which determine what system base will be used and how to get necessary data and connections
    """

    @staticmethod
    def get_actions() -> AbstractSystemActions:
        # it's different for Windows, Linux and MacOS
        import platform

        if 'Windows' == platform.system():
            return WindowsSystemActions()

        return UnixSystemActions()


class AbstractPrinter:
    """
    Printer class

    Each printer is child of this and implements following method
    """

    async def print(self, printer: AvailablePrinter, query: PrintQuery, code: str):
        raise NotImplementedError('Must be implemented first!')


class BrotherLabelPrinter(AbstractPrinter):
    """
    Small label printers from Brother
    """

    async def print(self, printer: AvailablePrinter, query: PrintQuery, code: str) -> None:
        async with aiohttp.ClientSession() as session:
            web_code = code.lower()
            for prefix in ['rh', 'hh']:
                web_code = web_code.removeprefix(prefix)
            label_url = LABEL_URL + web_code + "?key=" + KEY
            print(label_url)
            async with session.get(label_url) as response:
                image = BytesIO(await response.read())

                # https://github.com/pklaus/brother_ql/blob/master/brother_ql/cli.py#L134

                qlr = BrotherQLRaster(printer.model)
                qlr.exception_on_warning = True
                instructions = convert(qlr=qlr, images=[image], label=query.label, cut=True)
                send(instructions=instructions, printer_identifier=printer.link, backend_identifier=printer.backend,
                     blocking=True)


class PrinterFactory:
    """
    Get correct printer based on available ones and their configuration
    """

    @staticmethod
    def get_printer(printer: AvailablePrinter) -> AbstractPrinter:
        if AvailablePrinters.BROTHER_LABEL == printer.group:
            return BrotherLabelPrinter()

        raise FileNotFoundError('No printer processor with this settings!')


class ParseParams:
    """
    Parse codes which came from external source and will be used for printing
    """

    @staticmethod
    def parse_arguments(query: str) -> PrintQuery:
        incoming_query = PrintQuery()
        parsed_url = urllib.parse.urlparse(query)
        incoming_query.path = parsed_url.path
        qs = urllib.parse.parse_qs(str(parsed_url.query.replace('&amp;', '&')))
        incoming_query.codes = list(filter(None, ParseParams._parse_param(qs, 'codes').split(';')))
        incoming_query.label = ParseParams._parse_param(qs, 'label', '62')
        return incoming_query

    @staticmethod
    def _parse_param(qs: dict[str | bytes, list[str | bytes]], key: str, default: str = '') -> str:
        param = qs.get(key)
        if not param:
            return default
        try:
            obtained = param[0]
        except IndexError:
            return default
        if isinstance(obtained, str):
            return obtained
        if isinstance(obtained, bytes):
            return obtained.decode('utf-8')
        return default


class Printing:
    """
    The printing class itself

    Covers all print actions within this script
    """

    def __init__(self):
        self._action_class: AbstractSystemActions = SystemActionFactory.get_actions()

    async def print(self, params: PrintQuery) -> int:
        # get only local printers first
        for code in params.codes:
            try:
                await self._print_locally(params, code)
            except FileNotFoundError:
                try:
                    await self._print_network(params, code)
                except FileNotFoundError:
                    return 1 # error - cannot print
        return 0

    async def _print_locally(self, params: PrintQuery, code: str) -> str:
        locally_known_printers = self._action_class.get_locally_known()
        for locally_known_printer in locally_known_printers:
            printer = PrinterFactory.get_printer(locally_known_printer)
            try:
                await printer.print(locally_known_printer, params, code)
                return code
            except FileNotFoundError:
                print(
                    f'The printer *{locally_known_printer.model}* has not been found on *{locally_known_printer.link}*')
                locally_known_printers.remove(locally_known_printer)
            except PermissionError:
                print(f'The printer *{locally_known_printer.model}* has no rights')
                locally_known_printers.remove(locally_known_printer)
            except BaseException as ex:
                print(ex.__str__)
                # try next one
        raise FileNotFoundError('No local printer found')

    async def _print_network(self, params: PrintQuery, code: str) -> str:
        network_known_printers = self._action_class.get_network_known()
        for network_printer in network_known_printers:
            printer = PrinterFactory.get_printer(network_printer)
            try:
                await printer.print(network_printer, params, code)
                return code
            except BaseException as ex:
                print(ex.__str__)
                # try next one
        raise FileNotFoundError('No network printer found')


try:
    arg = sys.argv[1]
except IndexError:
    arg = ''

print_query = ParseParams.parse_arguments(arg)

if 'print' == print_query.path:
    exit(asyncio.run(Printing().print(print_query)))
else:
    print("Unknown action", print_query.path)
    exit(1)
