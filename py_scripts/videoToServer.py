import os
import datetime
import requests
import time
import json


config_file_path = 'config.json'

try:
    with open(config_file_path, 'r') as file:
        config_data = json.load(file)
except Exception as e:
    print(f"Error reading config file: {e}")


topic = config_data['topic']
movement_folder = config_data['movement_path']
upload_url = 'https://moleapi.9930i.com/s3/uploadFile'

def send_video(file_path):
    try:
        data = {'device_id': topic, 'type': "movement"}
        files = {'file': open(file_path, 'rb')}
        response = requests.post(upload_url, files=files, data=data)

        response.raise_for_status()  

        print(f"File '{file_path}' uploaded successfully. Deleting the file.", flush=True)
        os.remove(file_path)
    except requests.RequestException as e:
        print(f"Error uploading file '{file_path}': {e}", flush=True)

def process_videos():
    try:
        current_time = datetime.datetime.now()
        two_minutes_ago = current_time - datetime.timedelta(minutes=2)
        
        all_files = os.listdir(movement_folder)
        all_files.sort(key=lambda x: os.path.getmtime(os.path.join(movement_folder, x)))

        print(f"allFiles: {all_files}", flush=True)

        for filename in all_files:
            if filename.endswith(".mp4"):
                file_path = os.path.join(movement_folder, filename)
                modification_time = datetime.datetime.fromtimestamp(os.path.getmtime(file_path))

                if modification_time < two_minutes_ago:
                    print(f"Processing file: {filename}", flush=True)
                    send_video(file_path)
    except Exception as e:
        print(f"Error processing videos: {e}", flush=True)

def main():
    while True:
        process_videos()
        time.sleep(45)

if __name__ == "__main__":
    main()
