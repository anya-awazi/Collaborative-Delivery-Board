# Running KlausSafe on Windows

## Quick Start

The application is configured to run directly on your Windows machine (not in a virtual machine).

### Method 1: Using run.py (Recommended)
```powershell
python run.py
```

### Method 2: Using app.py directly
```powershell
python app.py
```

### Method 3: Using Flask directly
```powershell
python -m flask run
```

## Access the Application

Once running, open your web browser and go to:
- **http://localhost:5000** or
- **http://127.0.0.1:5000**

## Configuration

### Local Access Only (Current Setting)
- The application is configured with `host='127.0.0.1'`
- This means it only accepts connections from your local machine
- Safe for development and testing

### Network Access (If Needed)
If you want to access the application from other devices on your network:
1. Open `app.py` or `run.py`
2. Change `host='127.0.0.1'` to `host='0.0.0.0'`
3. Access from other devices using: `http://YOUR_WINDOWS_IP:5000`

## Windows Firewall

If you encounter connection issues:
1. Windows may ask permission for Python to access the network
2. Click "Allow access" when prompted
3. Or manually add Python to Windows Firewall exceptions

## Troubleshooting

### Port Already in Use
If port 5000 is already in use:
```python
# In app.py or run.py, change the port:
app.run(debug=True, host='127.0.0.1', port=5001)  # or any other port
```

### Python Not Found
Make sure Python is installed and in your PATH:
```powershell
python --version
```

If not found, try:
```powershell
py --version
```

### Dependencies Not Installed
```powershell
pip install -r requirements.txt
```

## Running in Background (Optional)

If you want to run the server in the background on Windows, you can use:
```powershell
# Start in background
Start-Process python -ArgumentList "run.py" -WindowStyle Hidden

# Or use PowerShell job
Start-Job -ScriptBlock { python run.py }
```

## Stop the Server

Press `Ctrl+C` in the terminal where the server is running.



