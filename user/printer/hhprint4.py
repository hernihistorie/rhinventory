#!/usr/bin/python3
import pprint
import subprocess
import asyncio
from io import BytesIO
import socket
import sys
import urllib.parse
from enum import Enum

try:
    import aiohttp
except ModuleNotFoundError:
    print("Please install aiohttp:")
    print("pip install aiohttp[speedups]")
    exit(1)

LABEL_URL = "https://inventory.herniarchiv.cz/label/asset/"
KEY = "Zu2eebo9oNgeequee6ie"

print("hhprint v4.0")


class AvailableTargets(str, Enum):
    """
    Where can be printer located
    """

    LOCAL = 'device'  # directly on device
    NETWORK = 'network'  # somewhere in network


class AvailablePrinters(str, Enum):
    """
    What printers are available and set here
    """

    BROTHER_LABEL = 'brother_label'


# configuration of printers
# it's in tuples, each printer has own definition
# what printer group, target (dev, net), printer name - model to find, path to where it will be sent
# preferred style is local printers first - ping on remotes will delay them
available_printers: list[tuple[str, str, str, str, str | None]] = [
    # strahov cerna lokal
    (AvailablePrinters.BROTHER_LABEL, AvailableTargets.LOCAL, 'QL-700', '/dev/usb/lp0', None),
    (AvailablePrinters.BROTHER_LABEL, AvailableTargets.LOCAL, 'QL-700', '/dev/usb/lp1', None),
    (AvailablePrinters.BROTHER_LABEL, AvailableTargets.LOCAL, 'QL-700', '/dev/usb/lp2', None),
    (AvailablePrinters.BROTHER_LABEL, AvailableTargets.LOCAL, 'QL-700', '/dev/usb/lp3', None),
    # strahov modra lokal
    (AvailablePrinters.BROTHER_LABEL, AvailableTargets.LOCAL, 'QL-600', '/dev/usb/lp0', None),
    (AvailablePrinters.BROTHER_LABEL, AvailableTargets.LOCAL, 'QL-600', '/dev/usb/lp1', None),
    (AvailablePrinters.BROTHER_LABEL, AvailableTargets.LOCAL, 'QL-600', '/dev/usb/lp2', None),
    (AvailablePrinters.BROTHER_LABEL, AvailableTargets.LOCAL, 'QL-600', '/dev/usb/lp3', None),
    # vrsky cerna sit na stole s tiskarnama
    (AvailablePrinters.BROTHER_LABEL, AvailableTargets.NETWORK, 'QL-700', 'tcp://10.8.1.252:9100', None),
]


class Code:
    """
    About obtained code
    """
    code: str = ''
    used: bool = False

    @staticmethod
    def from_str(code: str) -> 'Code':
        out = Code()
        out.code = code
        return out

    def __str__(self) -> str:
        return self.code


class PrintQuery:
    """
    Query data incoming from remote source
    """

    codes: list[Code] = []
    label: str = ''
    path: str = ''

    @staticmethod
    def from_tuple(data: tuple[list[str], str, str]) -> 'PrintQuery':
        # mainly for tests
        use_query = PrintQuery()
        use_query.codes = list(map(lambda x: Code.from_str(x), data[0]))
        use_query.label = data[1]
        use_query.path = data[2]
        return use_query


class AvailablePrinter:
    """
    Info about each available printer
    """

    group: str = ''
    location: str = ''
    model: str = ''
    link: str = ''
    windows_name: str | None = None
    backend: str = ''

    @staticmethod
    def from_tuple(data: tuple[str, str, str, str, str | None], backend: str = '') -> 'AvailablePrinter':
        use_printer = AvailablePrinter()
        use_printer.group = data[0]
        use_printer.location = data[1]
        use_printer.model = data[2]
        use_printer.link = data[3]
        use_printer.windows_name = data[4]
        use_printer.backend = backend
        return use_printer


class AbstractLogger:

    def log(self, what: str):
        raise NotImplementedError('TBA')

    def struct_log(self, what: object):
        raise NotImplementedError('TBA')


class CliLogger(AbstractLogger):

    def log(self, what: str):
        print(what)

    def struct_log(self, what: object):
        pprint.pprint(what)


