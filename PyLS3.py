#!/usr/bin/python3
import asyncio
from bleak import BleakScanner, BleakClient
import serial_asyncio
import serial.tools.list_ports
from collections import deque
from datetime import datetime, timedelta
from typing import Any, Awaitable
from abc import ABC, abstractmethod
import yaml
import argparse
import ast
import os
import re
import logging
from PyLS3_plot import plot_csv
from aioconsole import aprint, ainput
import platform
import warnings



class CustomFormatter(logging.Formatter):
    grey = "\x1b[1;30m"
    green = "\x1b[32m"
    blue = "\x1b[1;34m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"
    format = "%(asctime)s - %(name)s - %(levelname)8s - %(message)s (%(filename)s:%(lineno)d)"

    FORMATS = {
        logging.DEBUG: green + format + reset,
        logging.INFO: blue + format + reset,
        logging.WARNING: yellow + format + reset,
        logging.ERROR: red + format + reset,
        logging.CRITICAL: bold_red + format + reset
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)


class CustomFormatterNoColor(logging.Formatter):
    reset = "\x1b[0m"
    format = "%(asctime)s - %(name)s - %(levelname)8s - %(message)s (%(filename)s:%(lineno)d)"

    FORMATS = {
        logging.DEBUG: format,
        logging.INFO: format,
        logging.WARNING: format,
        logging.ERROR: format,
        logging.CRITICAL: format
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)


def make_dir(dir_name: str) -> None:
    try:
        os.makedirs(dir_name)
    except OSError:
        pass  # already exists


def norm_file_and_path(file: str):
    file_name = os.path.basename(file)
    dir_name = os.path.normpath((os.path.dirname(file)))
    # Append Script-Dir for non absoulut Paths
    if re.search('^([A-Za-z]:)?\\\\', "\\\\"):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        dir_name = os.path.join(script_dir, dir_name)
    file = os.path.join(dir_name, file_name)
    return file_name, dir_name, file


class Dumper(yaml.Dumper):
    def increase_indent(self, flow=False, *args, **kwargs):
        return super().increase_indent(flow=flow, indentless=False)

    def ignore_aliases(self, data):
        return True


def int_constructor(loader, node):
    return int


def float_constructor(loader, node):
    return float


def str_constructor(loader, node):
    return str


def none_constructor(loader, node):
    return None


def yaml_load(file: str) -> dict:
    """
    This function Loads a yaml file to a dictionary
    :param file: yaml File name
    :return: dictionary
    """
    yaml.add_constructor(u'!int', int_constructor, Loader=yaml.SafeLoader)
    yaml.add_constructor(u'!float', float_constructor, Loader=yaml.SafeLoader)
    yaml.add_constructor(u'!str', str_constructor, Loader=yaml.SafeLoader)
    yaml.add_constructor(u'!None', none_constructor, Loader=yaml.SafeLoader)
    with open(file, "r") as stream:
        try:
            data = yaml.safe_load(stream)
        except yaml.YAMLError as exc:
            logger.error(f"Exception: {exc}")
    return data


# not optimal
def classtype_representer(dumper, data):
    if data is int:
        return dumper.represent_scalar(u'!int', '', style='')
    elif data is float:
        return dumper.represent_scalar(u'!float', u'', style='')
        # return dumper.represent_scalar('tag:yaml.org,2002:str', u'!float', style='"')
        # return dumper.represent_str(u'!float')
    elif data is str:
        return dumper.represent_scalar(u'!str', '', style='')
        # return dumper.represent_str(u'!str')
    return dumper.represent_str('!unknown')


def none_representer(dumper, data):
    return dumper.represent_scalar(u'!None', '', style='')


def yaml_save(data: dict, file: str) -> None:
    """
    This function saves a dictionary to a yaml file
    :param data: dictionary
    :param file: yaml file
    :return: None
    """
    yaml.add_representer(type(int), classtype_representer)
    yaml.add_representer(type(None), none_representer)
    # yaml.dumper.Dumper.represent_data('x','y')
    # yaml.dump(int)
    file_name, dir_name, file = norm_file_and_path(file)
    make_dir(dir_name)
    with open(file, 'w') as outfile:
        yaml.dump(data, outfile, sort_keys=False, width=float("inf"), indent=4, Dumper=Dumper)


def load_PyLS3_Conf(args):
    # Load configuration files
    PyLS3_AppCfg = yaml_load(args.appcfg)
    PyLS3_UserCfg = yaml_load(args.usercfg)
    # PyLS3_Conf = {**PyLS3_AppCfg, **PyLS3_UserCfg}   # UserCfg overrides AppCfg
    PyLS3_Conf = deep_merge(PyLS3_AppCfg, PyLS3_UserCfg)
    if args.conf:
        args_dict = gen_args_dict(args.conf)
        PyLS3_Conf = deep_merge(PyLS3_Conf, args_dict)
        del args_dict
    return PyLS3_Conf


