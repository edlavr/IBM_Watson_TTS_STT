"""
My Text to Speech
"""
from audioop import avg
from json import load
from math import sqrt
from collections import deque
from io import BytesIO

from ibm_cloud_sdk_core.authenticators import IAMAuthenticator
from ibm_watson import TextToSpeechV1, SpeechToTextV1
from ibm_watson.websocket import RecognizeCallback, AudioSource
from pyaudio import PyAudio, paInt16

# credentials
with open('credentials.txt') as c:
    credentials = load(c)
TTS_authenticator = IAMAuthenticator(credentials['TTSapi'])
text_to_speech = TextToSpeechV1(authenticator=TTS_authenticator)
text_to_speech.set_service_url(credentials['TTSurl'])
STT_authenticator = IAMAuthenticator(credentials['STTapi'])
speech_to_text = SpeechToTextV1(authenticator=STT_authenticator)
speech_to_text.set_service_url(credentials['STTurl'])

# constants
BUFFER = 1024
RATE = 22050
FORMAT = paInt16
CHANNELS = 1
THRESHOLD = 2500
SILENCE = 3
PREV = 0.5


def speak(text):
    """
    Text To Speech core. Using Watson API to get binary data and convert them into .wav
    :param text:
    :return:
    """
    write_audio = PyAudio()

    stream = write_audio.open(format=FORMAT,
                              channels=CHANNELS,
                              rate=RATE,
                              output=True)

    data = text_to_speech.synthesize(
        text,
        voice='en-US_KevinV3Voice',
        accept='audio/wav'
    ).get_result().content.split(b'data', 1)[1]

    while data != b'':
        stream.write(data[:BUFFER])
        data = data[BUFFER:]

    stream.stop_stream()
    stream.close()
    write_audio.terminate()


def listen():
    """
    Speech To Text core
    :return:
    """
    read_audio = PyAudio()

    stream = read_audio.open(format=FORMAT,
                             channels=CHANNELS,
                             rate=RATE,
                             input=True,
                             )

    print("Listening...")

    received = b''
    voice = b''
    rel = int(RATE / BUFFER)
    silence = deque(maxlen=SILENCE * rel)
    prev_audio = b''[:int(rel / 2)]
    started = False
    n_of_phrases = 1

    while n_of_phrases > 0:
        current_data = stream.read(BUFFER)
        silence.append(sqrt(abs(avg(current_data, 4))))
        if sum([x > THRESHOLD for x in silence]) > 0:
            if not started:
                print("Recording...")
                started = True
            voice += current_data
        elif started is True:
            received = prev_audio + voice
            started = False
            silence = deque(maxlen=SILENCE * rel)
            prev_audio = b''[:int(rel / 2)]
            voice = b''
            n_of_phrases -= 1
        else:
            prev_audio += current_data

    print("Processing...")

    final = b'RIFF\xff\xff\xff\xffWAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00"V' \
            b'\x00\x00D\xac\x00\x00\x02\x00\x10\x00LIST\x1a\x00\x00\x00INFOISFT' \
            b'\x0e\x00\x00\x00Lavf58.29.100\x00data' + received

    received_data = BytesIO(final)

    class MyRecognizeCallback(RecognizeCallback):
        """
        Callback class from Watson
        """
        def __init__(self):
            RecognizeCallback.__init__(self)
            self.result = ''
            self.on_error('Couldn\'t hear what you said. Please try again later')

        def on_data(self, data):
            """
            If the voice is recognised
            :param data:
            """
            self.result = data['results'][0]['alternatives'][0]['transcript']

        def on_error(self, error):
            """
            If error occurs or the voice is not recognised
            :param error:
            """
            self.result = 'Error received: {}'.format(error)

    my_recognize_callback = MyRecognizeCallback()

    audio_source = AudioSource(received_data)
    speech_to_text.recognize_using_websocket(
        audio=audio_source,
        content_type='audio/wav',
        recognize_callback=my_recognize_callback,
        model='en-US_BroadbandModel'
    )

    received_data.close()
    stream.stop_stream()
    stream.close()
    read_audio.terminate()

    return my_recognize_callback.result


speak(listen())
