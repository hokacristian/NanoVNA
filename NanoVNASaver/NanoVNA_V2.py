#  NanoVNASaver
#
#  A python program to view and export Touchstone data from a NanoVNA
#  Copyright (C) 2019, 2020  Rune B. Broberg
#  Copyright (C) 2020,2021 NanoVNA-Saver Authors
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <https://www.gnu.org/licenses/>.
import logging
import platform
from struct import pack, unpack_from
from time import sleep
from typing import List

from NanoVNASaver.Serial import Interface
from NanoVNASaver.VNA import VNA
from NanoVNASaver.Version import Version

if platform.system() != 'Windows':
    import tty

logger = logging.getLogger(__name__)

_CMD_NOP = 0x00
_CMD_INDICATE = 0x0d
_CMD_READ = 0x10
_CMD_READ2 = 0x11
_CMD_READ4 = 0x12
_CMD_READFIFO = 0x18
_CMD_WRITE = 0x20
_CMD_WRITE2 = 0x21
_CMD_WRITE4 = 0x22
_CMD_WRITE8 = 0x23
_CMD_WRITEFIFO = 0x28

_ADDR_SWEEP_START = 0x00
_ADDR_SWEEP_STEP = 0x10
_ADDR_SWEEP_POINTS = 0x20
_ADDR_SWEEP_VALS_PER_FREQ = 0x22
_ADDR_RAW_SAMPLES_MODE = 0x26
_ADDR_VALUES_FIFO = 0x30
_ADDR_DEVICE_VARIANT = 0xf0
_ADDR_PROTOCOL_VERSION = 0xf1
_ADDR_HARDWARE_REVISION = 0xf2
_ADDR_FW_MAJOR = 0xf3
_ADDR_FW_MINOR = 0xf4

WRITE_SLEEP = 0.05

_ADF4350_TXPOWER_DESC_MAP = {
    0: '9dB attenuation',
    1: '6dB attenuation',
    2: '3dB attenuation',
    3: 'Maximum',
}
_ADF4350_TXPOWER_DESC_REV_MAP = {
    value: key for key, value in _ADF4350_TXPOWER_DESC_MAP.items()}

