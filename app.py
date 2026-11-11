import streamlit as st
import sounderpy as spy
import matplotlib.pyplot as plt
import io

st.set_page_config(page_title="Live BUFKIT Viewer", layout="wide")

# 1. Initialize the Session State to securely hold our pre-rendered images
if 'image_flipbook' not in st.session_state:
    st.session_state['image_flipbook'] = {}
if 'active_config' not in st.session_state:
    st.session_state['active_config'] = None

with st.sidebar:
    st.title("Settings")
    model = st.selectbox("Model", ["hrrr", "rap", "gfs", "rrfs"])
    station_input = st.text_input("Station ID (e.g., KRDU)", value="KRDU")
    station = station_input.strip().upper()

    st.markdown("---")
    dark_mode = st.toggle("Dark Mode", value=False)
    view_type = st.radio("View Type", ["Full Skew-T", "Hodograph Only"])
    st.markdown("---")

    if model == "gfs": max_hr = 384
    elif model == "rap": max_hr = 51
    else: max_hr = 48

    # Create a unique ID for the current settings to know if the user changed anything
    current_config = f"{model}_{station}_{view_type}_{dark_mode}"

    # 2. The "Load" button triggers the one-time generation process
    if st.button(f"Generate & Store {model.upper()} Run"):
        # Clear old images from RAM
        st.session_state['image_flipbook'] = {} 
        st.session_state['active_config'] = current_config
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for h in range(max_hr + 1):
            status_text.text(f"Rendering Hour {h}/{max_hr}...")
            try:
                # Fetch data and clear plotting memory
                data = spy.get_bufkit_data(model.lower(), station, h, hush=True)
                plt.close('all')
                
                # Draw the plot
                if view_type == "Full Skew-T":
                    spy.build_sounding(data, dark_mode=dark_mode, special_parcels='simple')
                else:
                    spy.build_hodograph(data, dark_mode=dark_mode)
                    
                fig = plt.gcf()
                buf = io.BytesIO()
                fig.savefig(buf, format="png", bbox_inches="tight", dpi=100)
                plt.close('all')
                
                # 3. Store the final PNG permanently in the session state
                st.session_state['image_flipbook'][h] = buf.getvalue()
                progress_bar.progress((h + 1) / (max_hr + 1))
                
            except IndexError:
                break # Reached the end of the BUFKIT run
            except Exception as e:
                st.error(f"Error at hour {h}: {e}")
                break
                
        status_text.success(f"✅ Successfully loaded {len(st.session_state['image_flipbook'])} hours! Scrubbing is now instant.")

    # 4. Only show the slider IF the images have been successfully generated
    if st.session_state['active_config'] == current_config and len(st.session_state['image_flipbook']) > 0:
        available_hours = list(st.session_state['image_flipbook'].keys())
        max_avail = max(available_hours)
        fcst_hour = st.slider("Forecast Hour", min_value=0, max_value=max_avail, value=0)
        st.markdown("💡 *Click the slider and use left/right keyboard arrows.*")
    else:
        fcst_hour = None

# MAIN PAGE
st.title(f"{model.upper()} Forecast Profile: {station}")

# 5. Instantly flash the saved image from the dictionary based on the slider value
if fcst_hour is not None and fcst_hour in st.session_state['image_flipbook']:
    # Note: Streamlit changed 'use_container_width' to 'use_column_width' for st.image
    st.image(st.session_state['image_flipbook'][fcst_hour], use_column_width=True)
else:
    st.info("👈 Click **Generate & Store Run** in the sidebar to build the interactive flipbook.")
