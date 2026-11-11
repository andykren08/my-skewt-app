import streamlit as st
import sounderpy as spy
import matplotlib.pyplot as plt

# WIDE LAYOUT
st.set_page_config(page_title="Live BUFKIT Viewer", layout="wide")

# CACHING
@st.cache_data(show_spinner=False)
def get_cached_sounding(model, station, hour):
    return spy.get_bufkit_data(model.lower(), station.upper(), hour, hush=True)

# SIDEBAR CONTROLS
with st.sidebar:
    st.title("Settings")
    model = st.selectbox("Model", ["hrrr", "rap", "gfs", "rrfs"])
    
    station_input = st.text_input("Station ID (e.g., KRDU)", value="KRDU")
    station = station_input.strip().upper()

    if model == "gfs":
        max_hr = 384
    elif model == "rap":
        max_hr = 51
    else:
        max_hr = 48

    fcst_hour = st.slider("Forecast Hour", min_value=0, max_value=max_hr, value=0)
    
    st.markdown("---")
    st.subheader("Display Options")
    
    # NEW: Display Toggles
    dark_mode = st.toggle("Dark Mode", value=False)
    view_type = st.radio("View Type", ["Full Skew-T", "Hodograph Only"])
    
    st.markdown("💡 *Tip: Click the slider above and use your left/right keyboard arrows to quickly toggle through hours.*")

# MAIN PAGE
st.title(f"{model.upper()} Forecast Profile: {station}")

if station:
    with st.spinner(f"Loading {model.upper()} hour {fcst_hour} for {station}..."):
        try:
            # Aggressively clear any stuck figures from previous failed runs before starting
            plt.close('all') 
            
            data = get_cached_sounding(model, station, fcst_hour)
            
            if view_type == "Full Skew-T":
                spy.build_sounding(data, dark_mode=dark_mode)
            else:
                spy.build_hodograph(data, dark_mode=dark_mode)
                
            fig = plt.gcf()
            
            # FIXED: Streamlit syntax update to clear the log warnings
            st.pyplot(fig, width='stretch')
            
            # FIXED: Completely wipe figures from RAM to prevent the Segmentation Fault
            plt.close('all')
            
        except Exception as e:
            st.error(f"Error fetching data: {e}")
