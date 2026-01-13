import streamlit as st
from google import genai
from google.genai import types
from PIL import Image
from io import BytesIO
from io import BytesIO
import asyncio
import edge_tts
import json

# --- Configuration ---
API_KEY = st.secrets.get("GOOGLE_API_KEY", "YOUR_API_KEY_HERE_FOR_LOCAL_TESTING")

# --- Session State Initialization ---
# This keeps data alive across Streamlit reruns
if "pokemon_image" not in st.session_state:
    st.session_state.pokemon_image = None
if "pokemon_desc" not in st.session_state:
    st.session_state.pokemon_desc = ""
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "image_accepted" not in st.session_state:
    st.session_state.image_accepted = False
if "selected_voice" not in st.session_state:
    st.session_state.selected_voice = "en-US-AnaNeural" # Default cute voice

def generate_pokemon(description):
    """Generates the Pokemon Image using Gemini 2.5 Flash Image."""
    if not API_KEY or "YOUR_API_KEY" in API_KEY:
        st.error("🚨 API Key is missing!")
        return None

    client = genai.Client(api_key=API_KEY)
    
    full_prompt = (
        f"A concept art illustration of a new Pokemon. "
        f"Description: {description}. "
        f"Style: Official Ken Sugimori art style, 2D vector, watercolor texture, "
        f"white background, creature design, anime style."
    )

    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash-image',
            contents=[full_prompt],
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE"]
            )
        )
        for part in response.candidates[0].content.parts:
            if part.inline_data:
                return part.inline_data.data
        return None
    except Exception as e:
        st.error(f"Error generating image: {e}")
        return None

def determine_voice_persona(description):
    """Asks Gemini to pick a voice based on the description."""
    client = genai.Client(api_key=API_KEY)
    
    prompt = (
        f"Analyze this Pokemon description and pick the best voice: '{description}'.\n"
        f"Options:\n"
        f"- 'en-US-AnaNeural': Child, cute, small, fairy, playful.\n"
        f"- 'en-US-AriaNeural': Female, elegant, mystical, psychic.\n"
        f"- 'en-US-GuyNeural': Male, neutral, standard.\n"
        f"- 'en-US-ChristopherNeural': Deep, tough, large, dragon, militant, aggressive, fighting/rock/ground types.\n"
        f"- 'en-US-RogerNeural': Old, wise, ghost/ancient types.\n"
        f"- 'en-GB-SoniaNeural': British, intellectual, refined, royal, ice types.\n"
        f"- 'en-GB-RyanNeural': British, calm, loyal, stoic, steel/grass types.\n"
        f"- 'en-AU-WilliamNeural': Australian, adventurous, fast, electric/flying types.\n"
        f"- 'en-US-EricNeural': Energetic, friendly, young male, starter types.\n\n"
        f"Return ONLY the voice ID string."
    )
    
    try:
        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=prompt
        )
        voice_id = response.text.strip()
        # Fallback if model hallucinates extra text
        valid_voices = [
            'en-US-AnaNeural', 'en-US-AriaNeural', 'en-US-GuyNeural', 
            'en-US-ChristopherNeural', 'en-US-RogerNeural',
            'en-GB-SoniaNeural', 'en-GB-RyanNeural', 'en-AU-WilliamNeural', 'en-US-EricNeural'
        ]
        text_found = [v for v in valid_voices if v in voice_id]
        return text_found[0] if text_found else "en-US-AnaNeural"
    except Exception as e:
        print(f"Voice selection error: {e}")
        return "en-US-AnaNeural"

async def generate_speech(text, voice, rate="+0%", pitch="+0Hz"):
    """Generates audio using edge-tts."""
    communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
    audio_data = b""
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_data += chunk["data"]
    return audio_data

def get_chat_response(user_input, image_bytes, description, audio_bytes=None):
    client = genai.Client(api_key=API_KEY)
    model_id = "gemini-2.0-flash" 

    system_instruction = (
        f"You are a Pokemon. Your appearance is defined by the attached image. "
        f"Your description is: {description}. "
        f"Adopt a persona based on your looks (e.g., if you look scary, be spooky; if cute, be playful). "
        f"Only answer as the Pokemon. Do not break character. Keep responses concise and fun."
    )

    contents = []
    
    # 1. Establish Persona (Text + Image)
    # FIX: Use types.Part(text=...) and types.Blob for images
    contents.append(
        types.Content(
            role="user",
            parts=[
                types.Part(text=system_instruction),
                types.Part(
                    inline_data=types.Blob(
                        data=image_bytes, 
                        mime_type="image/png"
                    )
                )
            ]
        )
    )

    # 1.5. Add Audio Input if available
    if audio_bytes:
        contents.append(
            types.Content(
                role="user",
                parts=[
                    types.Part(
                        inline_data=types.Blob(
                            data=audio_bytes,
                            mime_type="audio/wav"
                        )
                    )
                ]
            )
        )
    
    # 2. Add confirmation 
    contents.append(
        types.Content(
            role="model",
            parts=[types.Part(text="Pika! (I understand, I am ready to chat!)")]
        )
    )

    # 3. Add existing chat history
    for msg in st.session_state.chat_history:
        role = "user" if msg["role"] == "user" else "model"
        contents.append(
            types.Content(
                role=role,
                parts=[types.Part(text=msg["content"])]
            )
        )
        
    # 4. Add the new user message
    contents.append(
        types.Content(
            role="user",
            parts=[types.Part(text=user_input)]
        )
    )

    try:
        response = client.models.generate_content(
            model=model_id,
            contents=contents
        )
        return response.text
    except Exception as e:
        return f"*(The Pokemon looks confused... Error: {e})*"