class AbstractSystemActions:
    instance = None

    def __new__(
            cls,
    ):
        # singleton during run - data was not changed
        if cls.instance is None:
            cls.instance = super().__new__(cls)
        return cls.instance

    def is_connected_locally(self, printer: AvailablePrinter) -> bool:
        """
        Is passed printer connected locally to the machine?
        """
        raise NotImplementedError('Must be implemented first!')

    def is_known(self, printer: AvailablePrinter) -> bool:
        """
        Is passed printer enabled - installed with available drivers
        """
        raise NotImplementedError('Must be implemented first!')


class UnixSystemActions(AbstractSystemActions):
    """
    Work over *nix systems where the CLI commands are the usual way to get info
    """

    def __init__(self):
        # caches
        self._known_devices: list[str] = []  # /dev/usb/*
        self._connected_printers: list[str] = []  # printer XYZ status IDLE ...

    def is_connected_locally(self, printer: AvailablePrinter) -> bool:
        for connected_printer in self._get_connected():
            connected_printer = connected_printer.strip()
            if '' == connected_printer:
                # skip empty string
                continue

            if printer.model in connected_printer:
                # we got the printer
                if 'disabled' in connected_printer:
                    # this printer is now disabled - choose another one;
                    # if there is another with the same name and configuration it must pass
                    continue
                return True
        return False

    def is_known(self, printer: AvailablePrinter) -> bool:
        for known_device in self._get_known_devices():
            if printer.link in known_device:
                # get known locations in /dev/usb/*
                return True
        return False

    def _get_known_devices(self) -> list[str]:
        if not len(self._known_devices):
            self._known_devices = self._filter_paths(self._local_devices())
        return self._known_devices

    def _get_connected(self) -> list[str]:
        if not len(self._connected_printers):
            self._connected_printers = self._local_lines()
        return self._connected_printers

    def _local_lines(self) -> list[str]:
        locally_known_printers = subprocess.run(['lpstat', '-p'], capture_output=True)
        return locally_known_printers.stdout.decode().split('\n')

    def _local_devices(self) -> list[str]:
        locally_known_printers = subprocess.run(['ls', '/dev/usb'], capture_output=True)
        return locally_known_printers.stdout.decode().split('\n')

    def _filter_paths(self, paths: list[str]) -> list[str]:
        all_known: list[str] = []
        for path in paths:
            if 'lp' in path:
                all_known.append('/dev/usb/' + path)
        return all_known


class WindowsSystemActions(AbstractSystemActions):
    """
    Work over Windows OS, where is PowerShell to get info about connected printers and their drivers
    """

    def __init__(self):
        # caches
        self._known_devices: list[str] = []  # /dev/usb/*
        self._connected_printers: list[str] = []  # printer XYZ status IDLE ...

    def is_connected_locally(self, printer: AvailablePrinter) -> bool:
        # todo: dopsat podle windows spec
        #       tisk probehne oklikou - protoze windows print neumi grafiku, ale ta je tady podstatna (ikona a carovy kod jsou obrazky)
        #       proto se nejdriv cely vysledek dotazu nacpe do souboru a az to se pomoci cmdletu posle na tiskarnu (pres mspaint)
        #       nebo se nejdriv cely vysledek dotazu nacpe do PDF a az to se pomoci cmdletu posle na tiskarnu (pres acrobat)
        #       ale nejdriv je potreba zdetekovat, jestli v systemu tiskarna vubec je - to je prace tehle classy
        for connected_printer in self._get_connected():
            connected_printer = connected_printer.strip()
            if '' == connected_printer:
                # skip empty string
                continue

            if printer.model in connected_printer:
                # we got the printer
                if 'disabled' in connected_printer:
                    # this printer is now disabled - choose another one;
                    # if there is another with the same name and configuration it must pass
                    continue
                return True
        return False

    def _get_connected(self) -> list[str]:
        if not len(self._connected_printers):
            self._connected_printers = self._local_lines()
        return self._connected_printers

    def _local_lines(self) -> list[str]:
        locally_known_printers = subprocess.run(
            ['powershell', '-Command', 'Get-Printer | Format-Table Name, Type, DriverName, PortName, Shared'],
            capture_output=True)
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


class AbstractPrinterDriver:
    """
    Printer class

    Each printer is child of this and implements following method
    """

    def print(self, printer: AvailablePrinter, query: PrintQuery, image: BytesIO) -> None:
        raise NotImplementedError('Must be implemented first!')


