import streamlit as st
import sounderpy as spy
import plotly.graph_objects as go
import numpy as np

st.set_page_config(page_title="Interactive Skew-T", layout="wide")

# 1. The Skew Transformation Function
# Shifts the X-coordinate to the right as pressure decreases, creating the 45-degree tilt
def skew_x(temp, pressure):
    return temp + 40 * np.log10(1000 / pressure)

# Cache the fetch so if they scrub back to a previous hour, it's instant
@st.cache_data(show_spinner=False, max_entries=50)
def get_sounding_data(model, station, hour):
    # Fetch raw data. hush=True keeps the terminal clean.
    return spy.get_bufkit_data(model, station, hour, hush=True)

with st.sidebar:
    st.title("Interactive Viewer")
    model = st.selectbox("Model", ["hrrr", "rap", "gfs", "rrfs"])
    station = st.text_input("Station ID", value="KRDU").strip().upper()

    if model == "gfs": max_hr = 384
    elif model == "rap": max_hr = 51
    else: max_hr = 48

    fcst_hour = st.slider("Forecast Hour", min_value=0, max_value=max_hr, value=0)

st.title(f"{model.upper()} Profile: {station} | Hour {fcst_hour}")

if station:
    with st.spinner("Fetching array data..."):
        try:
            # Extract the raw arrays and strip the physical units
            data = get_sounding_data(model.lower(), station, fcst_hour)
            p = data['p'].m
            T = data['T'].m
            Td = data['Td'].m
            
            # --- FIXED: Extract metadata properly from SounderPy's site_info dictionary ---
            site_info = data.get('site_info', {})
            
            raw_init = site_info.get('run-time', ['Unknown Init'])
            raw_valid = site_info.get('valid-time', ['Unknown Valid'])
            
            # SounderPy returns these as lists of strings (e.g., ['2023', '08', '05', '12'])
            # This joins them together into a readable timestamp
            init_time = " ".join(raw_init) if isinstance(raw_init, list) else raw_init
            valid_time = " ".join(raw_valid) if isinstance(raw_valid, list) else raw_valid
            
            # Display the timestamps
            st.subheader(f"**Init:** {init_time} | **Valid:** {valid_time}")
            
            fig = go.Figure()
            
            # Add Background Isotherms
            p_bg = np.linspace(100, 1050, 100) 
            
            for temp_bg in range(-100, 60, 10): 
                is_freezing = (temp_bg == 0)
                
                fig.add_trace(go.Scatter(
                    x=skew_x(temp_bg, p_bg),
                    y=p_bg,
                    mode='lines',
                    line=dict(color='blue' if is_freezing else 'lightgrey', 
                              width=2 if is_freezing else 1),
                    hoverinfo='skip', 
                    showlegend=False
                ))

            # Add Dewpoint Line
            fig.add_trace(go.Scatter(
                x=skew_x(Td, p),
                y=p,
                mode='lines+markers',
                name='Dewpoint',
                line=dict(color='green', width=3),
                marker=dict(size=4),
                customdata=np.stack((Td, p), axis=-1),
                hovertemplate="<b>Td:</b> %{customdata[0]:.1f}°C<br><b>P:</b> %{customdata[1]:.0f} hPa<extra></extra>"
            ))
            
            # Add Temperature Line
            fig.add_trace(go.Scatter(
                x=skew_x(T, p),
                y=p,
                mode='lines+markers',
                name='Temperature',
                line=dict(color='red', width=3),
                marker=dict(size=4),
                customdata=np.stack((T, p), axis=-1),
                hovertemplate="<b>T:</b> %{customdata[0]:.1f}°C<br><b>P:</b> %{customdata[1]:.0f} hPa<extra></extra>"
            ))
            
            # Configure Layout
            fig.update_layout(
                yaxis=dict(
                    type="log",
                    autorange="reversed",
                    title="Pressure (hPa)",
                    range=[np.log10(1050), np.log10(100)],
                    tickvals=[1000, 850, 700, 500, 300, 200, 100],
                    showgrid=True,
                    gridcolor='lightgray'
                ),
                xaxis=dict(
                    title="Skewed Temperature (°C)",
                    range=[-40, 50], 
                    showticklabels=False,
                    showgrid=False
                ),
                hovermode="y unified",
                height=800,
                margin=dict(l=20, r=20, t=20, b=20)
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
        except IndexError:
            st.error(f"Hour {fcst_hour} not available in this run.")
        except Exception as e:
            st.error(f"Data error: {e}")
