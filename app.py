import streamlit as st
import sounderpy as spy
import matplotlib.pyplot as plt

st.set_page_config(page_title="Live BUFKIT Viewer", layout="centered")

st.title("Live PSU BUFKIT Skew-T Viewer")
st.write("Fetch live forecasted soundings directly from the Penn State archive.")

# 1. Create UI inputs for the SounderPy function parameters
col1, col2, col3 = st.columns(3)
with col1:
    model = st.selectbox("Model", ["nam", "gfs", "hrrr", "rap", "namnest"])
with col2:
    station = st.text_input("Station ID (e.g., KGFK, KORD)", value="KGFK").upper()
with col3:
    # NAM goes out to 84 hours, GFS to 384, HRRR to 18/48 depending on run
    fcst_hour = st.number_input("Forecast Hour", min_value=0, max_value=384, value=0)

if st.button("Generate Sounding"):
    with st.spinner(f"Fetching {model.upper()} data for {station} at hour {fcst_hour}..."):
        try:
            # 2. Fetch the latest available forecast directly from PSU
            # Leaving the run date arguments blank defaults to the most recent run
            data = spy.get_bufkit_data(model.lower(), station, fcst_hour, hush=True)
            
            # 3. Generate the Skew-T and Hodograph figure
            spy.build_sounding(data)
            
            # 4. Display the active Matplotlib figure in Streamlit
            fig = plt.gcf()
            st.pyplot(fig)
            
            # Clear the figure from memory
            plt.clf()
            
        except Exception as e:
            st.error(f"Error fetching or parsing data: {e}")
            st.info("Check if the Station ID is a valid BUFKIT site or if the forecast hour exceeds the model's range.")
