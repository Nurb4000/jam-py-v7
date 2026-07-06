# run.py
# used for Actions on Windows pyinstaller 
import os
import sys
import json
import uvicorn
from jam.wsgi import create_application
from asgiref.wsgi import WsgiToAsgi

# Get the directory where the executable is running
if getattr(sys, 'frozen', False):
    base_dir = sys._MEIPASS
else:
    base_dir = os.path.dirname(os.path.abspath(__file__))

# Create the application
application = WsgiToAsgi(create_application(base_dir))

def get_config_path():
    """Get the path to config.json (in the same directory as the executable)"""
    if getattr(sys, 'frozen', False):
        # Running as packaged executable - config is alongside the .exe
        config_dir = os.path.dirname(sys.executable)
    else:
        # Running as normal Python script
        config_dir = os.path.dirname(os.path.abspath(__file__))
    
    return os.path.join(config_dir, 'config.json')

def create_default_config(config_path):
    """Create a default config.json file with default values"""
    default_config = {
        "host": "0.0.0.0",
        "port": 8080,
        "log_level": "info",
        "debug": True
    }
    
    try:
        with open(config_path, 'w') as f:
            json.dump(default_config, f, indent=4)
        print(f"📝 Created default config file at: {config_path}")
        return default_config
    except Exception as e:
        print(f"⚠️ Warning: Could not create config file: {e}")
        return default_config

def load_config(config_path):
    """Load config from JSON file, create default if it doesn't exist"""
    if not os.path.exists(config_path):
        print(f"📝 Config file not found, creating default...")
        return create_default_config(config_path)
    
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        print(f"✅ Loaded config from: {config_path}")
        return config
    except Exception as e:
        print(f"⚠️ Warning: Could not read config file: {e}")
        print(f"📝 Using default settings...")
        return create_default_config(config_path)

if __name__ == "__main__":
    # Get config path and load configuration
    config_path = get_config_path()
    config = load_config(config_path)
    
    # Extract config values with defaults
    host = config.get("host", "0.0.0.0")
    port = config.get("port", 5000)
    log_level = config.get("log_level", "info")
    debug = config.get("debug", False)
    
    # Print startup information
    print("=" * 50)
    print(f"🚀 Starting Jam.py server")
    print(f"📍 URL: http://{host}:{port}")
    print(f"📁 Config: {config_path}")
    print(f"🐛 Debug mode: {debug}")
    print("=" * 50)
    print(f"📊 Press Ctrl+C to stop the server")
    print("=" * 50)
    
    # Run the server
    uvicorn.run(
        application,
        host=host,
        port=port,
        log_level=log_level,
        access_log=debug
    )