def csv_save(device_name, data) -> str:
    """
    Save data to an csv File
    :param device_name:
    :param data:
    :return:
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    dir_name = os.path.join(script_dir, PyLS3_Conf['Path']['Data'])
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    file_name = f"{timestamp}_{device_name}.csv"
    file = os.path.join(dir_name, file_name)
    # file_name, dir_name, file = norm_file_and_path(file)
    make_dir(dir_name)

    with open(file, 'w') as outfile:
        for line in data:
            outfile.write(line + "\n")
        outfile.close()

    return file


def csv_save_file(data: Any, file: str, Override: bool = "True"):
    """
    Save data to an csv File
    :param data:
    :param file:
    :return:
    """
    file_name, dir_name, file = norm_file_and_path(file)

    if os.path.isfile(file) and not Override:
        logger.warning(f"INFO> File '{file}' already exists, skipping.")
        return

    make_dir(dir_name)
    with open(file, 'w') as outfile:
        for line in data:
            outfile.write(line + "\n")
        outfile.close()


def hex_to_string(hex) -> str:
    """
    Convert hex string to UTF8 String
    :param hex: hex string
    :return: utf-8 string
    """
    if hex[:2] == '0x':
        hex = hex[2:]
    string_value = bytes.fromhex(hex).decode('utf-8')
    return string_value


def find_nearest_lower(value_list, value):
    candidates = [item for item in value_list if item < value]
    if not candidates: return None
    return max(candidates)


def find_nearest_lowerequal(value_list, value):
    candidates = [item for item in value_list if item <= value]
    if not candidates: return None
    return max(candidates)


nextHighest = lambda seq, x: min([(i-x, i) for i in seq if x <= i] or [(0, None)])[1]
nextLowest  = lambda seq, x: min([(x-i, i) for i in seq if x >= i] or [(0, None)])[1]


def split(string):
    if isinstance(string, int):
        string = str(string)
    return [char for char in string]


def string_to_dict(keys, value=None):
    key = keys.split(':')
    if not value:
        value = key.pop()
        # convert strings
        if re.search("^[0-9]+$", value):
            value = re.sub('\"\'', '', value)
        elif re.search("^[0-9.]+$", value):
            value = float(value)
        elif re.search("^\[.*]$", value):
            value = ast.literal_eval(value)
    if len(key) == 1:
        return {key[0]: value}
    else:
        return string_to_dict(':'.join(key[:-1]), {key[-1]: value})


def deep_merge(a, b):
    """
    Merge two values, with `b` taking precedence over `a`.

    Semantics:
    - If either `a` or `b` is not a dictionary, `a` will be returned only if
      `b` is `None`. Otherwise `b` will be returned.
    - If both values are dictionaries, they are merged as follows:
        * Each key that is found only in `a` or only in `b` will be included in
          the output collection with its value intact.
        * For any key in common between `a` and `b`, the corresponding values
          will be merged with the same semantics.
    """
    if not isinstance(a, dict) or not isinstance(b, dict):
        return a if b is None else b
    else:
        # If we're here, both a and b must be dictionaries or subtypes thereof.

        # Compute set of all keys in both dictionaries.
        keys = set(a.keys()) | set(b.keys())

        # Build output dictionary, merging recursively values with common keys,
        # where `None` is used to mean the absence of a value.
        return {
            key: deep_merge(a.get(key), b.get(key))
            for key in keys
        }


def gen_args_dict(conf_string_list):
    args_dict = dict()
    for conf_string in conf_string_list:
        d = string_to_dict(conf_string)
        args_dict = deep_merge(args_dict, d)
    return args_dict


def LS3crc(command: str) -> str:
    """
    Calculate CRC for Linescale3 Commands
    :param command: LS3 command without crc
    :return: LS3 CRC
    """
    crc = 0
    command = command.replace(" ", "")          # Remove space
    n = 2
    # for i in command.split():
    for i in range(0, len(command), n):
        v = command[i:i+n]
        crc += int(f'0x{v}', 16)
    h = hex(crc)
    h = h[2:]
    return str(h)


# command_without_crc = '41 0D 0A'
# command_with_crc = LS3command_crc(command_without_crc)
# print(command_without_crc, ' - ', command_with_crc)
def LS3command_crc(command: str):
    """
    Generates the LS3 command with CRC for commands without crc
    Calculate CRC for Linescale3 Commands
    :param command: LS3 command without crc
    :return: LS3 command with crc
    """
    crc = LS3crc(command)
    return f'{command} {crc}'.upper()


def LS3xyget(value):
    """
    Splits a number in 2 pieces
    :param value:
    :return:
    """
    value = f'{value:02d}'
    return split(value)


# LS3ReadLogxy()
def LS3ReadLogxy():
    """
    Creates the LS3 commands for reading the onboard logging Data
    :return: Commands in dict
    """
    for i in range(100):
        x, y = LS3xyget(i)
        command_without_crc = f"52 3{x} 3{y} 0D 0A"
        command_with_crc = LS3command_crc(command_without_crc)
        # print(f"ReadLog{i + 1} = {command_with_crc}")
        PyLS3_Conf['Commands'][f"ReadLog{i + 1}"] = dict()
        PyLS3_Conf['Commands'][f"ReadLog{i + 1}"]['Hex_Code'] = command_with_crc
        PyLS3_Conf['Commands'][f"ReadLog{i + 1}"]['Description'] = f"Read the {i}th log command"
        PyLS3_Conf['Commands'][f"ReadLog{i + 1}"]['SupportedProtocol'] = dict()
        PyLS3_Conf['Commands'][f"ReadLog{i + 1}"]['SupportedProtocol']['Bluetooth'] = False
        PyLS3_Conf['Commands'][f"ReadLog{i + 1}"]['SupportedProtocol']['USB'] = True


async def run_sequence(*functions: Awaitable[Any]) -> None:
    for function in functions:
        await function


async def run_parallel(*functions: Awaitable[Any]) -> None:
    await asyncio.gather(*functions)


class Connection(ABC):
    devices_active = 0
    devices_registered = list()
    device_object_list = list()

    def __init__(self):
        self.device_name = str()
        self.connected = False
        # self.init_defaults()

    def init_defaults(self):
        Connection.device_object_list.append(self)
        # defaults for all Connections (can't use init for serial connection)
        self.rx_data_onboardlogging = False
        self.device_force_close = False

        # RX Buffer
        self.last_packet_time = datetime.now()
        self.rx_data_counter = 0
        self.rx_dataq = bytes()
        self.capture_data = []
        self.capture_activated = False
        self.capture_running = False
        self.capture_stop_trigger = False
        self.capture_save_ongoing = False
        self.capture_starttime = 0
        self.precapture_data = deque([], maxlen=0)
        self.rx_timestamps = []
        self.rx_delays = []

        self.working_mode = str()
        self.measured_value = float()
        self.measure_mode = str()
        self.reference_zero = float()
        self.electric_quantity = int()
        self.unit_value = str()
        self.speed_value = int()
        # self.check_value = str()
        self.working_mode_parsed = str()
        self.measure_mode_parsed = str()
        self.unit_value_parsed = str()
        self.speed_value_parsed = str()

    @abstractmethod
    def connection_lost(self) -> None:
        pass

    @abstractmethod
    async def data_send(self, data) -> None:
        pass

    @abstractmethod
    def data_received(self) -> None:
        pass

    async def cmd_send(self, command: str):
        connectiontype = PyLS3_Conf['UseDevices'][self.device_name]['ConnectionType']
        while True:
            # Wait cmd
            if re.search('Wait([0-9]+)', command):
                wait_time = int(re.search('Wait([0-9]+)', command).group(1))
                logger.info(f"{self.device_name}: Wait {wait_time}s start")
                await asyncio.sleep(wait_time)
                logger.info(f"{self.device_name}: Wait {wait_time} finished")
                break

            # RawCMD
            elif re.search('RawCMD_([^_]+)_([TF])', command):
                match = re.search('RawCMD_([^_]+)_([TF])', command)
                hex_code = match.group(1)
                if match.group(2).upper() == "T":
                    hex_code = LS3command_crc(hex_code)
                bytes_to_send = bytes.fromhex(hex_code)
                logger.info(f"{self.device_name}: Sending command RawCMD '{hex_code}' '{bytes_to_send}'")
                await self.data_send(bytes_to_send)
                break

            try:
                PyLS3_Conf['Commands'][command]
            except KeyError:
                logger.error(f"{self.device_name}: Command '{command}' not defined!")
                break

            if not PyLS3_Conf['Commands'][command]['SupportedProtocol'][connectiontype]:
                logger.warning(f"{self.device_name}: Command '{command}' not Supported via {connectiontype}")
                break

            if command == 'ForceClose':
                await self.cmd_send('StopCaptureNow')
                await self.cmd_send('DeactivateLogging')
                await self.cleanup()
                self.device_force_close = True
                break

            elif command == 'SaveOnboardLogging':
                await self.cmd_send('DeactivateLogging')
                self.rx_data_onboardlogging = True
                await asyncio.sleep(0.5)
                stop_saveonboardlogging = False         # True if OnboardLogging Data has no Data

                # set Version specific values
                ls3os_versionspecific = find_nearest_lowerequal(PyLS3_Conf['LS3OS']['VersionSpecific'], PyLS3_Conf['Device'][self.device_name]['Version'])
                onboardlogging_row_index_list = PyLS3_Conf['LS3OS']['VersionSpecific'][ls3os_versionspecific]['OnboardLogging_row_index_list']
                csv_date_index = onboardlogging_row_index_list.index('Date') + 1
                csv_time_index = onboardlogging_row_index_list.index('Time') + 1
                min_index = max(csv_date_index, csv_time_index) + 1

                for i in range(1, 101):
                    self.rx_dataq = bytes()
                    self.capture_data = []
                    await self.cmd_send(f"ReadLog{i}")

                    while True:
                        rx_data_list = self.rx_dataq.decode("ASCII").split('\r\n')
                        if rx_data_list.__len__() >= 2 and rx_data_list[-2] == 'End':
                            if rx_data_list.__len__() >= min_index:
                                # save csv
                                csv_date = rx_data_list[csv_date_index]
                                try:
                                    csv_date_obj = datetime.strptime(csv_date, PyLS3_Conf['OnboardLogging']['CSVDateFormatFromLS3'])
                                except Exception as e:
                                    logger.error(f"Wrong Date-Format in OnboardLogging Data. Check version settings. Expection: {e} Using 1.1.1970")
                                    logger.debug(f"{self.rx_dataq}")  # Todo to remove
                                    csv_date_obj = datetime.fromtimestamp(0)
                                csv_date_str = csv_date_obj.strftime(PyLS3_Conf['OnboardLogging']['CSVDateFormatSave'])

                                csv_time = rx_data_list[csv_time_index]
                                try:
                                    csv_time_obj = datetime.strptime(csv_time, PyLS3_Conf['OnboardLogging']['CSVTimeFormatFromLS3'])
                                except Exception as e:
                                    logger.error(f"Wrong Time-Format in OnboardLogging Data. Check version settings. Expection: {e}")
                                    logger.debug(f"{self.rx_dataq}")  # Todo to remove
                                    csv_time_obj = datetime.fromtimestamp(i)
                                csv_time_str = csv_time_obj.strftime(PyLS3_Conf['OnboardLogging']['CSVTimeFormatSave'])

                                ls_folder = f"LS{''.join(PyLS3_Conf['Device'][self.device_name]['MAC'].split(':')[3:])}"
                                csv_file = f"{PyLS3_Conf['Path']['OnboardLogging']}/{ls_folder}/{csv_date_str}/{csv_time_str}.CSV"
                                logger.info(f"{self.device_name}: SaveOnboardLogging ReadLog{i} to file {csv_file}")
                                csv_save_file(rx_data_list[1:-2], csv_file, PyLS3_Conf['OnboardLogging']['CSVOverride'])
                                if PyLS3_Conf['OnboardLogging']['AutoGeneratePlot']:
                                    coro = plot_csv(csv_file, csv_type='onboardlogging', show_plot=False, save_image=True, override_image=PyLS3_Conf['OnboardLogging']['CSVOverride'], row_index_list=onboardlogging_row_index_list)
                                    task = asyncio.create_task(coro)
                                    # await task

                            else:
                                logger.info(f"{self.device_name}: SaveOnboardLogging ReadLog{i} is empty. Leaving SaveOnboardLogging")
                                stop_saveonboardlogging = True
                            break
                        await asyncio.sleep(1)
                    if stop_saveonboardlogging:
                        break
                self.rx_dataq = bytes()
                self.capture_data = []
                self.rx_data_onboardlogging = False
                await self.cmd_send('ActivateLogging')
                break

            elif command == 'StartCapture':
                logger.info(f"{self.device_name}: Capture starting (manual)")
                self.capture_activated = True
                self.capture_running = True
                self.capture_starttime = datetime.now()
                # self.capture_stop_trigger = False
                break

            elif command == 'StopCapture':
                logger.info(f"{self.device_name}: Capture stopping (manual)")
                self.capture_stop_trigger = True
                break

            elif command == 'StopCaptureNow':
                logger.info(f"{self.device_name}: Capture stopping (manual)")
                self.capture_stop_trigger = True
                self.capture_running = False
                break

            elif command == 'ActivateCapture':
                logger.info(f"{self.device_name}: Capture activated (manual)")
                self.capture_activated = True
                break

            elif command == 'DeactivateCapture':
                logger.info(f"{self.device_name}: Capture deactivated (manual)")
                self.capture_activated = False
                break

            logger.info(f"{self.device_name}: Sending command '{command}'")
            bytes_to_send = bytes.fromhex(PyLS3_Conf['Commands'][command]['Hex_Code'])
            await self.data_send(bytes_to_send)

            last_rx_data_counter = self.rx_data_counter
            last_measure_mode_parsed = self.measure_mode_parsed
            await asyncio.sleep(2.0)
            if command == 'ActivateLogging':
                if self.rx_data_counter == last_rx_data_counter:
                    logger.info(f"{self.device_name}: Repeat {command}...")
                    continue
            elif command == 'DectivateLogging':
                if self.rx_data_counter > last_rx_data_counter:
                    logger.info(f"{self.device_name}: Repeat {command}...")
                    continue
            elif command == 'UnitSwitchTokN':
                if not self.unit_value_parsed == "kN":
                    logger.info(f"{self.device_name}: Repeat {command}...")
                    continue
            elif command == 'UnitSwitchTokgf':
                if not self.unit_value_parsed == "kgf":
                    logger.info(f"{self.device_name}: Repeat {command}...")
                    continue
            elif command == 'UnitSwitchTolbf':
                if not self.unit_value_parsed == "lbf":
                    logger.info(f"{self.device_name}: Repeat {command}...")
                    continue
            elif command == 'Speed10':
                if not self.speed_value_parsed == "10":
                    logger.info(f"{self.device_name}: Repeat {command}...")
                    continue
            elif command == 'Speed40':
                if not self.speed_value_parsed == "40":
                    logger.info(f"{self.device_name}: Repeat {command}...")
                    continue
            elif command == 'Speed640':
                if not self.speed_value_parsed == "640":
                    logger.info(f"{self.device_name}: Repeat {command}...")
                    continue
            elif command == 'Speed1280':
                if not self.speed_value_parsed == "1280":
                    logger.info(f"{self.device_name}: Repeat {command}...")
                    continue

            elif command == 'ModeABS':
                if not self.measure_mode_parsed == "ABS":
                    logger.info(f"{self.device_name}: Repeat {command}...")
                    continue

            elif command == 'ModeREL':
                if not self.measure_mode_parsed == "REL":
                    logger.info(f"{self.device_name}: Repeat {command}...")
                    continue
            elif command == 'ModeToggleABS_REL':
                if self.measure_mode_parsed == last_measure_mode_parsed:
                    logger.info(f"{self.device_name}: Repeat {command}...")
                    continue
            # The Rest of the commands has not return ('MenuButton', 'ClearPeak', 'ZeroButton', 'ResetABS')
            # Break Loop if everything is ok
            break

    def rx_data_handler(self, data: Any):
        # logger.debug(f"DEBUG> data = {data}")
        if self.rx_data_onboardlogging:
            self.rx_dataq += data
        else:
            # get timestamps
            present_time = datetime.now()
            rx_timestamp = present_time.timestamp()
            rx_delays = (present_time - self.last_packet_time).microseconds
            self.last_packet_time = present_time
            # Decode Data
            self.rx_dataq += data

            # check dataq for corrupt entries
            while True:
                # One Log line has 20 Byte
                if len(self.rx_dataq) >= 20:
                    # control_index must be 18
                    control_index = self.rx_dataq.find(b'\r')
                    if control_index == -1:
                        # corrupt data
                        self.rx_dataq = bytes()
                        break
                    elif control_index < 19:
                        # Correct data
                        self.rx_dataq = self.rx_dataq[control_index + 1:]
                        continue
                    elif control_index > 19:
                        # Correct data
                        self.rx_dataq = self.rx_dataq[control_index - 19:]
                        continue
                    else:
                        # Correct control_index
                        data = self.rx_dataq[0:20]
                        self.rx_dataq = self.rx_dataq[20:]
                        self.rx_data_counter += 1
                        self.working_mode = data.decode("ASCII")[0]
                        self.measured_value = data.decode("ASCII")[1:7]
                        self.measure_mode = data.decode("ASCII")[7]
                        self.reference_zero = data.decode("ASCII")[8:14]
                        self.electric_quantity = (data[14] - 32) * 2
                        self.unit_value = data.decode("ASCII")[15]
                        self.speed_value = data.decode("ASCII")[16]
                        # self.check_value         = data.decode("ASCII")[17:19]
                        try:
                            self.working_mode_parsed = PyLS3_Conf['MessageCode']['WorkingMode'][self.working_mode]
                            self.measure_mode_parsed = PyLS3_Conf['MessageCode']['MeasureMode'][self.measure_mode]
                            self.unit_value_parsed = PyLS3_Conf['MessageCode']['UnitValue'][self.unit_value]
                            self.speed_value_parsed = PyLS3_Conf['MessageCode']['SpeedValue'][self.speed_value]
                        except Exception as e:
                            logger.warning(f"Exception {e}\n Data: {data} \n Dataq:{self.rx_dataq}\n----------------------\n")

                        cvs_line = f"{self.device_name}, {present_time}, {rx_timestamp}, {rx_delays}, {self.measured_value}, {self.unit_value_parsed}, {self.reference_zero}, {self.measure_mode_parsed}, {self.speed_value_parsed}Hz, {self.electric_quantity}, {self.working_mode_parsed}"
                        rx_delays = 0  # in case there are multiple entries in the rx_dataq

                        # Capture?
                        if not self.capture_activated:
                            pass
                        elif not self.capture_running and not self.capture_stop_trigger:
                            # Check StartTrigger
                            if float(self.measured_value) >= float(PyLS3_Conf['Capture']['StartTrigger']):
                                self.capture_running = True
                                logger.info(f"{self.device_name}: Capture starting")
                                self.capture_starttime = datetime.now()
                                self.capture_data.append(cvs_line)  # save to log
                            else:
                                self.precapture_data.append(cvs_line)  # save to precapture
                        elif self.capture_running:
                            self.capture_data.append(cvs_line)  # save to log
                            # Check MaxCaptureTime_s
                            if present_time - self.capture_starttime >= timedelta(seconds=PyLS3_Conf['Capture']['MaxCaptureTime_s']):
                                self.capture_stop_trigger = True
                                self.capture_running = False
                                # print(f"{datetime.now().isoformat()} {self.device_name}: Capture stopping (MaxCaptureTime_s exceeded)")
                                logger.info(f"{self.device_name}: Capture stopping (MaxCaptureTime_s exceeded)")
                            elif self.capture_stop_trigger or float(self.measured_value) <= float(PyLS3_Conf['Capture']['StopTrigger']):
                                if not self.capture_stop_trigger:
                                    logger.info(f"{self.device_name}: Capture Stop Trigger set ")
                                    self.capture_stop_trigger = True
                                if present_time - self.capture_starttime >= timedelta(seconds=PyLS3_Conf['Capture']['MinCaptureTime_s']):
                                    self.capture_running = False
                                    logger.info(f"{self.device_name}: Capture stopping")
                        else:
                            self.capture_save_ongoing = True
                            # write data
                            logger.info(f"{self.device_name}: Capture saving Data")
                            save_data = list(self.precapture_data) + self.capture_data
                            csv_file = csv_save(self.device_name, save_data)
                            if PyLS3_Conf['Capture']['AutoGeneratePlot']:
                                coro = plot_csv(csv_file, csv_type='pyls3', show_plot=False, save_image=True)
                                task = asyncio.create_task(coro)
                                # await task

                            self.capture_data.clear()
                            self.precapture_data.clear()
                            self.capture_save_ongoing = False
                            self.capture_stop_trigger = False
                            logger.info(f"{self.device_name}: Capture Stop Trigger unset")
                            logger.info(f"{self.device_name}: Ready (Capture activated)")

                            if PyLS3_Conf['Capture']['CaptureMode'] == "single":
                                logger.info(f"{self.device_name}: Capture deactivated")
                                self.capture_activated = False
                else:
                    break

            # # check dataq for corrupt entries
            # while True:
            #     if len(self.rx_dataq) >= 20:
            #         # control_index must be 18
            #         control_index = self.rx_dataq.find(b'\r')
            #         if control_index == -1:
            #             # corrupt data
            #             self.rx_dataq = bytes()
            #             break
            #         elif control_index < 19:
            #             self.rx_dataq = self.rx_dataq[control_index + 1:]
            #         elif control_index > 19:
            #             self.rx_dataq = self.rx_dataq[control_index - 19:]
            #         else:
            #             break
            #     else:
            #         break
            #
            # # split data to 20 byte, leave rest in queue
            # full_data_entries = len(self.rx_dataq) // 20 * 20
            #
            # for i in range(0, full_data_entries, 20):
            #     self.rx_data_counter += 1
            #     data = self.rx_dataq[i:i+20]
            #     self.working_mode = data.decode("ASCII")[0]
            #     self.measured_value = data.decode("ASCII")[1:7]
            #     self.measure_mode = data.decode("ASCII")[7]
            #     self.reference_zero = data.decode("ASCII")[8:14]
            #     self.electric_quantity = (data[14] - 32) * 2
            #     self.unit_value = data.decode("ASCII")[15]
            #     self.speed_value = data.decode("ASCII")[16]
            #     # self.check_value         = data.decode("ASCII")[17:19]
            #     try:
            #         self.working_mode_parsed = PyLS3_Conf['MessageCode']['WorkingMode'][self.working_mode]
            #         self.measure_mode_parsed = PyLS3_Conf['MessageCode']['MeasureMode'][self.measure_mode]
            #         self.unit_value_parsed = PyLS3_Conf['MessageCode']['UnitValue'][self.unit_value]
            #         self.speed_value_parsed = PyLS3_Conf['MessageCode']['SpeedValue'][self.speed_value]
            #     except Exception as e:
            #         logger.warning(f"Exception {e}\n Data: {data} \n Dataq:{self.rx_dataq}\n----------------------\n")
            #
            #     cvs_line = f"{self.device_name}, {present_time}, {rx_timestamp}, {rx_delays}, {self.measured_value}, {self.unit_value_parsed}, {self.reference_zero}, {self.measure_mode_parsed}, {self.speed_value_parsed}Hz, {self.electric_quantity}, {self.working_mode_parsed}"
            #     rx_delays = 0       # in case there are multiple in the rx_dataq
            #
            #     # Capture?
            #     if not self.capture_activated:
            #         pass
            #     elif not self.capture_running and not self.capture_stop_trigger:
            #         # Check StartTrigger
            #         if float(self.measured_value) >= float(PyLS3_Conf['Capture']['StartTrigger']):
            #             self.capture_running = True
            #             logger.info(f"{self.device_name}: Capture starting")
            #             self.capture_starttime = datetime.now()
            #             self.capture_data.append(cvs_line)  # save to log
            #         else:
            #             self.precapture_data.append(cvs_line)   # save to precapture
            #     elif self.capture_running:
            #         self.capture_data.append(cvs_line)  # save to log
            #         # Check MaxCaptureTime_s
            #         if present_time - self.capture_starttime >= timedelta(seconds=PyLS3_Conf['Capture']['MaxCaptureTime_s']):
            #             self.capture_stop_trigger = True
            #             self.capture_running = False
            #             # print(f"{datetime.now().isoformat()} {self.device_name}: Capture stopping (MaxCaptureTime_s exceeded)")
            #             logger.info(f"{self.device_name}: Capture stopping (MaxCaptureTime_s exceeded)")
            #         elif self.capture_stop_trigger or float(self.measured_value) <= float(PyLS3_Conf['Capture']['StopTrigger']):
            #             if not self.capture_stop_trigger:
            #                 logger.info(f"{self.device_name}: Capture Stop Trigger set ")
            #                 self.capture_stop_trigger = True
            #             if present_time - self.capture_starttime >= timedelta(seconds=PyLS3_Conf['Capture']['MinCaptureTime_s']):
            #                 self.capture_running = False
            #                 logger.info(f"{self.device_name}: Capture stopping")
            #     else:
            #         self.capture_save_ongoing = True
            #         # write data
            #         logger.info(f"{self.device_name}: Capture saving Data")
            #         save_data = list(self.precapture_data) + self.capture_data
            #         csv_file = csv_save(self.device_name, save_data)
            #         if PyLS3_Conf['Capture']['AutoGeneratePlot']:
            #             coro = plot_csv(csv_file, csv_type='pyls3', show_plot=False, save_image=True)
            #             task = asyncio.create_task(coro)
            #             # await task
            #
            #         self.capture_data.clear()
            #         self.precapture_data.clear()
            #         self.capture_save_ongoing = False
            #         self.capture_stop_trigger = False
            #         logger.info(f"{self.device_name}: Capture Stop Trigger unset")
            #         logger.info(f"{self.device_name}: Ready (Capture activated)")
            #
            #         if PyLS3_Conf['Capture']['CaptureMode'] == "single":
            #             logger.info(f"{self.device_name}: Capture deactivated")
            #             self.capture_activated = False
            #
            # self.rx_dataq = self.rx_dataq[full_data_entries:]           # remove processed data from queue

    def precapture_queue_initilize(self):
        maxlentries = int(self.speed_value_parsed) * PyLS3_Conf['Capture']['PreCaptureTime_s']
        self.precapture_data = deque([], maxlen=maxlentries)

    def precapture_queue_clear(self):
        self.precapture_data.clear()


class SerialConnection(asyncio.Protocol, Connection):
    # def __init__(self):
    #     Connection.__init__()
    #     self.device_name = device_name

    def connection_made(self, transport):
        self.init_defaults()
        self.transport = transport
        self.connected = True
        # logger.info(f"{self.device_name}: connected") # self.device_name is not set at this time
        Connection.devices_active += 1
        # Connection.devices_registered.append(self.device_name)
        logger.debug(f"Serial: Serial port opened {transport}")
        # input_str = '41 0D 0A 58'  # start logging
        input_str = '45 0D 0A 5C'       # stop  logging
        bytes_to_send = bytes.fromhex(input_str)
        transport.serial.rts = False  # You can manipulate Serial object via transport
        transport.write(bytes_to_send)  # Write serial data via transport

    def connection_lost(self, exc):
        logger.warning(f"{self.device_name}: Serial port closed")
        self.connected = False
        Connection.devices_active -= 1
        Connection.devices_registered.remove(self.device_name)
        # self.transport.loop.stop()
        # self.transport.close()

    def data_received(self, data):
        self.rx_data_handler(data)

    async def data_send(self, data: bytes) -> None:
        self.transport.write(data)  # Write serial data via transport

    def pause_writing(self):
        logger.debug('pause writing')
        logger.debug(self.transport.get_write_buffer_size())

    def resume_writing(self):
        logger.debug(self.transport.get_write_buffer_size())
        logger.debug('resume writing')

    async def cleanup(self):
        # await self.cmd_send('DeactivateLogging')
        if self in Connection.device_object_list:
            Connection.device_object_list.remove(self)
        # self.device_configured = False
        # self.connected = False
        # self.client = None


class BluetoothConnection(Connection):
    """
    The BluetoothConnection class has 4 required and 0 optional arguments.

    device_name - The Name of the remote device
    device_address - The Bluetooth address of the remote device
    read_characteristic – the characteristic on the remote device containing data we are interested in.
    write_characteristic – the characteristic on the remote device which we can write data.
    """
    client: BleakClient = None

    def __init__(
            self,
            # loop: asyncio.AbstractEventLoop,
            device_name: str,
            device_address: str,
            read_characteristic: str,
            write_characteristic: str,
    ):
        # self.loop = loop
        self.device_name = device_name
        self.device_address = device_address
        self.read_characteristic = read_characteristic
        self.write_characteristic = write_characteristic

        self.connected = False
        self.device_configured = False
        self.init_defaults()

    async def manager(self):
        logger.info(f"{self.device_name}: Starting connection manager")
        while True:
            if self.device_force_close:
                break
            if self.client:
                await self.connect()
            else:
                await self.device_find()
            await asyncio.sleep(10.0)

    async def device_find(self):
        logger.info(f"{self.device_name}: Searching device {self.device_address}")
        device = await BleakScanner.find_device_by_address(self.device_address, timeout=20.0)
        if not device:
            logger.info(f"{self.device_name}: A device with address {self.device_address} could not be found.")
        else:
            logger.info(f"{self.device_name}: Connecting to device ({self.device_address})")
            self.client = BleakClient(device)

    async def device_configure(self):
        for c in PyLS3_Conf['UseDevices'][self.device_name]['InitialCommands']:
            if not self.device_force_close:
                logger.info(f"{self.device_name}: Configure sending command '{c}'")
                await self.cmd_send(c)

        if not self.device_force_close:
            self.precapture_queue_initilize()
            self.device_configured = True
            self.capture_activated = True
            logger.info(f"{self.device_name}: Ready (Capture activated)")

    async def connect(self):
        if self.connected:
            return
        try:
            await self.client.connect()
            self.connected = self.client.is_connected
            if self.connected:
                logger.info(f"{self.device_name}: Connected to device ({self.device_address})")
                Connection.devices_registered.append(self.device_name)
                Connection.devices_active += 1
                self.client.set_disconnected_callback(self.connection_lost)
                await self.client.start_notify(
                    self.read_characteristic, self.data_received,
                )
                await self.cmd_send('ActivateLogging')
                await self.device_configure()
                while True:
                    if not self.connected:
                        break
                    await asyncio.sleep(5.0)
            else:
                logger.warning(f"Failed to connect to {self.device_name} ({self.device_address})")
        except Exception as e:
            logger.error(f"Exception: {self.device_name} Bl connect: {e}")

    def connection_lost(self, client: BleakClient):
        logger.warning(f"Disconnected from {self.device_name}!")
        self.device_configured = False
        self.connected = False
        self.client = None
        Connection.devices_active -= 1
        if self.device_name in Connection.devices_registered:
            Connection.devices_registered.remove(self.device_name)

    def data_received(self, sender: str, data: Any):
        self.rx_data_handler(data)

    async def data_send(self, data: bytes) -> None:
        await self.client.write_gatt_char(self.write_characteristic, data)

    async def cleanup(self):
        if self.client:
            await self.client.stop_notify(self.read_characteristic)
            await self.client.disconnect()
            self.device_configured = False
            self.connected = False
            if self in Connection.device_object_list:
                Connection.device_object_list.remove(self)
            # self.client = None

    '''
    async def select_device(self):
        logger.info("Bluetooth LE hardware warming up...")
        await asyncio.sleep(2.0)  # Wait for BLE to initialize.
        devices = await discover()

        print("Please select device: ")
        for i, device in enumerate(devices):
            print(f"{i}: {device.name}")

        response = -1
        while True:
            response = await ainput("Select device: ")
            try:
                response = int(response.strip())
            except:
                print("Please make valid selection.")

            if response > -1 and response < len(devices):
                break
            else:
                print("Please make valid selection.")

        logger.info(f"Connecting to {devices[response].name}")
        self.connected_device = devices[response]
        self.client = BleakClient(devices[response].address, loop=self.loop)
    '''


class SerialConnectionManager:
    def __init__(
            self,
            loop,
            device_name: str,
    ):
        self.loop = loop
        self.device_name = device_name

        self.device_found = False
        self.device_client = None
        self.device_object = None
        self.device_connected = False
        self.device_configured = False
        self.device_reading_active = False

    async def manager(self):
        logger.info(f"{self.device_name}: Starting ConnectionManager.")
        while True:
            try:
                if self.device_object.device_force_close:
                    break
            except AttributeError:
                pass

            if not self.device_found:
                logger.info(f"{self.device_name}: Searching device")
                await self.device_find()
            elif not self.device_client:
                logger.info(f"{self.device_name}: Create Client for device")
                await self.device_create_client()
            elif not self.device_connected:
                logger.info(f"{self.device_name}: Connect to device")
                await self.device_connect()
            elif not self.device_reading_active:
                logger.info(f"{self.device_name}: Activate Reading")
                await self.device_activate_reading()
            elif not self.device_configured:
                logger.info(f"{self.device_name}: Configure device")
                await self.device_configure()
            else:
                pass
            if self.device_connected:
                await self.device_check_connected()
            await asyncio.sleep(5)

    async def device_find(self):
        if PyLS3_Conf['UseDevices'][self.device_name]['ConnectionType'] == 'Bluetooth':
            pass
        elif PyLS3_Conf['UseDevices'][self.device_name]['ConnectionType'] == 'USB':
            com_ports = list(comport.device for comport in serial.tools.list_ports.comports())
            if PyLS3_Conf['Device'][self.device_name]['USB'] in com_ports:
                self.device_found = True
                logger.debug(f"{self.device_name}: Serial Port '{PyLS3_Conf['Device'][self.device_name]['USB']}' found in Serial-Port List '{com_ports}'")
            else:
                self.device_found = False
                logger.info(f"{self.device_name}: Serial Port '{PyLS3_Conf['Device'][self.device_name]['USB']}' not found in Serial-Port List '{com_ports}'")

    async def device_create_client(self):
        if self.device_name in Connection.devices_registered:
            Connection.devices_registered.remove(self.device_name)
        try:
            usb_speed = PyLS3_Conf['Device'][self.device_name]['USB_Speed']
        except KeyError:
            usb_speed = 230400

        try:
            coro = serial_asyncio.create_serial_connection(self.loop, SerialConnection, PyLS3_Conf['Device'][self.device_name]['USB'], usb_speed, bytesize=8, parity='N', stopbits=1, timeout=None, xonxoff=0, rtscts=0)
            task = asyncio.create_task(coro)
            transport, protocol = await task
            self.device_object = protocol
            self.device_client = 'DummySerial'
            self.device_object.device_name = self.device_name
            Connection.devices_registered.append(self.device_name)
        except Exception as e:
            logger.error(f"Exception {e}")
            self.device_client = None
            self.device_object = None
        # Try to set buffer, OS and driver dependent
        try:
            # if platform.system() == 'Windows':
            # max 2^31-1 = 2147483647
            transport.serial.set_buffer_size(rx_size=256000, tx_size=256000)
        except Exception:
            pass

    async def device_connect(self):
        self.device_connected = True
        pass

    async def device_activate_reading(self):
        await self.device_object.cmd_send('ActivateLogging')
        self.device_reading_active = True

    async def device_configure(self):
        for c in PyLS3_Conf['UseDevices'][self.device_name]['InitialCommands']:
            if not self.device_object.device_force_close:
                logger.info(f"{self.device_name}: Configure sending command '{c}'")
                await self.device_object.cmd_send(c)

        self.device_object.precapture_queue_initilize()
        self.device_configured = True
        self.device_object.capture_activated = True
        logger.info(f"{self.device_name}: Ready (Capture activated)")
        pass

    async def device_check_connected(self):
        if self.device_object.connected:
            self.device_connected = True
        else:
            self.device_found = False
            self.device_client = None
            self.device_object = None
            self.device_connected = False
            self.device_configured = False
            self.device_reading_active = False


async def user_console():
    logger.info(f"User-Console: started")
    logger.info(f"User-Console: the console is only displayed again after enter has been pressed (this may take a few seconds)!")
    run_user_console = True
    while run_user_console:
        await aprint(f"User-Console: Currently registered devices: {Connection.devices_registered}")
        await aprint("User-Console: Please enter: 'q | quit' 'l | list_cmd' \"send <command> [<device>]\" ")
        input_str = await ainput("Please enter value: ")

        if input_str in ('quit', 'q',):
            device_object_list = Connection.device_object_list.copy()
            for c in device_object_list:
                await c.cmd_send('ForceClose')
                # await asyncio.wait_for(c.cmd_send('ForceClose'), timeout=1.0)
                run_user_console = False
        elif input_str in ('l', 'list_cmd'):
            for c in PyLS3_Conf['Commands']:
                print(f"{c}: {PyLS3_Conf['Commands'][c]}")
        elif (input_str.split().__len__() == 2 or input_str.split().__len__() == 3) and input_str.split()[0] == 'send':
            cmd = input_str.split()[1]
            for c in Connection.device_object_list:
                if input_str.split().__len__() == 3:
                    if c.device_name == input_str.split()[2]:
                        await c.cmd_send(cmd)
                        break
                else:
                    await c.cmd_send(cmd)
        await asyncio.sleep(1.0)


async def main():
    loop = asyncio.get_event_loop()

    # Dict for all tasks
    task = dict()

    # start user_console
    if not args.no_user_console:
        task['con'] = asyncio.create_task(user_console())

    # Start connection to all Devices
    manager = dict()
    # for num, d in enumerate(PyLS3_Conf['UseDevices']):
    for d in PyLS3_Conf['UseDevices']:
        if PyLS3_Conf['UseDevices'][d]['ConnectionType'] == 'Bluetooth':
            manager[d] = BluetoothConnection(d, PyLS3_Conf['Device'][d]['MAC'], PyLS3_Conf['Bluetooth']['UART_TX_CHAR_UUID'], PyLS3_Conf['Bluetooth']['UART_RX_CHAR_UUID'])
        elif PyLS3_Conf['UseDevices'][d]['ConnectionType'] == 'USB':
            manager[d] = SerialConnectionManager(loop=loop, device_name=d)
        else:
            continue
        task[d] = asyncio.create_task(manager[d].manager())
    for d in task:
        await task[d]
    logger.info("PyLS3 is closing. Good bye!!!")


if __name__ == "__main__":
    # Parse CLI args
    parser = argparse.ArgumentParser(
        description='PyLS3 - This Python script connects to Linescale3 via Bluetooth or Serial (USB UART).',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        epilog="Have fun ;)")
    #    exit_on_error=False)
    parser.add_argument('-ca', '--appcfg', default='PyLS3_AppCfg.yml', help='PyLS3 App configuration File')
    parser.add_argument('-cu', '--usercfg', default='PyLS3_UserCfg.yml', help='PyLS3 User configuration File (overrides PyLS3 App configurations and args override both)')
    parser.add_argument('-nsc', '--not_save_cfg', default=False, action="store_true", help='Do not save a Backup of PyLS3_AppCfg and PyLS3_UserCfg.yml at startup')
    parser.add_argument("-c", '--conf', default=None,
                        # type=lambda kv: kv.split(","),
                        action='append',
                        help='''could be applied multiple times: 
                             e.g. -c AppSettings: UseDevices:LS3_1:InitialCommands:["\'Speed40\', \'ModeREL\'"]\
                                  -c AppSettings: UseDevices:LS3_1:ConnectionType:Bluetooth
                             '''
                        )
    parser.add_argument('-nuc', '--no_user_console', default=False, action="store_true", help='Do not start user-console')
    parser.add_argument('-nc', '--no_color', default=False, action="store_true", help='Logging without color (e.g. for windows cmd)')
    args = parser.parse_args()

    # Supress warnings
    warnings.filterwarnings("ignore", 'This pattern has match groups')

    # Clear screen on Windows (workaround, so colors are working in cmd)
    if platform.system() == 'Windows':
        os.system('cls')

    # create logger with 'spam_application'
    logger = logging.getLogger("PyLS3")
    logger.setLevel(logging.DEBUG)
    # create console handler with a higher log level
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    if args.no_color:
        ch.setFormatter(CustomFormatterNoColor())
    else:
        ch.setFormatter(CustomFormatter())
    logger.addHandler(ch)
    # logging.basicConfig(format='%(levelname)s: %(message)s', level=logging.INFO)  # DEBUG INFO WARNING ERROR CRITICAL (WARNING is default)
    # logger.debug('TEST')
    # logger.info('TEST')
    # logger.warning('TEST')
    # logger.error('TEST')
    # logger.critical('TEST')
    # logger.critical('TEST')
    # exit()

    # Load configuration files, maybe move somewhere else
    PyLS3_AppCfg = yaml_load(args.appcfg)
    PyLS3_UserCfg = yaml_load(args.usercfg)
    # PyLS3_Conf = {**PyLS3_AppCfg, **PyLS3_UserCfg}   # UserCfg overrides AppCfg
    PyLS3_Conf = deep_merge(PyLS3_AppCfg, PyLS3_UserCfg)
    if args.conf:
        args_dict = gen_args_dict(args.conf)
        PyLS3_Conf = deep_merge(PyLS3_Conf, args_dict)
        del args_dict
    # LS3ReadLogxy()  # Generate the log-read commands are included in AppCfg
    if not args.not_save_cfg:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        yaml_save(PyLS3_AppCfg, f"{PyLS3_Conf['Path']['Backup']}/{timestamp}_{args.appcfg}")
        yaml_save(PyLS3_UserCfg, f"{PyLS3_Conf['Path']['Backup']}/{timestamp}_{args.usercfg}")
        yaml_save(PyLS3_Conf, f"{PyLS3_Conf['Path']['Backup']}/{timestamp}_PyLS3_Conf.yml")
    del PyLS3_AppCfg
    del PyLS3_UserCfg
    # run main
    asyncio.run(main())
