import json
import time
import paho.mqtt.client as mqtt
import subprocess
import RPi.GPIO as GPIO
import io
import re
from pydub import AudioSegment
from pydub.playback import play
import os

output_pin = 18

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)
GPIO.setup(output_pin, GPIO.OUT)

def play_sound(sound_file):
    sound = AudioSegment.from_file(sound_file)
    play(sound)

input_json_file = 'stat.json' 
output_file = 'output.json'
last_message_time = time.time()
last_demand_message_time = time.time()

config_file_path = 'config.json'
with open(config_file_path, 'r') as file:
    config_data = json.load(file)

url = config_data['url']
topic = config_data['topic']
mac = config_data['ameba_mac']

user = config_data['user']
password = config_data['password']
port = config_data['port']
broker_address = config_data['broker_address']
allot_ip = ""

gb_stats = {
		"demand_mode" : "0",
		"nw_strength" : "0",
		"pir_status" : "0",
		"adxl_status" : "0",
		"stream_status" : "0",
		"lat" : "0",
		"long" : "0",
		"x-axis" : "0",
		"y-axis" : "0",
		"z-axis" : "0" ,
		"timestamp" : "" ,
		"alert_mode" : "0",
		"audio_flag" : "0",
		"ver" : "1" 
}


def on_message(client, userdata, msg):
    global process
    global last_message_time, last_demand_message_time
    if msg.topic == f"Ia/{topic}":        
        temp_audio_file = "audio.mp3"
        with open(temp_audio_file, "wb") as audio_file:
            audio_file.write(msg.payload)
        write_new_file(input_json_file, "1", "audio_flag")
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
                    last_demand_message_time = time.time()                    
                            
                elif instruction == "start alert mode":
                    write_new_file(input_json_file, "1", "alert_mode")
                    publish_mqtt(f'R/{topic}', json.dumps({"event": "alert mode started"}))
                            
                elif instruction == "stop alert mode":
                    write_new_file(input_json_file, "0", "alert_mode")
                    publish_mqtt(f'R/{topic}', json.dumps({"event": "alert mode stopped"}))
                    
                elif instruction == "start reboot":
                    publish_mqtt(f'R/{topic}', json.dumps({"event": "reboot mode started"}))
                    reboot_raspberry_pi()
                    
                elif instruction == "start streaming":
                    write_new_file(input_json_file, "1", "stream_status")
                    publish_mqtt(f'R/{topic}', json.dumps({"event": "stream mode started"}))
                    last_message_time = time.time()
                    
                elif instruction == "start ota":
                    publish_mqtt(f'R/{topic}', json.dumps({"event": "ota started"}))
                    ota_raspberry_pi()
                           
            elif "fps" in message:
                d = read_existing_file(config_file_path)
                d["fps"] = message["fps"]
                d["height"] = message["height"]
                d["width"] = message["width"]

                write_existing_file(config_file_path, d)
        except:
            pass
    
def reboot_raspberry_pi():
    try:
        subprocess.run(['sudo', 'reboot'])
    except Exception as e:
        print(f"Error: {e}")

def ota_raspberry_pi():
    try:
        subprocess.run(['git', 'pull', 'origin', 'develop'])
    except Exception as e:
        print(f"Error: {e}")
                    
def publish_mqtt(topic, message):
    client.publish(topic, message)

def on_disconnect(client, userdata, rc):
    if rc != 0:
        print(f"Unexpected disconnection. Publishing will message. stream mqtt stop", flush=True)
        publish_mqtt(f'R/{topic}', json.dumps({"status": "device disconnected"}))
        GPIO.output(output_pin, GPIO.LOW)
        #stop_streaming()

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        publish_mqtt(f'R/{topic}', json.dumps({"status": "device connected"}))
        print(f"Connected to MQTT broker: {broker_address} I/{topic}", flush=True)
        GPIO.output(output_pin, GPIO.HIGH)
        client.subscribe(f'I/{topic}')
        client.subscribe(f'Ia/{topic}')
    else:
        print(f"Failed to connect to MQTT broker with result code {rc}", flush=True)


client = mqtt.Client()
client.will_set(f'R/{topic}', payload=json.dumps({"status": "device disconnected"}), qos=0, retain=False)
client.on_disconnect = on_disconnect
client.on_connect = on_connect 
client.on_message = on_message 
client.username_pw_set(user, password)
client.connect(broker_address, port, 60)
client.loop_start()  


