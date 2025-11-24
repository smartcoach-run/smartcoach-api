# core/utils/server_banner.py

from datetime import datetime

def print_startup_banner(host: str, port: int, env: str = "dev"):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print("\n" + "=" * 70)
    print("🚀 SmartCoach Engine – API starting...")
    print(f"⏱  Start time      : {now}")
    print(f"🌍  Environment    : {env}")
    print(f"📡  API available  : http://{host}:{port}")
    print("=" * 70 + "\n")
