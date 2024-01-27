import RPi.GPIO as gpio
from time import sleep

import os

from spsdk.mboot.interfaces.uart import MbootUARTInterface
from spsdk.mboot.mcuboot import McuBoot, McuBootCommandError, StatusCode


def configure_gpio(pins: list):
    gpio.setmode(gpio.BCM)
    gpio.setwarnings(False)
    for pin in pins:
        gpio.setup(pin, gpio.OUT)
        gpio.setup(pin, gpio.OUT)

def set_isp(reset: int, isp: int, pin_position: int):
    gpio.output(reset, 0)
    gpio.output(isp, pin_position)
    sleep (0.5)
    gpio.output(reset, 1)

def main() -> None:

    # BCM 2 - this is pin 3 on the RPi
    isp_line = 2
    reset_pin = 3
    memoryID = 9
    configure_gpio([reset_pin, isp_line])

    # Make sure this line is set to high for programming
    set_isp(reset_pin, isp_line, 1)

    # Bootloader ROM uses FC0 pins 0_1 (Tx) and 0_2 (Rx) for UART
    interfaces = MbootUARTInterface.scan(port="/dev/ttyACM0", baudrate=921600)

    if len(interfaces) > 0:
        print(f"%d interfaces found on /dev/ttyACM0", len(interfaces))
    else:
        print("No interfaces found.  Exiting now.")
        set_isp(reset_pin, isp_line, 0)
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
                mb.configure_memory(0x10c000, memoryID)

                # Only clear out 32 kb for this.  We can run flash_erase_all
                # on this but that is going to take  a long time
                mb.flash_erase_region(0x08000000, 32000, memoryID)

            # We just erased a significant portion of flash - generate the FCB
            # once flash configured. This will fill out the FCB starting at
            # an offset of 0x400
            mb.fill_memory(0x0010C000, 4, 0xF000000F)

            mb.configure_memory(0x10c000, memoryID)

            # For verification, make sure that the FCB is not a mess
            print(f"FCB\n==============================")
            fcb = mb.read_memory(0x08000400, 0x200, )

            # Print the FCB...
            for i in range(0, len(fcb), 16):
                line = fcb[i:i+16]
                hex_line = ' '.join(f'{byte:02X}' for byte in line)
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

                # Set line to default position to boot properly
                gpio.output(isp_line, 0)
                gpio.output(reset_pin, 1)
                sleep(0.5)
                gpio.output(reset_pin, 0)

                # Reset MCU
              #  mb.reset(reopen=False)
            except McuBootCommandError as e:
                print(e)

if __name__ == "__main__":
    main()
