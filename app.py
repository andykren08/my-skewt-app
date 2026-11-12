import streamlit as st
import sounderpy as spy
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
import metpy.calc as mpcalc
from metpy.units import units

st.set_page_config(page_title="Interactive Skew-T", layout="wide")

# Initialize session state for the forecast hour
if 'hour_index' not in st.session_state:
    st.session_state.hour_index = 0

# The Skew Transformation Function
def skew_x(temp, pressure):
    return temp + 40 * np.log10(1000 / pressure)

# Cache the fetch so scrubbing back is instant
@st.cache_data(show_spinner=False, max_entries=50)
def get_sounding_data(model, station, hour):
    return spy.get_bufkit_data(model, station, hour, hush=True)

with st.sidebar:
    st.title("Interactive Viewer")
    model = st.selectbox("Model", ["hrrr", "rap", "gfs", "rrfs"])
    station = st.text_input("Station ID", value="KRDU").strip().upper()

    if model == "gfs": max_hr = 384
    elif model == "rap": max_hr = 51
    else: max_hr = 48
    
    st.markdown("---")
    dark_mode = st.toggle("Dark Mode", value=False)
    st.markdown("---")

    # Synchronized Navigation (using 'key' keeps the slider in focus)
    st.slider("Forecast Hour", min_value=0, max_value=max_hr, key="hour_index")
    
    col1, col2 = st.columns(2)
    if col1.button("⬅️ Prev Hour") and st.session_state.hour_index > 0:
        st.session_state.hour_index -= 1
        st.rerun()
    if col2.button("Next Hour ➡️") and st.session_state.hour_index < max_hr:
        st.session_state.hour_index += 1
        st.rerun()

st.title(f"{model.upper()} Profile: {station} | Hour {st.session_state.hour_index}")

