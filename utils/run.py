# run.py
# used for GH Actions with Windows pyinstaller, nothing else
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
        "debug": False
    }
    
    try:
        with open(config_path, 'w') as f:
            json.dump(default_config, f, indent=4)
        
        # More helpful message with instructions
        print("=" * 60)
        print(f"📝 Created default config file at: {config_path}")
        print("=" * 60)
        print("⚙️  To change the port or host:")
        print(f"   1. Open '{os.path.basename(config_path)}' in a text editor")
        print("   2. Change the 'port' value (default: 8080)")
        print("   3. Save the file and restart the application")
        print("=" * 60)
        print(f"🚀 Starting server on http://{default_config['host']}:{default_config['port']}")
        print("=" * 60)
        
        return default_config
    except Exception as e:
        print(f"⚠️ Warning: Could not create config file: {e}")
        return default_config

def load_config(config_path):
    """Load config from JSON file, create default if it doesn't exist"""
    if not os.path.exists(config_path):
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
    port = config.get("port", 8080)
    log_level = config.get("log_level", "info")
    debug = config.get("debug", False)
    
    # Print startup information
    print("=" * 60)
    print(f"🚀 Starting Jam.py server")
    print(f"📍 URL: http://{host}:{port}")
    print(f"📁 Config: {config_path}")
    print(f"🐛 Debug mode: {debug}")
    print("=" * 60)
    print(f"📊 Press Ctrl+C to stop the server")
    print("=" * 60)
    
    # Run the server
    uvicorn.run(
        application,
        host=host,
        port=port,
        log_level=log_level,
        access_log=debug
    )
