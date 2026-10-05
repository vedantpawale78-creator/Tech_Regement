@echo off
echo ========================================================
echo   SEMANTIC SENTINEL - STREAMLIT DASHBOARD
echo ========================================================
echo Starting Streamlit on http://localhost:8501 ...
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)
start http://localhost:8501
streamlit run app.py
pause
