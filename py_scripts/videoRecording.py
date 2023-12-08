import cv2
import time
import os
from datetime import datetime, timedelta
import json
import shutil

config_file_path = 'config.json'
with open(config_file_path, 'r') as file:
    config_data = json.load(file)

url = config_data['url']
topic = config_data['topic']
output_folder_base = config_data['recording_path']
fps = config_data['fps']
width = config_data['width']
height = config_data['height']
duration = config_data['duration']

rtmp_url = "rtmp://localhost:1935/live"

try:
    while True:
        timestamp_now = datetime.now()
        seven_days_ago = timestamp_now - timedelta(days=1)
        base_folder_to_delete = os.path.join(output_folder_base)

        for folder_name in os.listdir(base_folder_to_delete):
            folder_path = os.path.join(base_folder_to_delete, folder_name)

            if os.path.isdir(folder_path):
                folder_date = datetime.strptime(folder_name, "%Y-%m-%d")

                if folder_date <= seven_days_ago:
                    print(f"Deleting folder from 7 days ago: {folder_path}")
                    shutil.rmtree(folder_path)
            
        timestamp_now = datetime.now()
        date_folder = timestamp_now.strftime("%Y-%m-%d")
        output_folder = os.path.join(output_folder_base, date_folder)

        if not os.path.exists(output_folder):
            os.makedirs(output_folder)

        timestamp = timestamp_now.strftime("%Y-%m-%d_%H-%M-%S")
        output_filename = os.path.join(output_folder, f"video_{timestamp}.avi")

        cap = cv2.VideoCapture(rtmp_url)

        fourcc = cv2.VideoWriter_fourcc(*'XVID')
        out = cv2.VideoWriter(output_filename, fourcc, fps, (int(cap.get(3)), int(cap.get(4))))

        start_time = time.time()

        while time.time() - start_time < duration:
            ret, frame = cap.read()
            if not ret:
                print("Error reading frame. Exiting...")
                break

            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cv2.putText(frame, timestamp, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            out.write(frame)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        cap.release()
        out.release()
        cv2.destroyAllWindows()

except KeyboardInterrupt:
    print("Recording interrupted by user.")
