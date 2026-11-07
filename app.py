import streamlit as st
import requests
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import metpy.calc as mpcalc
from metpy.units import units

# --- 1. CONFIGURATION & UI ---
st.set_page_config(page_title="NC TAF Skew-T Viewer", layout="wide")
st.title("Interactive Hourly Skew-T Profiles (Central NC)")

# Initialize session state for the forecast hour
if "fhour" not in st.session_state:
    st.session_state.fhour = 0

col1, col2, col3 = st.columns([2, 2, 3])
with col1:
    model = st.selectbox("Select Model", ["hrrr", "rap", "gfs", "rrfs"]).lower()
with col2:
    site = st.selectbox("Select TAF Site", ["krdu", "kgso", "kint", "kfay", "krwi"]).lower()
with col3:
    st.write("Forecast Hour Navigation")
    btn_col1, btn_col2, btn_col3 = st.columns([1, 1, 1])
    with btn_col1:
        if st.button("◀ Prev"):
            st.session_state.fhour = max(0, st.session_state.fhour - 1)
    with btn_col2:
        st.session_state.fhour = st.number_input("Hour", min_value=0, max_value=84, value=st.session_state.fhour, label_visibility="collapsed")
    with btn_col3:
        if st.button("Next ▶"):
            st.session_state.fhour += 1

# Use the session state variable for the rest of the script
forecast_hour = st.session_state.fhour

# --- 2. DATA RETRIEVAL ---
@st.cache_data(ttl=3600)
def fetch_bufkit_data(model, site):
    """Fetches the latest BUFKIT file from the PSU E-Wall archive."""
    prefix = "gfs3" if model == "gfs" else model
    url = f"http://www.meteo.psu.edu/bufkit/data/{model.upper()}/{prefix}_{site}.buf"
    response = requests.get(url)
    
    if response.status_code == 200:
        return response.text
    else:
        st.error(f"Data not available for {model.upper()} at {site.upper()}. (HTTP {response.status_code})")
        return None

# --- 3. BUFKIT PARSER ---
def parse_bufkit_hour(raw_text, target_fhour):
    """
    Extracts the data for a specific forecast hour block.
    Splits by 'STN ' which marks the start of each new time step in BUFKIT files.
    """
    # Split file into individual forecast time blocks
    blocks = raw_text.split('STN ')
    
    # Filter out the file header block to leave only the data blocks
    data_blocks = [b for b in blocks if len(b.split('\n')) > 20]
    
    # Ensure the requested hour isn't out of range
    if target_fhour >= len(data_blocks):
        return pd.DataFrame()
        
    target_block = data_blocks[target_fhour]
    data_rows = []
    
    for line in target_block.split('\n'):
        line = line.strip()
        parts = line.split()
        
        # Identify data rows: must have enough columns and start with a number (Pressure)
        if len(parts) >= 7 and parts[0].replace('.', '', 1).isdigit():
            try:
                data_rows.append({
                    "Pressure_hPa": float(parts[0]),
                    "Temp_C": float(parts[1]),
                    "Dewpoint_C": float(parts[3]),
                    "Wind_Dir": float(parts[5]),
                    "Wind_Kts": float(parts[6])
                })
            except ValueError:
                continue
                
    if not data_rows:
        return pd.DataFrame()
        
    df = pd.DataFrame(data_rows)
    df = df.drop_duplicates(subset='Pressure_hPa')
    return df.sort_values("Pressure_hPa", ascending=False).reset_index(drop=True)

# --- 4. THERMODYNAMIC CALCULATIONS & PLOTTING ---
def plot_interactive_skewt(df, model, site, fhour):
    """Generates a Plotly-based Skew-T Log-P visualization."""
    p = df['Pressure_hPa'].values * units.hPa
    T = df['Temp_C'].values * units.degC
    Td = df['Dewpoint_C'].values * units.degC
    
    # Calculate Parcel Profile using MetPy
    try:
        prof = mpcalc.parcel_profile(p, T[0], Td[0]).to('degC')
        parcel_temp = prof.magnitude
    except Exception:
        parcel_temp = np.full(len(p), np.nan) # Fallback if parcel calculation fails

    # Calculate standard Skew-T transformation for Plotly (T_skew = T - constant * log(P))
    # To mimic a true Skew-T in Plotly, we apply a manual skew factor to the X-axis
    skew_factor = 35 
    log_p = np.log10(df['Pressure_hPa'])
    
    df['Temp_Skewed'] = df['Temp_C'] + (skew_factor * log_p)
    df['Dew_Skewed'] = df['Dewpoint_C'] + (skew_factor * log_p)
    parcel_skewed = parcel_temp + (skew_factor * log_p)

    fig = go.Figure()

    # Plot Environmental Temperature
    fig.add_trace(go.Scatter(
        x=df['Temp_Skewed'], y=df['Pressure_hPa'],
        mode='lines', name='Temperature (°C)',
        line=dict(color='red', width=2),
        text=df['Temp_C'],
        hovertemplate="Temp: %{text:.1f}°C<br>Pressure: %{y:.0f} hPa<extra></extra>"
    ))

    # Plot Environmental Dewpoint
    fig.add_trace(go.Scatter(
        x=df['Dew_Skewed'], y=df['Pressure_hPa'],
        mode='lines', name='Dewpoint (°C)',
        line=dict(color='green', width=2),
        text=df['Dewpoint_C'],
        hovertemplate="Dewpoint: %{text:.1f}°C<br>Pressure: %{y:.0f} hPa<extra></extra>"
    ))

    # Plot Parcel Profile
    fig.add_trace(go.Scatter(
        x=parcel_skewed, y=df['Pressure_hPa'],
        mode='lines', name='Surface Parcel',
        line=dict(color='gray', width=1, dash='dash'),
        text=parcel_temp,
        hovertemplate="Parcel Temp: %{text:.1f}°C<br>Pressure: %{y:.0f} hPa<extra></extra>"
    ))

    # Format the Layout for Log-P Y-axis
    fig.update_layout(
        title=f"{site.upper()} | {model.upper()} | Forecast Hour: {fhour}",
        yaxis=dict(
            title="Pressure (hPa)",
            type="log",
            autorange="reversed",
            tickvals=[1000, 850, 700, 500, 300, 200, 100],
            range=[np.log10(1050), np.log10(100)],
            gridcolor="gray"
        ),
        xaxis=dict(
            title="Temperature (°C) [Skewed]",
            showticklabels=False,
            gridcolor="gray"
        ),
        height=800,
        hovermode="y unified",
        template="plotly_dark",     # Changes to dark mode
        plot_bgcolor='black',       # Matches BUFKIT black background
        paper_bgcolor='black'
    )
    
    return fig

# --- 5. EXECUTION ---
if st.button("Generate Skew-T"):
    with st.spinner("Fetching and parsing BUFKIT data..."):
        raw_data = fetch_bufkit_data(model, site)
        
        if raw_data:
            df_profile = parse_bufkit_hour(raw_data, forecast_hour)
            
            if not df_profile.empty:
                fig = plot_interactive_skewt(df_profile, model, site, forecast_hour)
                st.plotly_chart(fig, use_container_width=True)
                
                with st.expander("View Raw Data Profile"):
                    st.dataframe(df_profile)
            else:
                st.warning("Could not find the specified forecast hour in the BUFKIT file. Try Hour 0.")