if station:
    with st.spinner("Fetching array data..."):
        try:
            data = get_sounding_data(model.lower(), station, st.session_state.hour_index)
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
            
            # MetPy Parcel Profile Calculation
            parcel_path = mpcalc.parcel_profile(p * units.hPa, T[0] * units.degC, Td[0] * units.degC).m
            
            # Dark Mode Color Mapping
            text_color = "white" if dark_mode else "black"
            bg_color = "#0e1117" if dark_mode else "white" 
            grid_color = "#333333" if dark_mode else "lightgray"
            
            site_info = data.get('site_info', {})
            raw_init = site_info.get('run-time', ['Unknown Init'])
            raw_valid = site_info.get('valid-time', ['Unknown Valid'])
            
            def format_date(date_list):
                if isinstance(date_list, (list, tuple)) and len(date_list) >= 4:
                    return f"{date_list[1]}/{date_list[2]}/{date_list[0]} {date_list[3]}Z"
                return " ".join(date_list) if isinstance(date_list, (list, tuple)) else str(date_list)

            st.subheader(f"**Init:** {format_date(raw_init)} | **Valid:** {format_date(raw_valid)}")
            
            # 2-column layout sharing the synchronized log y-axis
            fig = make_subplots(
                rows=1, cols=2, shared_yaxes=True, 
                column_widths=[0.82, 0.18], horizontal_spacing=0.02
            )
            
            # 1. Background Isotherms (Col 1)
            p_bg = np.linspace(100, 1050, 100) 
            for temp_bg in range(-100, 60, 10): 
                is_freezing = (temp_bg == 0)
                
                fig.add_trace(go.Scatter(
                    x=skew_x(temp_bg, p_bg), y=p_bg, mode='lines',
                    line=dict(color='blue' if is_freezing else grid_color, 
                              width=2 if is_freezing else 1),
                    hoverinfo='skip', showlegend=False
                ), row=1, col=1)
                
                # Text label at the 1000 hPa level for the isotherm
                if temp_bg >= -90 and temp_bg <= 50:
                    fig.add_trace(go.Scatter(
                        x=[skew_x(temp_bg, 1000)], y=[1000],
                        mode='text', text=[f"{temp_bg}"],
                        textposition="bottom center",
                        textfont=dict(color='blue' if is_freezing else text_color, size=14),
                        hoverinfo='skip', showlegend=False
                    ), row=1, col=1)

            # 2. Background Dry Adiabats
            p_levels = np.linspace(1000, 100, 50) * units.hPa
            for t0 in range(-40, 100, 20):
                t_dry = mpcalc.dry_lapse(p_levels, t0 * units.degC).m
                fig.add_trace(go.Scatter(
                    x=skew_x(t_dry, p_levels.m), y=p_levels.m, mode='lines',
                    line=dict(color='tan', width=1, dash='dash'),
                    hoverinfo='skip', showlegend=False
                ), row=1, col=1)

            # 3. Background Moist Adiabats
            for t0 in range(-20, 50, 10):
                t_moist = mpcalc.moist_lapse(p_levels, t0 * units.degC).m
                fig.add_trace(go.Scatter(
                    x=skew_x(t_moist, p_levels.m), y=p_levels.m, mode='lines',
                    line=dict(color='lightgreen', width=1, dash='dot'),
                    hoverinfo='skip', showlegend=False
                ), row=1, col=1)

            # 4. Parcel Trajectory
            fig.add_trace(go.Scatter(
                x=skew_x(parcel_path, p), y=p, mode='lines', name='SB Parcel',
                line=dict(color=text_color, width=2, dash='dashdot'),
                hoverinfo='skip', showlegend=False
            ), row=1, col=1)

            # 5. Dewpoint Trace
            fig.add_trace(go.Scatter(
                x=skew_x(Td, p), y=p, mode='lines+markers', name='Dewpoint',
                line=dict(color='green', width=3), marker=dict(size=4),
                customdata=np.stack((Td, p, z_agl_m, z_agl_ft), axis=-1),
                hovertemplate="<b>Td:</b> %{customdata[0]:.1f}°C<br><b>P:</b> %{customdata[1]:.0f} hPa | <b>AGL:</b> %{customdata[2]:.0f}m (%{customdata[3]:.0f}ft)<extra></extra>"
            ), row=1, col=1)
            
            # 6. Temperature Trace
            fig.add_trace(go.Scatter(
                x=skew_x(T, p), y=p, mode='lines+markers', name='Temperature',
                line=dict(color='red', width=3), marker=dict(size=4),
                customdata=np.stack((T, p, z_agl_m, z_agl_ft), axis=-1),
                hovertemplate="<b>T:</b> %{customdata[0]:.1f}°C<br><b>P:</b> %{customdata[1]:.0f} hPa | <b>AGL:</b> %{customdata[2]:.0f}m (%{customdata[3]:.0f}ft)<extra></extra>"
            ), row=1, col=1)

            # 7. Directional Wind Arrows
            step = 4 
            fig.add_trace(go.Scatter(
                x=wspd[::step], y=p[::step], mode='markers+lines', name='Wind',
                line=dict(color=grid_color, width=1),
                marker=dict(
                    symbol='arrow',
                    size=12,
                    angle=270 - wdir[::step], 
                    color=wspd[::step], 
                    colorscale='Purples', 
                    showscale=False,
                    line=dict(width=1, color=text_color)
                ),
                customdata=np.stack((wspd[::step], wdir[::step], p[::step], z_agl_m[::step], z_agl_ft[::step]), axis=-1),
                hovertemplate="<b>Spd:</b> %{customdata[0]:.0f} kts<br><b>Dir:</b> %{customdata[1]:.0f}°<br><b>P:</b> %{customdata[2]:.0f} hPa | <b>AGL:</b> %{customdata[3]:.0f}m (%{customdata[4]:.0f}ft)<extra></extra>"
            ), row=1, col=2)
            
            # Unified axis configurations
            y_axis_config = dict(
                type="log",
                autorange="reversed",
                range=[np.log10(1050), np.log10(100)],
                tickvals=[1000, 850, 700, 500, 300, 200, 100],
                showgrid=True,
                gridcolor=grid_color,
                title_font=dict(size=18, color=text_color), 
                tickfont=dict(size=16, color=text_color)    
            )

            fig.update_layout(
                yaxis=dict(**y_axis_config, title="Pressure (hPa)"),
                yaxis2=dict(**y_axis_config, showticklabels=False),
                hovermode="y unified",
                height=800,
                margin=dict(l=20, r=20, t=20, b=50), 
                font=dict(size=18, color=text_color),
                paper_bgcolor=bg_color,
                plot_bgcolor=bg_color,
                hoverlabel=dict(
                    font_size=18,
                    font_color=text_color,
                    bgcolor=bg_color
                )
            )
            
            fig.update_xaxes(
                title="Temperature (°C)", 
                title_font=dict(size=18, color=text_color),
                range=[-90, 60], showticklabels=False, showgrid=False, row=1, col=1
            )
            
            fig.update_xaxes(
                title="Wind (kts)", 
                title_font=dict(size=18, color=text_color), 
                tickfont=dict(size=16, color=text_color),
                showgrid=True, gridcolor=grid_color, row=1, col=2
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
        except IndexError:
            st.error(f"Hour {st.session_state.hour_index} not available in this run.")
        except Exception as e:
            st.error(f"Data error: {e}")
