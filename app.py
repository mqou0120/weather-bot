import os
import requests
from flask import Flask, request, jsonify  # 確保有匯入 Flask
from datetime import datetime, timedelta, timezone

# 關鍵點：這一行一定要存在，且名稱必須是小寫的 app
app = Flask(__name__) 

API_KEY = os.environ.get("WEATHER_API_KEY")

# ... 接下來接續 get_smart_advice, get_weather_info 等函式 ...