#!/bin/bash
# Double-click this file to start Anvay and open it in your browser.
cd "/Users/arun/Desktop/Anvay"
source venv/bin/activate
(sleep 2 && open http://127.0.0.1:5000) &
python3 app.py
