import subprocess
import json
import os

config_file_path = 'config.json'
with open(config_file_path, 'r') as file:
    config_data = json.load(file)

output_folder = config_data['recording_path']

if not os.path.exists(output_folder):
    os.makedirs(output_folder)
    
command = ["python3", "-m", "http.server", "3030"]

with subprocess.Popen(command, cwd=output_folder) as server_process:
    try:
        server_process.wait()

    except KeyboardInterrupt:
        pass
