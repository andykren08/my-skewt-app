 import streamlit as st
import sounderpy as spy
import matplotlib.pyplot as plt

st.set_page_config(page_title="Live BUFKIT Viewer", layout="centered")

st.title("Live PSU BUFKIT Skew-T Viewer")
st.write("Fetch live forecasted soundings directly from the Penn State archive.")

col1, col2, col3 = st.columns(3)
with col1:
    model = st.selectbox("Model", ["rrfs", "gfs", "hrrr", "rap"])

# Dynamically set the max forecast hour depending on the model chosen
if model == "gfs":
    max_hr = 384
elif model == "rrfs":
    max_hr = 84
elif model == "rap":
    max_hr = 51
elif model == "hrrr":
    max_hr = 48
else:
    max_hr = 84

with col2:
    station = st.text_input("Station ID (e.g., KGFK, KORD)", value="KGFK").upper()
with col3:
    # Uses the dynamic max_hr variable
    fcst_hour = st.number_input("Forecast Hour", min_value=0, max_value=max_hr, value=0)

if st.button("Generate Sounding"):
    with st.spinner(f"Fetching {model.upper()} data for {station} at hour {fcst_hour}..."):
        try:
            data = spy.get_bufkit_data(model.lower(), station, fcst_hour, hush=True)
            
            spy.build_sounding(data)
            
            fig = plt.gcf()
            st.pyplot(fig)
            
            plt.clf()
            
        except ValueError as ve:
            st.error(f"Value Error: {ve}")
            st.info("If it says model not found, ensure your Streamlit deployment is using the latest version of SounderPy.")
        except Exception as e:
            st.error(f"Error fetching or parsing data: {e}")
            st.info("Check if the Station ID is a valid BUFKIT site for the selected model.")
