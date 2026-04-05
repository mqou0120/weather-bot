import os
import requests
from flask import Flask, request, jsonify
from datetime import datetime, timedelta, timezone

app = Flask(__name__)
API_KEY = os.environ.get("WEATHER_API_KEY")

def get_aqi_info(lat, lon):
    # (同上方修正後的 PM2.5 邏輯)
    ...

def get_weather_info(city):
    if not API_KEY: return "⚠️ 請檢查環境變數 WEATHER_API_KEY"
    
    clean_city = str(city).replace("臺", "台").replace("市", "").replace("縣", "").replace("區", "").strip()
    search_query = f"{clean_city},TW" if not any(c.isalpha() for c in clean_city) else clean_city

    try:
        # 1. 座標轉換
        geo_url = f"http://api.openweathermap.org/geo/1.0/direct?q={search_query}&limit=1&appid={API_KEY}"
        geo_res = requests.get(geo_url, timeout=3)
        if geo_res.status_code != 200 or not geo_res.json():
            return f"❓ 找不到「{city}」的地點資訊"
        
        data = geo_res.json()[0]
        lat, lon = data['lat'], data['lon']
        location_name = data.get('local_names', {}).get('zh', data['name'])

        # 2. 氣象與空氣品質 (並行或連續抓取)
        w_url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={API_KEY}&units=metric&lang=zh_tw"
        w_res = requests.get(w_url, timeout=3).json()
        
        temp = w_res.get('main', {}).get('temp', "--")
        desc = w_res.get('weather', [{}])[0].get('description', "未知").replace("多云", "多雲").replace("阴", "陰")
        aqi_status = get_aqi_info(lat, lon)

        # 建議邏輯
        suggest = "天氣不錯，出門走走！"
        if "雨" in desc: suggest = "記得帶傘 ☔"
        elif isinstance(temp, (int, float)):
            if temp >= 30: suggest = "防曬補水，小心中暑 ☀️"
            elif temp <= 16: suggest = "氣溫較低，注意保暖 🧥"

        # 3. 台灣時間修正 (Python 3.12 建議寫法)
        tw_time = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M")

        return (
            f"🌍 氣象服務 ({tw_time})\n"
            f"--------------------------\n"
            f"📍 地點：{location_name}\n"
            f"🌡️ 溫度：{temp}°C\n"
            f"☁️ 狀態：{desc}\n"
            f"😷 空氣：{aqi_status}\n"
            f"--------------------------\n"
            f"💡 建議：{suggest}"
        )
    except Exception as e:
        return "⚠️ 服務暫時無法連線，請稍後再試。"

@app.route('/webhook', methods=['POST'])
def webhook():
    req = request.get_json(silent=True)
    if not req: return jsonify({"fulfillmentText": "無效請求"})
    
    # 更安全的參數解析
    params = req.get('queryResult', {}).get('parameters', {})
    loc_val = params.get('location', "")
    
    # 判斷 loc_val 是字典還是字串
    if isinstance(loc_val, dict):
        city = loc_val.get('city') or loc_val.get('admin-area') or loc_val.get('subisland')
    else:
        city = str(loc_val)

    # 最終備援
    final_city = city if city and city != "None" else req.get('queryResult', {}).get('queryText', "")
    final_city = final_city.replace("天氣", "").strip()

    reply = get_weather_info(final_city)
    return jsonify({"fulfillmentText": reply})