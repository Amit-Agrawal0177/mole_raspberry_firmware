import json
import time
import paho.mqtt.client as mqtt

import io
from pydub import AudioSegment
from pydub.playback import play

def play_sound(sound_file):
    sound = AudioSegment.from_file(sound_file)
    play(sound)

input_json_file = 'stat.json' 
output_file = 'output.json'

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

def on_message(client, userdata, msg):
    global process
    global last_message_time
    if msg.topic == f"Ia/{topic}":
        play_sound(io.BytesIO(msg.payload))
    else:
        message = msg.payload.decode("utf-8")
        print(f"message from MQTT broker: {message}", flush=True)
        try:    
            message = json.loads(message)        
            if "ins" in message:
                instruction = message["ins"]
                if instruction == "start demand mode":
                    write_new_file(input_json_file, "1", "demand_mode")
                    publish_mqtt(f'R/{topic}', json.dumps({"event": "demand mode started"}))
                    
                elif instruction == "stop demand mode":
                    write_new_file(input_json_file, "0", "demand_mode")
                    publish_mqtt(f'R/{topic}', json.dumps({"event": "demand mode stopped"}))
                            
                elif instruction == "start alert mode":
                    write_new_file(input_json_file, "1", "alert_mode")
                    publish_mqtt(f'R/{topic}', json.dumps({"event": "alert mode started"}))
                            
                elif instruction == "stop alert mode":
                    write_new_file(input_json_file, "0", "alert_mode")
                    publish_mqtt(f'R/{topic}', json.dumps({"event": "alert mode stopped"}))
                    
                    
        except:
            pass
            
def publish_mqtt(topic, message):
    client.publish(topic, message)

def on_disconnect(client, userdata, rc):
    if rc != 0:
        print(f"Unexpected disconnection. Publishing will message. stream mqtt stop", flush=True)
        publish_mqtt(f'R/{topic}', json.dumps({"status": "device disconnected"}))
        #stop_streaming()

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        publish_mqtt(f'R/{topic}', json.dumps({"status": "device connected"}))
        print(f"Connected to MQTT broker: {broker_address} I/{topic}", flush=True)
        client.subscribe(f'I/{topic}')
        client.subscribe(f'Ia/{topic}')
    else:
        print(f"Failed to connect to MQTT broker with result code {rc}", flush=True)

client = mqtt.Client()
client.on_message = on_message

client = mqtt.Client()
client.will_set(f'R/{topic}', payload=json.dumps({"status": "device disconnected"}), qos=0, retain=False)
client.on_disconnect = on_disconnect
client.on_connect = on_connect 
client.on_message = on_message 
client.username_pw_set(user, password)
client.connect(broker_address, port, 60)
client.loop_start()  


def read_json_file(file_path):
    with open(file_path, 'r') as file:
        json_data = json.load(file)
    return json_data

def read_existing_file(file_path):
    with open(file_path, 'r') as file:
        json_data = json.load(file)
    return json_data

def write_existing_file(file_path, data):
    with open(file_path, 'w') as file:
        json.dump(data, file, indent=2)
        
def write_new_file(json_file_path, flag, mode):
    with open(json_file_path, 'r') as file:
        stats = json.load(file)
        
    stats[mode] = flag
    
    with open(json_file_path, 'w') as file:
        json.dump(stats, file)

push_interval = 30
data_timer = time.time() + push_interval
flag = 0
flag2 = 0
flag3 = 0
flag4 = 0
current_time = time.time()

def main():
    global data_timer, push_interval, flag, current_time

    while True:
        json_data = read_json_file(input_json_file)
        
        print(json_data["demand_mode"], json_data["alert_mode"], flush=True)
        existing_data = read_existing_file(output_file)
        existing_data.append(json_data)
        
        write_existing_file(output_file, existing_data)        
            
        if json_data["demand_mode"] == "1" and json_data["alert_mode"] == "1":
            if flag == 0:
                flag = 1
                push_interval = 10
                data_timer = current_time + push_interval
            
        elif json_data["demand_mode"] == "1" and json_data["alert_mode"] == "0":
            if flag == 0:
                flag = 1
                push_interval = 30
                data_timer = current_time + push_interval
            
        elif json_data["demand_mode"] == "0" and json_data["alert_mode"] == "1":
            if flag == 0:
                flag = 1
                push_interval = 60
                data_timer = current_time + push_interval
            
        elif json_data["demand_mode"] == "0" and json_data["alert_mode"] == "0":
            if flag == 0:
                flag = 1
                push_interval = 90
                data_timer = current_time + push_interval
            
        current_time = time.time()
        if current_time >= data_timer:
            publish_mqtt(f'R/{topic}', json.dumps(existing_data))
            write_existing_file(output_file, [])
            flag = 0
            
        time.sleep(10)

if __name__ == "__main__":
    main()