class WindowsPrinterDriver(AbstractPrinterDriver):
    """
    Universal pass for Windows

    It prints through the mspaint app
    @link https://thatpainter.com/microsoft-paint-command-line-options-open-print-and-automate-paint/
    @link https://tutorialreference.com/batch-scripting/examples/faq/batch-script-how-to-open-ms-paint
    """

    def print(self, printer: AvailablePrinter, query: PrintQuery, image: BytesIO) -> None:
        import tempfile
        import os

        # first save as temporary file
        temp_file = tempfile.NamedTemporaryFile(delete=False)
        temp_file.seek(0)
        temp_file.write(image.getvalue()) # image is PNG
        temp_file.close()

        # then cmd to printer
        subprocess.run(
            ['mspaint', '/pt', str(printer.windows_name), temp_file.name],
            capture_output=True)
        os.remove(temp_file.name)


class BrotherLabelPrinterDriver(AbstractPrinterDriver):
    """
    Small label printers from Brother
    """

    def __init__(self):
        # check import
        try:
            from brother_ql.conversion import convert
            from brother_ql.backends.helpers import send
            from brother_ql.raster import BrotherQLRaster
        except ModuleNotFoundError:
            print("Please install brother_ql:")
            print("pip install brother_ql")
            exit(1)

    def print(self, printer: AvailablePrinter, query: PrintQuery, image: BytesIO) -> None:
        # raw import
        from brother_ql.conversion import convert
        from brother_ql.backends.helpers import send
        from brother_ql.raster import BrotherQLRaster

        # https://github.com/pklaus/brother_ql/blob/master/brother_ql/cli.py#L134
        qlr = BrotherQLRaster(printer.model)
        qlr.exception_on_warning = True
        instructions = convert(qlr, images=[image], label=query.label, cut=True)
        send(instructions, printer.link, printer.backend, True)


class PrinterDriverFactory:
    """
    Get printer driver based on their configuration
    """

    def get_driver(self, printer: AvailablePrinter) -> AbstractPrinterDriver:
        import platform
        # first by OS - Windows got a different treatment
        if 'Windows' == platform.system():
            return WindowsPrinterDriver()

        # then group
        if AvailablePrinters.BROTHER_LABEL == printer.group:
            return BrotherLabelPrinterDriver()

        raise FileNotFoundError('No printer driver with this settings!')


class AbstractImageSource:
    """
    What source will be used to get image which will be printed
    """

    async def get_image(self, code: Code) -> BytesIO:
        raise NotImplementedError('TBA')


class ImageSourceRemoteQuery(AbstractImageSource):
    """
    Query to remote machine to get image for printing
    """

    def __init__(
            self,
            label_url: str = '',
            key: str = '',
            logger: AbstractLogger = CliLogger(),
    ):
        self._label_url: str = label_url
        self._key: str = key
        self._logger: AbstractLogger = logger

    async def get_image(self, code: Code) -> BytesIO:
        async with aiohttp.ClientSession() as session:
            web_code = code.code.lower()
            for prefix in ['rh', 'hh']:
                web_code = web_code.removeprefix(prefix)
            label_url = self._label_url + web_code + "?key=" + self._key
            self._logger.log(label_url)
            async with session.get(label_url) as response:
                if 200 == response.status:
                    return BytesIO(await response.read()) # returns PNG file when everything is OK
                # otherwise log the response and kill next processing
                self._logger.log(f'The code *{code.code}* got response code *{response.status}*.')
                self._logger.struct_log(await response.read())
                raise FileNotFoundError(f'The code *{code.code}* returns no image!')


class AbstractConnection:
    """
    Where the printer is connected in the means of computer (locally via USB/LPT or remote network)
    """

    def __init__(self, printer: AvailablePrinter):
        self._printer: AvailablePrinter = printer

    def can(self) -> bool:
        """
        Check if this combination is usable
        """
        raise NotImplementedError('Must be implemented first!')


class ConnectedLocally(AbstractConnection):
    """
    Connection is directly to the machine
    """

    def __init__(
            self,
            printer: AvailablePrinter,
            system_actions: AbstractSystemActions | None = None,
    ):
        super().__init__(printer)
        self._system_actions: AbstractSystemActions = system_actions or SystemActionFactory.get_actions()

    def can(self) -> bool:
        return self._system_actions.is_connected_locally(self._printer) and self._system_actions.is_known(self._printer)


