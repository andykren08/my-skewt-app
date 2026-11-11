import streamlit as st
import sounderpy as spy
import matplotlib.pyplot as plt
import io

st.set_page_config(page_title="Live BUFKIT Viewer", layout="wide")

# NEW: We now cache the rendered PNG image, not the raw data.
# max_entries=100 ensures we don't accidentally fill the server's RAM with images
@st.cache_data(show_spinner=False, max_entries=100)
def get_cached_plot_image(model, station, hour, view, dark):
    # 1. Fetch data
    data = spy.get_bufkit_data(model.lower(), station.upper(), hour, hush=True)
    
    # 2. Aggressively clear old memory before drawing
    plt.close('all')
    
    # 3. Draw the plot
    if view == "Full Skew-T":
        spy.build_sounding(data, dark_mode=dark, special_parcels='simple')
    else:
        spy.build_hodograph(data, dark_mode=dark)
        
    fig = plt.gcf()
    
    # 4. Save the plot to an invisible PNG image buffer
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", dpi=100) # dpi=100 keeps it fast
    
    # 5. Destroy the heavy Matplotlib figure instantly
    plt.close('all')
    
    # Return just the raw image data
    return buf.getvalue()

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
        
    st.markdown("---")
    st.subheader("Display Options")
    dark_mode = st.toggle("Dark Mode", value=False)
    view_type = st.radio("View Type", ["Full Skew-T", "Hodograph Only"])
    st.markdown("---")

    # UPDATED: Pre-load button now renders and caches the PNG images
    if st.button(f"Pre-load all {model.upper()} hours"):
        progress_bar = st.progress(0)
        status_text = st.empty()
        available_hours = max_hr
        
        for h in range(0, max_hr + 1):
            status_text.text(f"Rendering hour {h}/{max_hr}... (This takes a moment)")
            try:
                get_cached_plot_image(model, station, h, view_type, dark_mode)
                progress_bar.progress((h + 1) / (max_hr + 1))
            except IndexError:
                available_hours = h - 1
                progress_bar.progress(1.0)
                break
            except Exception as e:
                status_text.text(f"Stopped early at hour {h}.")
                break
                
        if available_hours < max_hr:
            status_text.success(f"✅ Images rendered! (Run stops at hour {available_hours})")
        else:
            status_text.success("✅ Images rendered! Scrubbing is now instant.")

    fcst_hour = st.slider("Forecast Hour", min_value=0, max_value=max_hr, value=0)
    st.markdown("💡 *Tip: Click the slider above and use your left/right keyboard arrows to quickly toggle through hours.*")

# MAIN PAGE
st.title(f"{model.upper()} Forecast Profile: {station}")

if station:
    with st.spinner(f"Loading {model.upper()} hour {fcst_hour} for {station}..."):
        try:
            # Fetch the pre-rendered image buffer
            img_bytes = get_cached_plot_image(model, station, fcst_hour, view_type, dark_mode)
            
            # Display it as a raw image instead of a Matplotlib object
            st.image(img_bytes, use_container_width=True)
            
        except IndexError:
            st.error(f"Hour {fcst_hour} is not available in the current {model.upper()} run.")
        except Exception as e:
            st.error(f"Error fetching data: {e}")