def read_json_file(file_path):
    try:
        with open(file_path, 'r') as file:
            json_data = json.load(file)
        return json_data    
    except Exception as e:
        with open(file_path, 'w') as file:
            json.dump(gb_stats, file, indent=2)
        return gb_stats

def read_existing_file(file_path):
    try:
        with open(file_path, 'r') as file:
            json_data = json.load(file)
        return json_data
    except Exception as e:
        with open(file_path, 'w') as file:
            json.dump([], file, indent=2)
        return []
    

def write_existing_file(file_path, data):
    try:
        with open(file_path, 'w') as file:
            json.dump(data, file, indent=2)
    except Exception as e:
        with open(file_path, 'w') as file:
            json.dump([], file, indent=2)
            
def write_new_file(json_file_path, flag, mode):
    with open(json_file_path, 'r') as file:
        stats = json.load(file)
        
    stats[mode] = flag
    
    with open(json_file_path, 'w') as file:
        json.dump(stats, file)


push_interval = 10
data_timer = time.time() + push_interval
flag1 = 0
flag2 = 0
flag3 = 0
flag4 = 0
current_time = time.time()
save_time = time.time()

def main():
    global data_timer, push_interval, flag1, flag2, flag3, flag4, current_time, last_demand_message_time, last_message_time, save_time

    while True:
        json_data = read_json_file(input_json_file)
        
        existing_data = read_existing_file(output_file)
            
        if json_data["demand_mode"] == "1" and json_data["adxl_status"] == "1":
            if flag1 == 0:
                flag1 = 1
                flag2 = 0
                flag3 = 0
                flag4 = 0
                push_interval = 10
                data_timer = current_time + push_interval
                
            existing_data.append(json_data)        
            write_existing_file(output_file, existing_data)   
            
        elif json_data["demand_mode"] == "1" and json_data["adxl_status"] == "0":
            if flag2 == 0:
                flag1 = 0
                flag2 = 1
                flag3 = 0
                flag4 = 0
                push_interval = 120
                data_timer = current_time + push_interval
                save_timer = save_time + 60
                
            save_time = time.time()
            if save_time >= save_timer:
                save_timer = save_time + 60
                existing_data.append(json_data)
                write_existing_file(output_file, existing_data)    
            
        elif json_data["demand_mode"] == "0" and json_data["adxl_status"] == "1":
            if flag3 == 0:
                flag1 = 0
                flag2 = 0
                flag3 = 1
                flag4 = 0
                push_interval = 120
                data_timer = current_time + push_interval
                save_timer = save_time + 60
                
            save_time = time.time()
            if save_time >= save_timer:
                save_timer = save_time + 60
                existing_data.append(json_data)
                write_existing_file(output_file, existing_data)  
            
        elif json_data["demand_mode"] == "0" and json_data["adxl_status"] == "0":
            if flag4 == 0:
                flag1 = 0
                flag2 = 0
                flag3 = 0
                flag4 = 1
                push_interval = 1800
                data_timer = current_time + push_interval
                save_timer = save_time + 600
                
            save_time = time.time()
            if save_time >= save_timer:
                save_timer = save_time + 600
                existing_data.append(json_data)
                write_existing_file(output_file, existing_data)  

        else :
            existing_data.append(json_data)
            write_existing_file(output_file, existing_data) 

        current_time = time.time()
        #print(f'{json_data["demand_mode"]} {json_data["adxl_status"]} {current_time} {data_timer} {data_timer - current_time}', flush=True)
        if current_time >= data_timer:
            publish_mqtt(f'R/{topic}', json.dumps(existing_data))
            write_existing_file(output_file, [])
            data_timer = current_time + push_interval
        
        if time.time() - last_message_time > 30:
            if json_data["stream_status"] == "1":
                write_new_file(input_json_file, "0", "stream_status")
                publish_mqtt(f'R/{topic}', json.dumps({"event": "stream mode stopped"}))
        
        if time.time() - last_demand_message_time > 1800:
            if json_data["demand_mode"] == "1":
                write_new_file(input_json_file, "0", "demand_mode")
                publish_mqtt(f'R/{topic}', json.dumps({"event": "demand mode stopped"}))
                
        time.sleep(10)

if __name__ == "__main__":
    main()


