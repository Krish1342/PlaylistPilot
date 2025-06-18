#!/bin/bash

# Start Flask auth server in background
python auth_server.py &

# Wait a moment for Flask to start
sleep 3

# Start Streamlit app
streamlit run streamlit_app.py --server.port $PORT --server.address 0.0.0.0 --server.headless true