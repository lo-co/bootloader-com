from spsdk.mboot.interfaces.uart import MbootUARTInterface
from spsdk.mboot.mcuboot import McuBoot, McuBootCommandError, StatusCode

def main() -> None:
    # Bootloader ROM uses FC0 pins 0_1 (Tx) and 0_2 (Rx) for UART
    interfaces = MbootUARTInterface.scan(port="/dev/ttyACM0", baudrate=921600)

    # Assumes only one interface really...
    for interface in interfaces:
        # Raise an exception when there is an McuBootCommandError
        with McuBoot(interface, True) as mb:

            try:
                # If memory is unconfigured, we will not be able to be erase and
                # an exceptionwill be thrown
                mb.flash_erase_region(0x08000000, 32000, 9)
            except McuBootCommandError as e:
                mb.fill_memory(0x0010C000, 4, 0xC1503057)
                mb.fill_memory(0x0010C004, 4, 0x20000000)
                mb.configure_memory(0x10c000, 9)
                mb.flash_erase_region(0x08000000, 32000, 9)

                mb.fill_memory(0x0010C000, 4, 0xF000000F)
                mb.configure_memory(0x10c000, 9)

                fcb = mb.read_memory(0x08000400, 0x200, )

            # Print the FCB...
            for i in range(0, len(fcb), 16):
                line = fcb[i:i+16]
                hex_line = ' '.join(f'{byte:02X}' for byte in line)
                print(hex_line)

            try:
                with open(f"../bin/test_gpio_led_output.bin", "rb") as f:
                    img = f.read()
                    mb.write_memory(0x08001000, img, 0)
                    print("Flash successfully written to...")

                # Reset MCU
                mb.reset(reopen=False)
            except McuBootCommandError as e:
                print(e)

if __name__ == "__main__":
    main()