class NanoVNA_V2(VNA):
    name = "NanoVNA-V2"
    valid_datapoints = (101, 11, 51, 401, 301, 501, 1023)
    screenwidth = 320
    screenheight = 240

    def __init__(self, iface: Interface):
        super().__init__(iface)

        if platform.system() != 'Windows':
            tty.setraw(self.serial.fd)

        # reset protocol to known state
        with self.serial.lock:
            self.serial.write(pack("<Q", 0))
            sleep(WRITE_SLEEP)

        # firmware major version of 0xff indicates dfu mode
        if self.version.data["major"] == 0xff:
            raise IOError('Device is in DFU mode')

        if "S21 hack" in self.features:
            self.valid_datapoints = (101, 11, 51, 301, 301, 501, 1021)

        # self.sweepStartHz = 200e6
        # self.sweepStepHz = 1e6
        self.sweepStartHz = 1e5
        self.sweepStepHz = 19933222.59136213 #401 data point
        # self.sweepStepHz = 11976027.944111776 #501 data point

        self._sweepdata = []
        self._updateSweep()

    def getCalibration(self) -> str:
        return "Unknown"

    def read_features(self):
        self.features.add("Customizable data points")
        # TODO: more than one dp per freq
        self.features.add("Multi data points")
        self.board_revision = self.read_board_revision()
        if self.board_revision >= Version("2.0.4"):
            self.sweep_max_freq_Hz = 4400e6
        else:
            self.sweep_max_freq_Hz = 3000e6
        if self.version <= Version("1.0.1"):
            logger.debug("Hack for s21 oddity in first sweeppoint")
            self.features.add("S21 hack")
        if self.version >= Version("1.0.2"):
            self.features.update({"Set TX power partial", "Set Average"})
            # Can only set ADF4350 power, i.e. for >= 140MHz
            self.txPowerRanges = [
                ((140e6, self.sweep_max_freq_Hz),
                 [_ADF4350_TXPOWER_DESC_MAP[value] for value in (3, 2, 1, 0)]),
            ]

    def readFirmware(self) -> str:
        result = f"HW: {self.read_board_revision()}\nFW: {self.version}"
        logger.debug("readFirmware: %s", result)
        return result

    def readFrequencies(self) -> List[int]:
        return [
            int(self.sweepStartHz + i * self.sweepStepHz)
            for i in range(self.datapoints)]

    def readValues(self, value) -> List[str]:
        # Actually grab the data only when requesting channel 0.
        # The hardware will return all channels which we will store.
        if value == "data 0":
            s21hack = "S21 hack" in self.features
            # reset protocol to known state
            timeout = self.serial.timeout
            with self.serial.lock:
                self.serial.write(pack("<Q", 0))
                sleep(WRITE_SLEEP)
                # cmd: write register 0x30 to clear FIFO
                self.serial.write(pack("<BBB",
                                       _CMD_WRITE, _ADDR_VALUES_FIFO, 0))
                sleep(WRITE_SLEEP)
                # clear sweepdata
                self._sweepdata = [(complex(), complex())] * (
                    self.datapoints + s21hack)
                pointstodo = self.datapoints + s21hack
                # we read at most 255 values at a time and the time required empirically is
                # just over 3 seconds for 101 points or 7 seconds for 255 points
                self.serial.timeout = min(pointstodo, 255) * 0.035 + 0.1
                while pointstodo > 0:
                    logger.info("reading values")
                    pointstoread = min(255, pointstodo)
                    # cmd: read FIFO, addr 0x30
                    self.serial.write(
                        pack("<BBB",
                             _CMD_READFIFO, _ADDR_VALUES_FIFO,
                             pointstoread))
                    sleep(WRITE_SLEEP)
                    # each value is 32 bytes
                    nBytes = pointstoread * 32

                    # serial .read() will try to read nBytes bytes in timeout secs
                    arr = self.serial.read(nBytes)
                    if nBytes != len(arr):
                        logger.warning("expected %d bytes, got %d",
                                       nBytes, len(arr))
                        # the way to retry on timeout is keep the data already read
                        # then try to read the rest of the data into the array
                        if nBytes > len(arr):
                            arr = arr + self.serial.read(nBytes - len(arr))
                    if nBytes != len(arr):
                        return []

                    freq_index = -1
                    for i in range(pointstoread):
                        (fwd_real, fwd_imag, rev0_real, rev0_imag, rev1_real,
                         rev1_imag, freq_index) = unpack_from(
                             "<iiiiiihxxxxxx", arr, i * 32)
                        fwd = complex(fwd_real, fwd_imag)
                        refl = complex(rev0_real, rev0_imag)
                        thru = complex(rev1_real, rev1_imag)
                        if i == 0:
                            logger.debug("Freq index from: %i", freq_index)
                        self._sweepdata[freq_index] = (refl / fwd, thru / fwd)
                    logger.debug("Freq index to: %i", freq_index)

                    pointstodo = pointstodo - pointstoread
            self.serial.timeout = timeout

            if s21hack:
                self._sweepdata = self._sweepdata[1:]

            ret = [x[0] for x in self._sweepdata]
            ret = [str(x.real) + ' ' + str(x.imag) for x in ret]
            return ret

        if value == "data 1":
            ret = [x[1] for x in self._sweepdata]
            ret = [str(x.real) + ' ' + str(x.imag) for x in ret]
            return ret

        return []

    def resetSweep(self, start: int, stop: int):
        self.setSweep(start, stop)

    def readVersion(self) -> 'Version':
        cmd = pack("<BBBB",
                   _CMD_READ, _ADDR_FW_MAJOR,
                   _CMD_READ, _ADDR_FW_MINOR)
        with self.serial.lock:
            self.serial.write(cmd)
            sleep(WRITE_SLEEP)
            resp = self.serial.read(2)
        if len(resp) != 2:
            logger.error("Timeout reading version registers. Got: %s", resp)
            raise IOError("Timeout reading version registers")
        result = Version(f"{resp[0]}.0.{resp[1]}")
        logger.debug("readVersion: %s", result)
        return result

    def read_board_revision(self) -> 'Version':
        cmd = pack("<BBBB",
                   _CMD_READ, _ADDR_DEVICE_VARIANT,
                   _CMD_READ, _ADDR_HARDWARE_REVISION)
        with self.serial.lock:
            self.serial.write(cmd)
            sleep(WRITE_SLEEP)
            resp = self.serial.read(2)
        if len(resp) != 2:
            logger.error("Timeout reading version registers")
            return None
        result = Version(f"{resp[0]}.0.{resp[1]}")
        logger.debug("read_board_revision: %s", result)
        return result


    def setSweep(self, start, stop):
        step = (stop - start) / (self.datapoints - 1)
        if start == self.sweepStartHz and step == self.sweepStepHz:
            return
        self.sweepStartHz = start
        self.sweepStepHz = step
        logger.info('NanoVNAV2: set sweep start %d step %d',
                    self.sweepStartHz, self.sweepStepHz)
        self._updateSweep()
        return

    def _updateSweep(self):
        s21hack = "S21 hack" in self.features
        cmd = pack("<BBQ", _CMD_WRITE8, _ADDR_SWEEP_START,
                   max(50000,
                       int(self.sweepStartHz - (self.sweepStepHz * s21hack))))
        cmd += pack("<BBQ", _CMD_WRITE8,
                    _ADDR_SWEEP_STEP, int(self.sweepStepHz))
        cmd += pack("<BBH", _CMD_WRITE2,
                    _ADDR_SWEEP_POINTS, self.datapoints + s21hack)
        cmd += pack("<BBH", _CMD_WRITE2,
                    _ADDR_SWEEP_VALS_PER_FREQ, 1)
        with self.serial.lock:
            self.serial.write(cmd)
            sleep(WRITE_SLEEP)

    def setTXPower(self, freq_range, power_desc):
        if freq_range[0] != 140e6:
            raise ValueError('Invalid TX power frequency range')
        # 140MHz..max => ADF4350
        self._set_register(0x42, _ADF4350_TXPOWER_DESC_REV_MAP[power_desc], 1)

    def _set_register(self, addr, value, size):
        if size == 1:
            packet = pack("<BBB", _CMD_WRITE, addr, value)
        elif size == 2:
            packet = pack("<BBH", _CMD_WRITE2, addr, value)
        elif size == 4:
            packet = pack("<BBI", _CMD_WRITE4, addr, value)
        elif size == 8:
            packet = pack("<BBQ", _CMD_WRITE8, addr, value)
        self.serial.write(packet)
        logger.debug("set register %02x (size %d) to %x", addr, size, value)
