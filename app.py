import streamlit as st
import sounderpy as spy
import plotly.graph_objects as go
from plotly.subplots import make_subplots
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
            data = get_sounding_data(model.lower(), station, fcst_hour)
            p = data['p'].m if hasattr(data['p'], 'm') else np.array(data['p'])
            T = data['T'].m if hasattr(data['T'], 'm') else np.array(data['T'])
            Td = data['Td'].m if hasattr(data['Td'], 'm') else np.array(data['Td'])
            
            # Wind extraction
            u_raw = data.get('u', data.get('u_wind'))
            v_raw = data.get('v', data.get('v_wind'))
            u = u_raw.m if hasattr(u_raw, 'm') else np.array(u_raw)
            v = v_raw.m if hasattr(v_raw, 'm') else np.array(v_raw)
            wspd = np.hypot(u, v)
            wdir = (270 - np.rad2deg(np.arctan2(v, u))) % 360

            # Height and AGL calculation
            z_raw = data.get('z', data.get('height'))
            z = z_raw.m if hasattr(z_raw, 'm') else np.array(z_raw)
            sfc_elev = z[0]
            z_agl_m = z - sfc_elev
            z_agl_ft = z_agl_m * 3.28084
            
            site_info = data.get('site_info', {})
            raw_init = site_info.get('run-time', ['Unknown Init'])
            raw_valid = site_info.get('valid-time', ['Unknown Valid'])
            
            def format_date(date_list):
                if isinstance(date_list, (list, tuple)) and len(date_list) >= 4:
                    return f"{date_list[1]}/{date_list[2]}/{date_list[0]} {date_list[3]}Z"
                return " ".join(date_list) if isinstance(date_list, (list, tuple)) else str(date_list)

            init_time = format_date(raw_init)
            valid_time = format_date(raw_valid)
            
            st.subheader(f"**Init:** {init_time} | **Valid:** {valid_time}")
            
            # 2-column layout sharing the synchronized log y-axis
            fig = make_subplots(
                rows=1, cols=2, shared_yaxes=True, 
                column_widths=[0.82, 0.18], horizontal_spacing=0.02
            )
            
            # Background Isotherms (Col 1)
            p_bg = np.linspace(100, 1050, 100) 
            for temp_bg in range(-100, 60, 10): 
                is_freezing = (temp_bg == 0)
                fig.add_trace(go.Scatter(
                    x=skew_x(temp_bg, p_bg), y=p_bg, mode='lines',
                    line=dict(color='blue' if is_freezing else 'lightgrey', 
                              width=2 if is_freezing else 1),
                    hoverinfo='skip', showlegend=False
                ), row=1, col=1)

            # Dewpoint Trace (Col 1)
            fig.add_trace(go.Scatter(
                x=skew_x(Td, p), y=p, mode='lines+markers', name='Dewpoint',
                line=dict(color='green', width=3), marker=dict(size=4),
                customdata=np.stack((Td, p, z_agl_m, z_agl_ft), axis=-1),
                hovertemplate="<b>Td:</b> %{customdata[0]:.1f}°C<br><b>P:</b> %{customdata[1]:.0f} hPa | <b>AGL:</b> %{customdata[2]:.0f}m (%{customdata[3]:.0f}ft)<extra></extra>"
            ), row=1, col=1)
            
            # Temperature Trace (Col 1)
            fig.add_trace(go.Scatter(
                x=skew_x(T, p), y=p, mode='lines+markers', name='Temperature',
                line=dict(color='red', width=3), marker=dict(size=4),
                customdata=np.stack((T, p, z_agl_m, z_agl_ft), axis=-1),
                hovertemplate="<b>T:</b> %{customdata[0]:.1f}°C<br><b>P:</b> %{customdata[1]:.0f} hPa | <b>AGL:</b> %{customdata[2]:.0f}m (%{customdata[3]:.0f}ft)<extra></extra>"
            ), row=1, col=1)

            # Wind Profile Trace (Col 2)
            fig.add_trace(go.Scatter(
                x=wspd, y=p, mode='lines+markers', name='Wind Speed',
                line=dict(color='purple', width=2), marker=dict(size=4),
                customdata=np.stack((wspd, wdir, p, z_agl_m, z_agl_ft), axis=-1),
                hovertemplate="<b>Spd:</b> %{customdata[0]:.0f} kts<br><b>Dir:</b> %{customdata[1]:.0f}°<br><b>P:</b> %{customdata[2]:.0f} hPa | <b>AGL:</b> %{customdata[3]:.0f}m (%{customdata[4]:.0f}ft)<extra></extra>"
            ), row=1, col=2)
            
            # Unified axis configurations
            y_axis_config = dict(
                type="log",
                autorange="reversed",
                range=[np.log10(1050), np.log10(100)],
                tickvals=[1000, 850, 700, 500, 300, 200, 100],
                showgrid=True,
                gridcolor='lightgray'
            )

            fig.update_layout(
                yaxis=dict(**y_axis_config, title="Pressure (hPa)"),
                yaxis2=dict(**y_axis_config, showticklabels=False),
                hovermode="y unified",
                height=800,
                margin=dict(l=20, r=20, t=20, b=20)
            )
            
            fig.update_xaxes(title="Skewed Temperature (°C)", range=[-40, 50], showticklabels=False, showgrid=False, row=1, col=1)
            fig.update_xaxes(title="Wind (kts)", showgrid=True, gridcolor='lightgray', row=1, col=2)
            
            st.plotly_chart(fig, use_container_width=True)
            
        except IndexError:
            st.error(f"Hour {fcst_hour} not available in this run.")
        except Exception as e:
            st.error(f"Data error: {e}")
