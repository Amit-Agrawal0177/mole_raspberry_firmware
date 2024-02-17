import paho.mqtt.client as mqtt
import pygame
import requests
import io
import time

from pydub import AudioSegment
from pydub.playback import play

def play_sound(sound_file):
    sound = AudioSegment.from_file(sound_file)
    play(sound)
    
# MQTT settings
# MQTT settings
user = "mole"
password = "Team@9930i"
port = 27189
broker_address = "mole_mq.9930i.com"
MQTT_TOPIC = "abc"

# Function to handle incoming MQTT messages
def on_message(client, userdata, msg):
    print("a")
    # Download the audio file from the remote server
    play_sound(io.BytesIO(msg.payload))

# Create an MQTT client instance
mqtt_client = mqtt.Client()

# Set the callback function for incoming messages
mqtt_client.on_message = on_message

# Connect to the MQTT broker
mqtt_client.username_pw_set(user, password)
mqtt_client.connect(broker_address, port, 60)


# Subscribe to the MQTT topic
mqtt_client.subscribe(MQTT_TOPIC)

# Loop to listen for incoming MQTT messages
mqtt_client.loop_start()

# Function to publish an audio message
def publish_audio_message(audio_file_path):
    # Read the audio file content
    with open(audio_file_path, "rb") as audio_file:
        audio_content = audio_file.read()

    # Publish the audio file content to the MQTT topic
    mqtt_client.publish(MQTT_TOPIC, audio_content)

# Example: Publish an audio message

# Allow some time for the audio to be played
time.sleep(10)

# Disconnect from the MQTT broker
mqtt_client.disconnect()
