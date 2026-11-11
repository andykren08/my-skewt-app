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
            # 2. Extract the raw arrays and strip the physical units using .m
            data = get_sounding_data(model.lower(), station, fcst_hour)
            
            p = data['p'].m    # Strips 'hectopascal', leaves just the number
            T = data['T'].m    # Strips 'degC'
            Td = data['Td'].m  # Strips 'degC'
            
            # 3. Build the Plotly Figure
            fig = go.Figure()
            
            # Add Dewpoint Line
            fig.add_trace(go.Scatter(
                x=skew_x(Td, p),
                y=p,
                mode='lines+markers',
                name='Dewpoint',
                line=dict(color='green', width=3),
                marker=dict(size=4),
                # Pass the TRUE temperature into the background data
                customdata=np.stack((Td, p), axis=-1),
                # Format the tooltip to show the true data, ignoring the skewed X coordinate
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
            
            # 4. Configure the Skew-T Layout Constraints
            fig.update_layout(
                yaxis=dict(
                    type="log",
                    autorange="reversed", # Standard meteorological convention
                    title="Pressure (hPa)",
                    range=[np.log10(1050), np.log10(100)], # Lock Y axis from 1050 to 100 hPa
                    tickvals=[1000, 850, 700, 500, 300, 200, 100],
                    showgrid=True,
                    gridcolor='lightgray'
                ),
                xaxis=dict(
                    title="Skewed Temperature (°C)",
                    showticklabels=False, # Hide the skewed X values as they are arbitrary
                    showgrid=False
                ),
                hovermode="y unified", # Combines tooltips so T and Td show up on the same horizontal line
                height=800,
                margin=dict(l=20, r=20, t=20, b=20)
            )
            
            # Render the interactive plot
            st.plotly_chart(fig, use_container_width=True)
            
        except IndexError:
            st.error(f"Hour {fcst_hour} not available in this run.")
        except Exception as e:
            st.error(f"Data error: {e}")