class ConnectedViaNetwork(AbstractConnection):
    """
    Connection is somewhere over the network
    """

    def can(self) -> bool:
        return self._ping_available_network(ConnectedViaNetwork._parse_address_for_ping(self._printer))

    def _ping_available_network(self, address: urllib.parse.ParseResult) -> bool:
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

    @staticmethod
    def _parse_address_for_ping(printer: AvailablePrinter) -> urllib.parse.ParseResult:
        return urllib.parse.urlparse(printer.link)


class ConnectionFactory:
    """
    Get printers based on their connections in config
    """

    def get_location(self, printer: AvailablePrinter) -> AbstractConnection:
        if AvailableTargets.LOCAL == printer.location:
            return ConnectedLocally(printer)

        if AvailableTargets.NETWORK == printer.location:
            return ConnectedViaNetwork(printer)

        raise FileNotFoundError('No printer connection with this settings!')


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
        incoming_query.codes = list(map(lambda x: Code.from_str(x), filter(None, ParseParams._parse_param(qs, 'codes').split(';'))))
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

    def __init__(
            self,
            use_printers: list[tuple[str, str, str, str, str | None]],
            location: ConnectionFactory = ConnectionFactory(),
            image_source: AbstractImageSource | None = None,
            driver_factory: PrinterDriverFactory | None = None,
            logger: AbstractLogger = CliLogger(),
    ):
        self._available_printers: list[tuple[str, str, str, str, str | None]] = use_printers
        self._location: ConnectionFactory = location
        self._driver_factory: PrinterDriverFactory = driver_factory or PrinterDriverFactory()
        self._image_source: AbstractImageSource = image_source or ImageSourceRemoteQuery()
        self._logger: AbstractLogger = logger

    async def run(self, params: PrintQuery) -> int:
        """
        Chained runner

        Order of printers in configuration sets the order of possible options
        Earlier printer is preferred before later one
        There is no difference between locally and remotely set printers
        """
        codes_avail: list[Code] = params.codes
        for printer in self._available_printers:
            printer_class = AvailablePrinter.from_tuple(printer)
            location = self._location.get_location(printer_class)
            if location.can():
                try:
                    driver = self._driver_factory.get_driver(printer_class)
                    for code in codes_avail:
                        if code.used:
                            # already used - skip
                            continue

                        try:
                            # try to get image from remote
                            image = await self._image_source.get_image(code)
                        except Exception as ex_1:
                            # log and mark skipped for next step
                            code.used = True
                            self._logger.log(pprint.pformat(ex_1))
                            continue

                        try:
                            # send image to printer to process
                            driver.print(printer_class, params, image)
                            code.used = True
                        except Exception as ex_2:
                            self._logger.log(f'Error during work with printer *{printer_class.model}*')
                            self._logger.log(pprint.pformat(ex_2))

                except Exception as ex_3:
                    # another printer will do
                    self._logger.log(
                        f'The printer *{printer_class.model}* on *{printer_class.link}* has problem and must be skipped')
                    self._logger.log(pprint.pformat(ex_3))

            if 1 > Printing._count_codes_left(codes_avail):
                break

        if 1 > Printing._count_codes_left(codes_avail):
            return 0
        self._logger.log('Codes still left:')
        self._logger.struct_log(Printing._get_codes_names(Printing._get_codes_left(codes_avail)))
        return 1

    @staticmethod
    def _count_codes_left(codes: list[Code]) -> int:
        return len(Printing._get_codes_left(codes))

    @staticmethod
    def _get_codes_left(codes: list[Code]) -> list[Code]:
        return list(filter(lambda x: not x.used, codes))

    @staticmethod
    def _get_codes_names(codes: list[Code]) -> list[str]:
        return list(map(lambda x: x.code, codes))


if __name__ == "__main__":
    # skip when in tests
    try:
        arg = sys.argv[1]
    except IndexError:
        arg = ''

    print_query = ParseParams.parse_arguments(arg)

    if 'print' == print_query.path:
        exit(
            asyncio.run(
                Printing(
                    available_printers,
                    ConnectionFactory(),
                    ImageSourceRemoteQuery(LABEL_URL, KEY),
                ).run(print_query)
            )
        )
    else:
        print("Unknown action", print_query.path)
        exit(1)
