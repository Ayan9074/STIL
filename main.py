import streamlit as st
import websockets
import asyncio
import base64
import json
import pyaudio
import requests
st.set_page_config(layout="wide")
# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Function to summarize text using OpenAI API
def summarize_text_with_openai_api(text, api_key, pro):
    prompts = {"summary": "Summarize the text in less words", "questions": "generate 7 questions based on this text to test my knowledge"}
    prompt = prompts[pro]
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
    }

    data = {
        "prompt": f"{prompt}:\n\n{text}",
        "temperature": 0.7,
        "max_tokens": 150,
        "top_p": 1.0,
        "frequency_penalty": 0.0,
        "presence_penalty": 0.0,
        "model": "gpt-3.5-turbo-instruct"
    }

    response = requests.post('https://api.openai.com/v1/completions', headers=headers, json=data)

    if response.status_code == 200:
        summary = response.json()['choices'][0]['text'].strip()
        return summary
    else:
        return f"Error: {response.text}"

# Configuration
GLADIA_KEY = "key goes here"
GLADIA_URL = "wss://api.gladia.io/audio/text/audio-transcription"

# Audio Configuration
FRAMES_PER_BUFFER = 3200
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
p = pyaudio.PyAudio()

# Streamlit UI Setup
if 'transcriptions' not in st.session_state:
    st.session_state['transcriptions'] = []
    st.session_state['run'] = False
    st.session_state['action'] = None
title_alignment="""
<style>
.st-emotion-cache-10trblm {
  text-align: center !important;
  margin-left: 0;
}
</style>
"""


vertical_line_css = """
<style>
.vertical-line {
    border-left: 2px solid #000;
    height: 500px;
}
</style>
"""

st.markdown(vertical_line_css, unsafe_allow_html=True)
st.markdown(title_alignment, unsafe_allow_html=True)
st.title('STIL MVP')

# Split the layout into two columns
left_col, middle_col, right_col = st.columns([1, 0.05, 2])

# Right Column Layout

notes_placeholder = st.empty()
with middle_col:
    st.markdown('<div class="vertical-line"></div>', unsafe_allow_html=True)  # This column will display as a vertical line
# Left Column Layout for actions
with left_col:
    if st.session_state['action'] == 'notes':
        st.header("Summarized Notes:")
        notes_placeholder = st.empty()
        if st.session_state['transcriptions']:
            text = '.'.join(st.session_state['transcriptions'])
            summarized_notes = summarize_text_with_openai_api(text, api_key="key goes here", pro="summary")
            notes_placeholder.markdown(summarized_notes)
        else:
            notes_placeholder.markdown("No transcription to summarize")

    elif st.session_state['action'] == 'questions':
        st.header("Questions")
        st.write("Here are some questions...")
    elif st.session_state['action'] == 'practice':
        st.header("Practice Questions:")
        notes_placeholder = st.empty()
        if st.session_state['transcriptions']:
            text = ''.join(st.session_state['transcriptions'])
            summarized_notes = summarize_text_with_openai_api(text, api_key="key goes here", pro="questions")
            notes_placeholder.markdown(summarized_notes)
        else:
            notes_placeholder.markdown("No transcription to summarize")
with right_col:
    start, stop = st.columns(2)
    start.button('Start listening', on_click=lambda: start_listening(), use_container_width=True)
    stop.button('Stop listening', on_click=lambda: stop_listening(), use_container_width=True)

    # Transcription area with a scrollbar
    trp = st.markdown(r"<div class='scrollable-container'>" +"<br>".join(f"{i+1}: {t}" for i, t in enumerate(st.session_state['transcriptions'])) + r"<style> .scrollable-container {height: 400px; overflow-y: auto;}</style> </div>", unsafe_allow_html=True)
    # Placeholder for displaying the current partial or final transcription
    current_transcription_placeholder = st.empty()

    # Buttons in the bottom 1/3 of the right column
    with st.container():
        get_notes, ask_questions, get_practice = st.columns(3)
        if get_notes.button('Get Notes', key='1'):
            st.session_state['action'] = 'notes'
            # Get the last transcription
            if st.session_state['transcriptions']:
                last_transcription = st.session_state['transcriptions'][-1]

        if ask_questions.button('Ask Questions', key='2'):
            st.session_state['action'] = 'questions'
        if get_practice.button('Get Practice Questions', key='3'):
            st.session_state['action'] = 'practice'
# Audio Streaming
stream = p.open(
    format=FORMAT,
    channels=CHANNELS,
    rate=RATE,
    input=True,
    frames_per_buffer=FRAMES_PER_BUFFER
)

# Functions to handle start and stop listening
def start_listening():
    st.session_state['run'] = True
    asyncio.run(send_receive())

def stop_listening():
    st.session_state['run'] = False

# WebSocket Communication with Gladia
async def send_receive():
    async with websockets.connect(GLADIA_URL) as ws:
        config = {
            'x-gladia-key': GLADIA_KEY,
            'language_behaviour': 'automatic single language',
            'reinject_context': 'true'
        }
        await ws.send(json.dumps(config))

        send_task = asyncio.create_task(send(ws))
        receive_task = asyncio.create_task(receive(ws))
        await asyncio.gather(send_task, receive_task)

async def send(ws):
    while st.session_state['run']:
        try:
            data = stream.read(FRAMES_PER_BUFFER)
            data = base64.b64encode(data).decode("utf-8")
            json_data = json.dumps({"frames": str(data)})
            await ws.send(json_data)
            await asyncio.sleep(0.01)
        except Exception as e:
            print(e)
            break

async def receive(ws):
    while st.session_state['run']:
        try:
            response = await ws.recv()
            utterance = json.loads(response)
            if 'transcription' in utterance:
                transcription = utterance['transcription']
                if utterance['type'] == 'partial':
                    current_transcription_placeholder.markdown(f"**Partial:** {transcription}")
                elif utterance['type'] == 'final':
                    st.session_state['transcriptions'].append(transcription)
                    # Update the transcription area within the scrollable container
                    trp.markdown(r"<div class='scrollable-container'>" +"<br>".join(f"{i+1}: {t}" for i, t in enumerate(st.session_state['transcriptions'])) + r"<style> .scrollable-container {height: 400px; overflow-y: auto;}</style> </div>", unsafe_allow_html=True)
                    current_transcription_placeholder.markdown("**Listening for more...**")
        except Exception as e:
            print(e)
            break