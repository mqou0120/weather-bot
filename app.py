import os
import requests
from flask import Flask, request, jsonify
from datetime import datetime, timedelta

app = Flask(__name__)
API_KEY = os.environ.get("WEATHER_API_KEY")

# --- 模組 A：抓取空氣品質 (AQI) ---
def get_aqi_info(lat, lon):
    try:
        url = f"http://api.openweathermap.org/data/2.5/air_pollution?lat={lat}&lon={lon}&appid={API_KEY}"
        res = requests.get(url, timeout=2).json()
        aqi_val = res['list'][0]['main']['aqi']
        # 台灣習慣的描述對照
        aqi_map = {1: "良好 ✨", 2: "普通 ☁️", 3: "對敏感族群不健康 ⚠️", 4: "不健康 😷", 5: "危害 🚨"}
        return aqi_map.get(aqi_val, "未知")
    except:
        return "數據獲取中..."

# --- 模組 B：抓取氣象與溫度 ---
def get_weather_info(city):
    print(f">>> [LOG] 查詢城市: {city}")
    if not API_KEY: return "⚠️ 缺少 API Key 設定"

    # 地名標準化 (處理台/臺與行政區)
    clean_city = str(city).replace("臺", "台").replace("市", "").replace("縣", "").replace("區", "").strip()
    search_query = f"{clean_city},TW" if not any(c.isalpha() for c in clean_city) else clean_city

    try:
        # 1. 座標轉換 (Geocoding)
        geo_url = f"http://api.openweathermap.org/geo/1.0/direct?q={search_query}&limit=1&appid={API_KEY}"
        geo_res = requests.get(geo_url, timeout=3).json()
        if not geo_res: return f"❓ 找不到「{city}」"

        lat, lon = geo_res[0]['lat'], geo_res[0]['lon']
        location_name = geo_res[0].get('local_names', {}).get('zh', geo_res[0]['name'])

        # 2. 氣象抓取 (單獨請求)
        w_url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={API_KEY}&units=metric&lang=zh_tw"
        w_data = requests.get(w_url, timeout=3).json()
        temp = w_data.get('main', {}).get('temp', "--")
        desc = w_data.get('weather', [{}])[0].get('description', "未知")
        desc = desc.replace("多云", "多雲").replace("阴", "陰").replace("阵雨", "陣雨")

        # 3. 空氣品質單獨呼叫 (分開抓，不影響氣溫)
        aqi_status = get_aqi_info(lat, lon)

        # 4. 生活建議邏輯
        suggest = "氣溫舒適，出門走走吧！"
        if "雨" in desc: suggest = "記得帶傘喔！ ☔"
        elif isinstance(temp, (int, float)):
            if temp >= 28: suggest = "天氣炎熱，多喝水！ 🥤"
            elif temp <= 18: suggest = "天氣偏涼，加件外套。 🧥"

        # 5. 台灣日期
        date_str = (datetime.utcnow() + timedelta(hours=8)).strftime("%Y-%m-%d")

        return (
            f"🌍 氣象服務 ({date_str})\n"
            f"--------------------------\n"
            f"📍 地點：{location_name}\n"
            f"🌡️ 溫度：{temp}°C\n"
            f"☁️ 狀態：{desc}\n"
            f"😷 空氣：{aqi_status}\n"
            f"--------------------------\n"
            f"💡 建議：{suggest}\n"
            f"--------------------------"
        )
    except Exception as e:
        print(f">>> [ERROR] {e}")
        return "⚠️ 數據解析失敗，請稍後再試。"

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        req = request.get_json(silent=True, force=True)
        res = req.get('queryResult', {})
        params = res.get('parameters', {})
        
        # 抓取地名保險機制
        city = params.get('location')
        if isinstance(city, dict): city = city.get('city') or city.get('admin-area')
        elif isinstance(city, list) and city: city = city[0]
        
        final_city = str(city) if city and str(city).lower() != 'none' else res.get('queryText', '')
        
        reply = get_weather_info(final_city)
        return jsonify({"fulfillmentText": reply})
    except:
        return jsonify({"fulfillmentText": "請輸入正確的地名（例如：板橋）。"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))