# --- UI Layout ---
st.set_page_config(page_title="Alex's Pokemon Creator", page_icon="⚡", layout="wide")
st.title("⚡ Alex's Pokemon Generator 2")

# --- MODE 1: GENERATION (If no image exists yet) ---
if st.session_state.pokemon_image is None:
    #st.markdown("Powered by **Google Gemini 2.5 Flash Image**")
    user_desc = st.text_area("Describe your Pokemon:", placeholder="e.g., A ghost-type kitten made of smoke...")

    if st.button("Generate"):
        if not user_desc:
            st.warning("Please enter a description!")
        else:
            with st.spinner("Summoning pixel data..."):
                image_bytes = generate_pokemon(user_desc)
                
                if image_bytes:
                    # Save to session state to switch modes
                    st.session_state.pokemon_image = image_bytes
                    st.session_state.pokemon_desc = user_desc
                    st.session_state.image_accepted = False
                    st.rerun() # Force a rerun to switch to Review UI

# --- MODE 2: REVIEW (Image exists, but not accepted) ---
elif not st.session_state.image_accepted:
    col1, col2 = st.columns([1, 1])
    
    with col1:
        # Display the current draft image
        image = Image.open(BytesIO(st.session_state.pokemon_image))
        st.image(image, caption="Draft Pokemon", use_container_width=True)
        
    with col2:
        st.subheader("Review your Pokemon")
        
        # Allow user to revise description
        new_desc = st.text_area("Revise Description:", value=st.session_state.pokemon_desc, height=150)
        
        col_btn1, col_btn2 = st.columns([1, 1])
        
        with col_btn1:
            if st.button("Regenerate"):
                if not new_desc:
                    st.warning("Description cannot be empty.")
                else:
                    with st.spinner("Re-summoning..."):
                        image_bytes = generate_pokemon(new_desc)
                        if image_bytes:
                            st.session_state.pokemon_image = image_bytes
                            st.session_state.pokemon_desc = new_desc
                            st.rerun()

        with col_btn2:
            if st.button("It's Perfect! Start Chatting"):
                # Determine voice persona once upon acceptance
                with st.spinner("Analyzing vocal cords..."):
                    voice_id = determine_voice_persona(st.session_state.pokemon_desc)
                    st.session_state.selected_voice = voice_id
                
                st.session_state.image_accepted = True
                st.rerun()

# --- MODE 3: CHAT (Image exists AND accepted) ---
else:
    col1, col2 = st.columns([1, 1])
    
    with col1:
        # Display the static image
        image = Image.open(BytesIO(st.session_state.pokemon_image))
        st.image(image, caption="Your Pokemon Partner", use_container_width=True)
        
        # Reset Button
        if st.button("Release & Create New"):
            st.session_state.pokemon_image = None
            st.session_state.pokemon_desc = ""
            st.session_state.chat_history = []
            st.session_state.image_accepted = False
            st.rerun()

    with col2:
        st.subheader(f"Chat with your Pokemon!")
        
        # Display Chat History
        container = st.container(height=400)
        with container:
            # Show a welcome message if history is empty
            if not st.session_state.chat_history:
                st.info(f"Go ahead, say hello to your new {st.session_state.pokemon_desc}!")
                
            for message in st.session_state.chat_history:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])

        # Chat Input (Text)
        prompt = st.chat_input("Say something...")
        
        # Chat Input (Audio)
        audio_input = st.audio_input("Or speak to your Pokemon")

        user_msg = None
        user_audio = None

        if prompt:
            user_msg = prompt
        elif audio_input:
            user_msg = "🎤 *(Voice Message)*"
            user_audio = audio_input.read()

        if user_msg:
            # 1. Add User Message to History
            st.session_state.chat_history.append({"role": "user", "content": user_msg})
            
            # 2. Display User Message immediately
            with container:
                with st.chat_message("user"):
                    st.markdown(user_msg)
                    
            # 3. Get Response
            with st.spinner("The Pokemon is thinking..."):
                reply = get_chat_response(
                    prompt if prompt else "Respond to the audio", 
                    st.session_state.pokemon_image, 
                    st.session_state.pokemon_desc,
                    audio_bytes=user_audio
                )
            
            # 4. Add Model Message to History & Display
            st.session_state.chat_history.append({"role": "assistant", "content": reply})
            
            # 5. Generate Audio Response
            try:
                # Use the selected persona voice
                # Check if it's the Deep Monster voice (ChristopherNeural) and apply pitch shift
                pitch = "+0Hz"
                rate = "+0%"
                if st.session_state.selected_voice == "en-US-ChristopherNeural":
                    pitch = "-30Hz"
                    rate = "-10%"
                
                # Run async function in sync context
                audio_response = asyncio.run(generate_speech(
                    reply, 
                    st.session_state.selected_voice,
                    rate=rate,
                    pitch=pitch
                ))
            except Exception as e:
                audio_response = None
                print(f"TTS Error: {e}")

            with container:
                with st.chat_message("assistant"):
                    st.markdown(reply)
                    if audio_response:
                        st.audio(audio_response, format="audio/mp3", autoplay=True)