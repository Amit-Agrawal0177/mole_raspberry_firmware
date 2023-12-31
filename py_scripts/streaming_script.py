#command = 'ffmpeg -f video4linux2 -input_format h264 -i /dev/video0 -f alsa -i default -c:v copy -c:a aac -strict experimental -f flv  ' + rtmp_url
#command = 'ffmpeg -f video4linux2 -input_format h264 -i /dev/video0 -c:v copy -f flv ' + rtmp_url
#command = 'ffmpeg -i rtmp://localhost:1935/live -c:v copy -c:a aac -strict experimental -f flv ' + rtmp_url
#command = 'ffmpeg -i rtmp://localhost:1935/live -f alsa -ac 1 -ar 44100 -i hw:2,0  -c:v copy -c:a aac -strict experimental -f flv ' + rtmp_url
#command = 'ffmpeg -i rtmp://localhost:1935/live -f alsa -i default -c:v copy -c:a aac -strict experimental -f flv ' + rtmp_url
#command = 'ffmpeg -f video4linux2 -input_format h264 -i /dev/video0 -f alsa -i default -c:v copy -c:a aac -strict experimental -f flv  ' + rtmp_url
#command = 'ffmpeg -f video4linux2 -input_format h264 -i rtmp://localhost:1935/live -f alsa -i default -c:v copy -c:a aac -strict experimental -f flv  ' + rtmp_url
#command = '/usr/bin/ffmpeg -f dshow -i video="Integrated Webcam" -f dshow -i audio="Microphone (2- High Definition Audio Device)" -c:v libx264 -c:a aac -strict -2 -f flv ' + rtmp_url




    
import os
import json
import time
import subprocess
import re
import paho.mqtt.client as mqtt
import signal


config_file_path = 'config.json'
with open(config_file_path, 'r') as file:
    config_data = json.load(file)

url = config_data['url']
topic = config_data['topic']
mac = config_data['ameba_mac']
topic = config_data['topic']

user = config_data['user']
password = config_data['password']
port = config_data['port']
broker_address = config_data['broker_address']

rtmp_url = f'rtmp://{url}/live/{topic}'

allot_ip = ""

def get_ips_for_mac(target_mac, arp_output):
    pattern = re.compile(r"(\S+) \((\d+\.\d+\.\d+\.\d+)\) at (\S+)")
    ips = []

    for line in arp_output.splitlines():
        match = pattern.search(line)
        if match:
            _, ip, mac = match.groups()
            if mac.lower() == target_mac.lower():
                ips.append(ip)

    return ips

def find_ip_with_retry(target_mac):
    max_retries = 5
    retries = 0

    while retries < max_retries:
        result = subprocess.run(["arp", "-a"], capture_output=True, text=True)
        if result.returncode == 0:
            arp_output = result.stdout
            ips = get_ips_for_mac(target_mac, arp_output)

            if ips:
                print(f"The IP addresses for MAC address {target_mac} are: {', '.join(ips)}", flush=True)
                return ips

        retries += 1
        time.sleep(5)  # Wait for 5 seconds before retrying

    print(f"Unable to find IP addresses for MAC address {target_mac} after {max_retries} retries.", flush=True)
    return []

def on_message(client, userdata, msg):
    global process
    message = msg.payload.decode("utf-8")
    print(f"message from MQTT broker: {message}", flush=True)
    message = json.loads(message)
    
    if "ins" in message:
        instruction = message["ins"]
        if instruction == "start streaming":
            if process is None or process.poll() is not None:
                publish_mqtt(f'R/{topic}', json.dumps({"event": "streaming start"}))
                start_streaming()
        elif instruction == "stop streaming":
            publish_mqtt(f'R/{topic}', json.dumps({"event": "streaming stop"}))
            stop_streaming()


def publish_mqtt(topic, message):
    client.publish(topic, message)
    

def on_disconnect(client, userdata, rc):
    if rc != 0:
        print(f"Unexpected disconnection. Publishing will message. stream mqtt stop", flush=True)
        publish_mqtt(f'R/{topic}', json.dumps({"status": "streaming disconnected"}))
        stop_streaming()

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        publish_mqtt(f'R/{topic}', json.dumps({"status": "streaming connected"}))
        print(f"Connected to MQTT broker: {broker_address} I/{topic}", flush=True)
        client.subscribe(f'I/{topic}')
    else:
        print(f"Failed to connect to MQTT broker with result code {rc}", flush=True)

def start_streaming():
    global process
    command = 'ffmpeg -i rtsp://' + allot_ip + ' -c:v copy -c:a aac -strict experimental -f flv ' + rtmp_url
    print(f"Starting streaming: {command}", flush=True)
    process = subprocess.Popen(command, shell=True, preexec_fn=os.setsid)

def stop_streaming():
    global process
    if process is not None and process.poll() is None:
        print("Stopping streaming.", flush=True)
        os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        process = None

client = mqtt.Client()
client.on_message = on_message

try:
    ip = find_ip_with_retry(mac)
    allot_ip = ip[0]
except Exception as e:
    print(f"An error occurred: {str(e)}", flush=True)

try:
    client = mqtt.Client()
    client.will_set(f'R/{topic}', payload=json.dumps({"status": "streaming disconnected"}), qos=0, retain=False)
    client.on_disconnect = on_disconnect
    client.on_connect = on_connect 
    client.on_message = on_message 
    client.username_pw_set(user, password)
    client.connect(broker_address, port, 60)
    client.loop_start()  
except:
    print("mqtt connection fail", flush=True)

process = None

try:
    while True:
        time.sleep(1)

except KeyboardInterrupt:
    if process is not None and process.poll() is None:
        print("Stopping streaming due to keyboard interrupt.", flush=True)
        os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        process = None

    client.disconnect()
    client.loop_stop()



