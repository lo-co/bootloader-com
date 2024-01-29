import RPi.GPIO as gpio
from time import sleep

import os

from spsdk.mboot.interfaces.uart import MbootUARTInterface
from spsdk.mboot.mcuboot import McuBoot, McuBootCommandError, StatusCode

from enum import Enum

import argparse


class Reset(Enum):
    """
    Values to toggle the reset line.

    Attributes:
        ENABLED (int): Reset is asserted
        DISABLED (int): Reset is not active
    """

    ENABLED = 0
    DISABLED = 1


class Isp_State(Enum):
    LOW = 0
    HIGH = 1


class OutputPins(Enum):
    """
    BCM numbered lines.

    Attributes:
        ISP2 (int): port number for toggling the ISP2 line
        RESET (int): port number for toggling the Reset line
    """

    ISP2 = 2
    RESET = 3


def configure_gpio() -> None:
    """
    Configure the Raspberry Pi GPIO.  This uses two pins - one for reset
    and one for ISP2 functionality on the RT685 EVK.  Both of these should
    be configured as output.
    """
    gpio.setmode(gpio.BCM)
    gpio.setwarnings(True)
    gpio.setup(OutputPins.ISP2.value, gpio.OUT)
    gpio.setup(OutputPins.RESET.value, gpio.OUT)


def set_isp(isp_state: Isp_State = Isp_State.LOW) -> None:
    """
    Set the ISP2 line based on the input `isp_state`. This function will
    first put the board in reset, then set the ISP2 value, and finally pull
    the EVK out of reset after 500 ms. The default setting for the ISP pins
    is LOW HIGH LOW.  When we want to communicate with the ROM bootloader
    via UART, we will set the values to LOW HIGH HIGH by pulling the ISP2
    line HIGH.

    Args:
        isp_state (Isp_State): Set the pin state appropriately.  The default is
        low.
    """
    gpio.output(OutputPins.RESET.value, Reset.ENABLED.value)
    gpio.output(OutputPins.ISP2.value, isp_state.value)
    sleep(0.5)
    gpio.output(OutputPins.RESET.value, Reset.DISABLED.value)


def main(comm_port: str, baud_rate: int) -> None:

    memoryID = 9
    configure_gpio()

    # Make sure this line is set to high for programming
    set_isp(Isp_State.HIGH)

    # Bootloader ROM uses FC0 pins 0_1 (Tx) and 0_2 (Rx) for UART
    interfaces = MbootUARTInterface.scan(port=comm_port, baudrate=baud_rate)

    if len(interfaces) > 0:
        print(f"%d interfaces found on /dev/ttyACM0", len(interfaces))
    else:
        print("No interfaces found.  Exiting now.")
        set_isp()
        return

    # Assumes only one interface really...
    for interface in interfaces:
        # Raise an exception when there is an McuBootCommandError
        with McuBoot(interface, True) as mb:

            try:
                # If memory is unconfigured, we will not be able to be erase and
                # an exceptionwill be thrown
                mb.flash_erase_region(0x08000000, 32000, memoryID)
            except McuBootCommandError as e:
                mb.fill_memory(0x0010C000, 4, 0xC1503057)
                mb.fill_memory(0x0010C004, 4, 0x20000000)
                mb.configure_memory(0x10C000, memoryID)

                # Only clear out 32 kb for this.  We can run flash_erase_all
                # on this but that is going to take  a long time
                mb.flash_erase_region(0x08000000, 32000, memoryID)

            # We just erased a significant portion of flash - generate the FCB
            # once flash configured. This will fill out the FCB starting at
            # an offset of 0x400
            mb.fill_memory(0x0010C000, 4, 0xF000000F)

            mb.configure_memory(0x10C000, memoryID)

            # For verification, make sure that the FCB is not a mess
            print(f"FCB\n==============================")
            fcb = mb.read_memory(
                0x08000400,
                0x200,
            )

            # Print the FCB...
            for i in range(0, len(fcb), 16):
                line = fcb[i : i + 16]
                hex_line = " ".join(f"{byte:02X}" for byte in line)
                print(hex_line)

            try:
                current_path = os.path.abspath(__file__)
                parent_dir = os.path.dirname(os.path.dirname(current_path))
                img = os.path.join(parent_dir, "bin", "test_gpio_led_output.bin")
                print(f"Current Path:", img)
                with open(img, "rb") as f:
                    img = f.read()
                    mb.write_memory(0x08001000, img, 0)
                    print("Flash successfully written to...")

                # Reset MCU
            #  mb.reset(reopen=False)
            except McuBootCommandError as e:
                print(e)

    # Set line to default position to boot properly
    set_isp()


if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description="Host for communicating with the NXP bootloader"
    )

    parser.add_argument(
        "--comm_port",
        type=str,
        default="/dev/ttyACM0",
        help="UART port for Raspberry Pi to communicate on",
    )
    parser.add_argument("--baud", type=int, default=921600, help="Baud rate in bps.")

    args = parser.parse_args()

    main(args.comm_port, args.baud)
