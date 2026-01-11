import streamlit as st
from google import genai
from google.genai import types
from PIL import Image
from io import BytesIO

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

def get_chat_response(user_input, image_bytes, description):
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
st.title("⚡ Alex's Pokemon Generator")

# --- MODE 1: GENERATION (If no image exists yet) ---
if st.session_state.pokemon_image is None:
    st.markdown("Powered by **Google Gemini 2.5 Flash Image**")
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
                    st.rerun() # Force a rerun to switch to Chat UI instantly

# --- MODE 2: CHAT (If image exists) ---
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

        # Chat Input
        if prompt := st.chat_input("Say something..."):
            # 1. Add User Message to History
            st.session_state.chat_history.append({"role": "user", "content": prompt})
            
            # 2. Display User Message immediately
            with container:
                with st.chat_message("user"):
                    st.markdown(prompt)
                    
            # 3. Get Response
            with st.spinner("The Pokemon is thinking..."):
                reply = get_chat_response(
                    prompt, 
                    st.session_state.pokemon_image, 
                    st.session_state.pokemon_desc
                )
            
            # 4. Add Model Message to History & Display
            st.session_state.chat_history.append({"role": "assistant", "content": reply})
            with container:
                with st.chat_message("assistant"):
                    st.markdown(reply)