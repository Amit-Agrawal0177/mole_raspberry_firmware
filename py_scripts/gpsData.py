import os
import json
import subprocess
import time
from datetime import datetime, timedelta
import paho.mqtt.client as mqtt
import serial

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

config_file_path = 'config.json'
with open(config_file_path, 'r') as file:
    config_data = json.load(file)

url = config_data['url']
topic = config_data['topic']

user = config_data['user']
password = config_data['password']
port = config_data['port']
broker_address = config_data['broker_address']

location_publish_interval = config_data['location_publish_interval']
restart_var = 0

def publish_mqtt(topic, message):
    client.publish(topic, message)

def on_disconnect(client, userdata, rc):
    if rc != 0:
        print(f"Unexpected disconnection. Publishing will message.")
        publish_mqtt(f'R/{topic}', json.dumps({"status": "gps disconnected"}))

def on_publish_location(client, userdata, msg):
    #print("on_publish_location", flush=True)
    global restart_var
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
    #print(f"restart_var {restart_var}", flush=True)
    
    json_file_path = 'stat.json'
    with open(json_file_path, 'r') as file:
        stats = json.load(file)
        
    stats['lat'] = latitude
    stats['long'] = longitude
    
    with open(json_file_path, 'w') as file:
        json.dump(stats, file)
    
    location_message = {"lat": latitude, "long": longitude}
    #print(f"gps {location_message}", flush=True)
    publish_mqtt(f'R/{topic}', json.dumps(location_message))

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"Connected to MQTT broker: {broker_address}")
        publish_mqtt(f'R/{topic}', json.dumps({"status": "gps connected"}))
        local_ip_address = subprocess.check_output(['hostname', '-I']).decode('utf-8').strip()
        local_ip_address = local_ip_address.split()[0]
        print(f"local_ip_address: {local_ip_address}", flush=True)
        publish_mqtt(f'R/{topic}', json.dumps({"local_ip_address": local_ip_address}))
    else:
        print(f"Failed to connect to MQTT broker with result code {rc}")

try:
    client = mqtt.Client()
    client.will_set(f'R/{topic}', payload=json.dumps({"status": "gps disconnected"}), qos=0, retain=False)
    client.on_disconnect = on_disconnect
    client.on_connect = on_connect 
    client.username_pw_set(user, password)
    client.connect(broker_address, port, 60)
    client.loop_start()  
except:
    print("mqtt connection fail", flush="True")

location_timer = time.time() + location_publish_interval
    
try:
    while True:
        current_time = time.time()
        if current_time >= location_timer:
            on_publish_location(client, None, None)
            location_timer = current_time + location_publish_interval

        time.sleep(1)

except KeyboardInterrupt:
    client.disconnect()
    client.loop_stop()
