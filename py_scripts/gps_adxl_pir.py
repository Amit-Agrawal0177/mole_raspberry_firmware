import os
import json
import subprocess
import time
from datetime import datetime, timedelta
#import paho.mqtt.client as mqtt
import serial

import RPi.GPIO as GPIO
import busio
import adafruit_adxl34x

scl_pin = 3
sda_pin = 2

i2c = busio.I2C(scl=scl_pin, sda=sda_pin)
accelerometer = adafruit_adxl34x.ADXL345(i2c)

x1 = 0
y1 = 0
z1 = 0
accel_flag = 0
accel_count = 0

config_file_path = 'config.json'
with open(config_file_path, 'r') as file:
    config_data = json.load(file)

thr = config_data['accel_thr']
location_publish_interval = config_data['location_publish_interval']
restart_var = 0

def on_publish_location():
    #print("on_publish_location", flush=True)
    global restart_var
    
    command = "AT+CSQ"
    ser.write((command + "\r\n").encode())
    response = ser.read_until(b'OK\r\n').decode(errors='ignore')
    nw = response.split(':')[1].split(',')[0].strip()
    #print(f"response {nw} {response}", flush=True)
    
    command = "AT+CGPSINFO"
    ser.write((command + "\r\n").encode())
    response = ser.read_until(b'OK\r\n').decode(errors='ignore')
    
    latitude = ""
    longitude = ""
    
    values = response.strip().split(',')
    if len(response) > 15:
        latitude = values[0]
        longitude = values[2]
        latitude = latitude.replace("+CGPSINFO: ", "")
        restart_var = 0
        
    if len(longitude) == 0:
        restart_var = restart_var + 1
        if restart_var > 5:
            ser.write("AT+CGPS=0\r\n".encode())
            x = ser.read_until(b'OK\r\n').decode(errors='ignore')
            print(f"r {x}", flush=True)
            
            
            ser.write("AT+CGPS=1\r\n".encode())
            x = ser.read_until(b'OK\r\n').decode(errors='ignore')
            print(f"r {x}", flush=True)
            restart_var = 0
    
    json_file_path = 'stat.json'
    with open(json_file_path, 'r') as file:
        stats = json.load(file)
        
    stats['lat'] = latitude
    stats['long'] = longitude
    cTime = datetime.now()
    stats['timestamp'] = cTime.strftime('%Y:%m:%d %H:%M:%S')
    stats['nw_strength'] = nw
    
    with open(json_file_path, 'w') as file:
        json.dump(stats, file)
    
    location_message = {"lat": latitude, "long": longitude}
    #print(f"gps {location_message}", flush=True)
    #publish_mqtt(f'R/{topic}', json.dumps(location_message))

def find_usb_port(device_path):
    try:
        result = subprocess.run(['udevadm', 'info', '--query=property', '--name=' + device_path], capture_output=True, text=True)
        
        for line in result.stdout.split('\n'):
            if 'ID_PATH=' in line:
                # Extract the USB port number
                usb_port_info = line.split('=')[1]
                return int(usb_port_info.split('.')[-1])

    except FileNotFoundError:
        print("udevadm command not found. Make sure udev is installed on your system.", flush=True)
    except Exception as e:
        print(f"An error occurred: {str(e)}", flush=True)

    return None

def find_ttyUSB0(max_ports=10):
    for i in range(max_ports):
        device_path = f'/dev/ttyUSB{i}'
        if os.path.exists(device_path):
            usb_port_index = find_usb_port(device_path)
            if usb_port_index is not None:
                print(f"/dev/ttyUSB0 is connected to USB port: {usb_port_index}", flush=True)
                return usb_port_index

    print("/dev/ttyUSB0 not found on any USB port.", flush=True)
    return None
    
usb_port_index = find_ttyUSB0()


ser = serial.Serial(
    port= f'/dev/ttyUSB{usb_port_index}',
    baudrate=115200,
    timeout=1
)

ser.write("AT\r\n".encode())
response = ser.read_until(b'OK\r\n').decode(errors='ignore')
print(response, flush=True)

ser.write("AT+CGPS=1\r\n".encode())
response = ser.read_until(b'OK\r\n').decode(errors='ignore')
print(response, flush=True)


location_timer = time.time() + location_publish_interval
    
try:    
    while True:        
        x, y, z = accelerometer.acceleration
        #current_time = datetime.now()
        #print("%f %f %f" % (x, y, z), flush=True)
        
        if (x1 - thr > x) or (x1 + thr < x) or (y1 - thr > y) or (y1 + thr < y) or (z1 - thr > z) or (z1 + thr < z):
            if accel_flag == 0:
                print("**** intrp Occur **** ", flush=True)
                #publish_mqtt(f'R/{topic}', json.dumps({"event": "activity"}))
                json_file_path = 'stat.json'
                with open(json_file_path, 'r') as file:
                    stats = json.load(file)
                    
                stats['adxl_status'] = "1"
                stats['x-axis'] = x
                stats['y-axis'] = y
                stats['z-axis'] = z
                cTime = datetime.now()
                stats['timestamp'] = cTime.strftime('%Y:%m:%d %H:%M:%S')
                
                with open(json_file_path, 'w') as file:
                    json.dump(stats, file)
            accel_count = 0
            x1 = x
            y1 = y
            z1 = z
            accel_flag = 1
            
        if accel_flag == 1 and accel_count >= 60 :
            accel_flag = 0
            accel_count = 0
            print("**** inactivity Occur **** ", flush=True)
            with open(json_file_path, 'r') as file:
                stats = json.load(file)
                
            stats['adxl_status'] = "0"
            stats['x-axis'] = x
            stats['y-axis'] = y
            stats['z-axis'] = z
            cTime = datetime.now()
            stats['timestamp'] = cTime.strftime('%Y:%m:%d %H:%M:%S')
            
            with open(json_file_path, 'w') as file:
                json.dump(stats, file)
            #publish_mqtt(f'R/{topic}', json.dumps({"event": "inactivity"}))
            
        accel_count = accel_count + 1     
        
        current_time = time.time()
        if current_time >= location_timer:
            on_publish_location()
            location_timer = current_time + location_publish_interval

        time.sleep(1)

except KeyboardInterrupt:
	pass
