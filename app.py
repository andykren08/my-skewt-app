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

    # NEW: Pre-load button to warm the cache
    if st.button(f"Pre-load all {model.upper()} hours"):
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        available_hours = max_hr
        
        for h in range(0, max_hr + 1):
            status_text.text(f"Downloading hour {h}/{max_hr}...")
            try:
                # Calling this function caches the data in the background
                get_cached_sounding(model, station, h)
                progress_bar.progress((h + 1) / (max_hr + 1))
            except IndexError:
                # We hit the end of the file (e.g., HRRR hour 18 on a 16z run)
                available_hours = h - 1
                progress_bar.progress(1.0) # Force bar to 100%
                break
            except Exception as e:
                status_text.text(f"Stopped early at hour {h} due to an error.")
                break
                
        if available_hours < max_hr:
            status_text.success(f"✅ Pre-load complete! Note: This run stops at hour {available_hours}.")
        else:
            status_text.success("✅ Pre-load complete! Scrubbing will now be instant.")

    fcst_hour = st.slider("Forecast Hour", min_value=0, max_value=max_hr, value=0)
    
    st.markdown("---")
    st.subheader("Display Options")
    dark_mode = st.toggle("Dark Mode", value=False)
    view_type = st.radio("View Type", ["Full Skew-T", "Hodograph Only"])
    
# ... (Main page layout remains the same) ...

if station:
    with st.spinner(f"Loading {model.upper()} hour {fcst_hour} for {station}..."):
        try:
            plt.close('all') 
            data = get_cached_sounding(model, station, fcst_hour)
            
            # NEW: Add special_parcels='simple' to bypass heavy ECAPE calculations
            if view_type == "Full Skew-T":
                spy.build_sounding(data, dark_mode=dark_mode, special_parcels='simple')
            else:
                spy.build_hodograph(data, dark_mode=dark_mode)
                
            fig = plt.gcf()
            st.pyplot(fig, width='stretch')
            plt.close('all')
            
        except IndexError:
            st.error(f"Hour {fcst_hour} is not available in the current {model.upper()} run.")
            st.info("Tip: The HRRR only goes out to 48 hours on 00z, 06z, 12z, and 18z runs. Other runs stop at hour 18.")
        except Exception as e:
            st.error(f"Error fetching data: {e}")
