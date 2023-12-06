import os
import subprocess

def find_usb_port(device_path):
    try:
        result = subprocess.run(['udevadm', 'info', '--query=property', '--name=' + device_path], capture_output=True, text=True)
        
        for line in result.stdout.split('\n'):
            if 'ID_PATH=' in line:
                # Extract the USB port number
                usb_port_info = line.split('=')[1]
                return int(usb_port_info.split('.')[-1])

    except FileNotFoundError:
        print("udevadm command not found. Make sure udev is installed on your system.")
    except Exception as e:
        print(f"An error occurred: {str(e)}")

    return None

def find_ttyUSB0(max_ports=10):
    for i in range(max_ports):
        device_path = f'/dev/ttyUSB{i}'
        if os.path.exists(device_path):
            usb_port_index = find_usb_port(device_path)
            if usb_port_index is not None:
                print(f"/dev/ttyUSB0 is connected to USB port: {usb_port_index}")
                return usb_port_index

    print("/dev/ttyUSB0 not found on any USB port.")
    return None

if __name__ == "__main__":
    usb_port_index = find_ttyUSB0()
    if usb_port_index is not None:
        print(f"The device is connected to USB port index: {usb_port_index}")
