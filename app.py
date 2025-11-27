import streamlit as st
from google import genai
from google.genai import types
from PIL import Image
from io import BytesIO
import base64

# --- Configuration ---
# In a real deployed app, these will be pulled from st.secrets
# For local testing, you can temporarily paste your key here, but remove it before committing to GitHub!
API_KEY = st.secrets.get("GOOGLE_API_KEY", "YOUR_API_KEY_HERE_FOR_LOCAL_TESTING")

def generate_pokemon(description):
    """
    Calls Google's Imagen 3 model via the GenAI SDK to create the image.
    """
    if not API_KEY or "YOUR_API_KEY" in API_KEY:
        st.error("🚨 API Key is missing! Please configure it in Streamlit secrets.")
        return None

    client = genai.Client(api_key=API_KEY)

    # Enhance the prompt to ensure consistent style
    full_prompt = (
        f"A concept art illustration of a new Pokemon. "
        f"Description: {description}. "
        f"Style: Official Ken Sugimori art style, 2D vector, watercolor texture, "
        f"white background, creature design, anime style."
    )

    # A ghost-type black kitten with blue eyes and a horn.
    try:
        # 2. Use 'gemini-2.5-flash-image' which is the correct public model
        # We use generate_content (not generate_images) for this model
        response = client.models.generate_content(
            model='gemini-2.5-flash-image',
            contents=[full_prompt],
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE"]
            )
        )

        # 3. Extract the image from the response parts
        for part in response.candidates[0].content.parts:
            if part.inline_data:
                return part.inline_data.data
                
        st.error("No image found in the response.")
        return None
            
    except Exception as e:
        st.error(f"Error communicating with Google API: {e}")
        return None

# --- UI Layout ---
st.set_page_config(page_title="Gemini Pokemon Creator", page_icon="⚡")

st.title("⚡ Gemini Pokemon Generator")
st.markdown("Powered by **Google Imagen 3**")

# 1. User Input
user_desc = st.text_area("Describe your Pokemon:", placeholder="e.g., A ghost-type kitten made of smoke with glowing blue eyes...")

if st.button("Generate"):
    if not user_desc:
        st.warning("Please enter a description!")
    else:
        with st.spinner("Summoning pixel data..."):
            # 2. Call API
            image_bytes = generate_pokemon(user_desc)
            
            if image_bytes:
                # 3. Display Image
                image = Image.open(BytesIO(image_bytes))
                st.image(image, caption="A Wild Pokemon Appeared!", use_column_width=True)
                
                # Optional: Download Button
                st.download_button(
                    label="Download Image",
                    data=image_bytes,
                    file_name="new_pokemon.png",
                    mime="image/png"
                )
