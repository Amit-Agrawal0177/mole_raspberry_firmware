import os
import json
import time
import subprocess
import re
import signal
from pydub import AudioSegment


config_file_path = 'config.json'
with open(config_file_path, 'r') as file:
    config_data = json.load(file)

mac = config_data['ameba_mac']
url = config_data['url']
topic = config_data['topic']
rtmp_url = f'rtmp://{url}/live/{topic}'
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
            
def write_new_file(json_file_path, flag, mode):
    with open(json_file_path, 'r') as file:
        stats = json.load(file)
        
    stats[mode] = flag
    
    with open(json_file_path, 'w') as file:
        json.dump(stats, file)
        
def read_json_file():
    try:
        file_path = 'stat.json' 
        with open(file_path, 'r') as file:
            json_data = json.load(file)
        return json_data    
    except Exception as e:
        with open(file_path, 'w') as file:
            json.dump(gb_stats, file, indent=2)
        return gb_stats
        
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

    while True:
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


def play_via_file():
	temp_audio_file = "audio.mp3"
    
	cmd = f"ffmpeg -re -i {temp_audio_file} -vn -ac 1 -ar 8000 -b:a 128k -c:a pcm_mulaw -f rtp rtp://{ip}:5004"
	print(f'{cmd}', flush=True)
	
	process = subprocess.Popen(cmd, shell=True, preexec_fn=os.setsid)
	process.wait()  # Wait for the subprocess to finish
	os.remove(temp_audio_file)

ip = find_ip_with_retry(mac)
allot_ip = ip[0]
   

process = None
last_message_time = time.time()

while True:
    time.sleep(2)
    json_data = read_json_file()
    
    if json_data["audio_flag"] == "1":
        print(f"Start playing audio", flush=True)
        play_via_file()
        write_new_file('stat.json', "0", "audio_flag")
