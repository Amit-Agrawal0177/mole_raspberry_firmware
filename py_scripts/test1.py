import os
import json
import subprocess
import time
from datetime import datetime, timedelta
import paho.mqtt.client as mqtt
import serial
import busio
import adafruit_adxl34x
import RPi.GPIO as GPIO

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

scl_pin = 3
sda_pin = 2

i2c = busio.I2C(scl=scl_pin, sda=sda_pin)
accelerometer = adafruit_adxl34x.ADXL345(i2c)

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

output_folder = config_data['movement_path']

location_publish_interval = config_data['location_publish_interval']
buffer_time = config_data['buffer_time']
width = config_data['width']
height = config_data['height']
fps = 5.0
chunk_duration = 60

thr = config_data['accel_thr']
x1 = 0
y1 = 0
z1 = 0
accel_flag = 0
accel_count = 0

rtmp_url = "rtmp://localhost:1935/live"

output_pin = 17
input_pin = 18

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)
GPIO.setup(output_pin, GPIO.OUT)
GPIO.setup(input_pin, GPIO.IN)

if not os.path.exists(output_folder):
    os.makedirs(output_folder)

def publish_mqtt(topic, message):
    client.publish(topic, message)

def on_disconnect(client, userdata, rc):
    if rc != 0:
        print(f"Unexpected disconnection. Publishing will message.")
        publish_mqtt(f'R/{topic}', json.dumps({"status": "movement disconnected"}))

def on_publish_location(client, userdata, msg):
    #print("on_publish_location", flush=True)
    command = "AT+CGPSINFO"
    ser.write((command + "\r\n").encode())
    response = ser.read_until(b'OK\r\n').decode(errors='ignore')
    print(response)
    latitude = 37.7749 
    longitude = -122.4194  
    location_message = {"latitude": latitude, "longitude": longitude}
    publish_mqtt(f'R/{topic}', json.dumps({"gps": response}))

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"Connected to MQTT broker: {broker_address}")
        publish_mqtt(f'R/{topic}', json.dumps({"status": "movement connected"}))
        local_ip_address = subprocess.check_output(['hostname', '-I']).decode('utf-8').strip()
        local_ip_address = local_ip_address.split()[0]
        print(f"local_ip_address: {local_ip_address}")
        publish_mqtt(f'R/{topic}', json.dumps({"local_ip_address": local_ip_address}))
    else:
        print(f"Failed to connect to MQTT broker with result code {rc}")

try:
    client = mqtt.Client()
    client.will_set(f'R/{topic}', payload=json.dumps({"status": "movement disconnected"}), qos=0, retain=False)
    client.on_disconnect = on_disconnect
    client.on_connect = on_connect 
    client.username_pw_set(user, password)
    client.connect(broker_address, port, 60)
    client.loop_start()  
except:
    print("mqtt connection fail", flush="True")

location_timer = time.time() + location_publish_interval
    
try:
    GPIO.output(output_pin, GPIO.HIGH)

    start_time = None
    recording = False
    out = None
    chunk_start_time = time.time()

    while True:
        x, y, z = accelerometer.acceleration
        print("%f %f %f" % (x, y, z), flush=True)
        
        if (x1 - thr > x) or (x1 + thr < x) or (y1 - thr > y) or (y1 + thr < y) or (z1 - thr > z) or (z1 + thr < z):
            if accel_flag == 0:
                print("**** intrp Occur **** ", flush=True)
                publish_mqtt(f'R/{topic}', json.dumps({"status": "activity"}))
            accel_count = 0
            x1 = x
            y1 = y
            z1 = z
            accel_flag = 1
            
        if accel_flag == 1 and accel_count >= 60 :
            accel_flag = 0
            accel_count = 0
            print("**** inactivity Occur **** ", flush=True)
            publish_mqtt(f'R/{topic}', json.dumps({"status": "inactivity"}))
            
        accel_count = accel_count + 1
        
        input_state = GPIO.input(input_pin)
        print(input_state, flush="True")

        if input_state == GPIO.HIGH:
            start_time = time.time()
            if not recording:
                print("Starting to record...", flush=True)
                publish_mqtt(f'R/{topic}', json.dumps({"status": "movement start"}))
                recording = True
                start_time = time.time()
                timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                output_filename = os.path.join(output_folder, f"video_{timestamp}.mp4")

                ffmpeg_cmd = (
                    f"ffmpeg -i {rtmp_url} -t {buffer_time} -r {fps} "
                    f"-vf scale={width}:{height} -c:a copy -c:v libx264 -preset ultrafast {output_filename}"
                )

                subprocess.run(ffmpeg_cmd, shell=True)
                chunk_start_time = time.time()

        if recording:
            elapsed_time = time.time() - start_time
            if elapsed_time >= buffer_time:
                print("Stopping recording...", flush=True)
                publish_mqtt(f'R/{topic}', json.dumps({"status": "movement stop"}))
                recording = False
                chunk_start_time = time.time()

        current_time = time.time()
        if current_time >= location_timer:
            on_publish_location(client, None, None)
            location_timer = current_time + location_publish_interval

        time.sleep(1)

except KeyboardInterrupt:
    GPIO.cleanup()
    if recording:
        print("Stopping recording due to keyboard interrupt...", flush=True)
        recording = False
    client.disconnect()
    client.loop_stop()
