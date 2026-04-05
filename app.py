import os
import requests
from flask import Flask, request, jsonify
from datetime import datetime, timedelta

app = Flask(__name__)
# 從環境變數讀取 Key，確保安全性
API_KEY = os.environ.get("WEATHER_API_KEY")

def get_weather_info(city):
    if not API_KEY:
        return "⚠️ 系統設定錯誤：缺少 API Key。"

    # 1. 強力清洗地名：只留地名主體，拿掉所有行政區劃
    clean_city = city.replace("臺", "台").replace("市", "").replace("縣", "").replace("區", "").replace("天氣", "").strip()
    
    # 2. 台灣優先搜尋策略：中文加 ,TW，英文直接搜
    search_query = f"{clean_city},TW" if not any(c.isalpha() for c in clean_city) else clean_city

    try:
        # 3. 獲取座標 (Geocoding)
        geo_url = f"http://api.openweathermap.org/geo/1.0/direct?q={search_query}&limit=1&appid={API_KEY}"
        geo_res = requests.get(geo_url, timeout=5).json()
        
        # 如果失敗，嘗試裸搜 (備援機制)
        if not geo_res:
            geo_url = f"http://api.openweathermap.org/geo/1.0/direct?q={clean_city}&limit=1&appid={API_KEY}"
            geo_res = requests.get(geo_url, timeout=5).json()
            
        if not geo_res:
            return f"❓ 找不到「{city}」的地點資訊。"

        lat, lon = geo_res[0]['lat'], geo_res[0]['lon']
        location_name = geo_res[0].get('local_names', {}).get('zh', geo_res[0]['name'])

        # 4. 獲取氣象數據
        w_url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={API_KEY}&units=metric&lang=zh_tw"
        w_data = requests.get(w_url, timeout=5).json()
        
        temp = w_data.get('main', {}).get('temp', "--")
        desc = w_data.get('weather', [{}])[0].get('description', "未知")

        # 5. 空氣品質 (加入獨立 try，失敗不影響天氣顯示)
        aqi_desc = "暫無資料"
        try:
            aqi_url = f"http://api.openweathermap.org/data/2.5/air_pollution?lat={lat}&lon={lon}&appid={API_KEY}"
            aqi_res = requests.get(aqi_url, timeout=3).json()
            aqi_val = aqi_res['list'][0]['main']['aqi']
            aqi_map = {1: "良好", 2: "普通", 3: "不健康(敏感)", 4: "不健康", 5: "危害"}
            aqi_desc = aqi_map.get(aqi_val, "未知")
        except:
            pass

        # 6. 繁體修正與日期
        trad_map = {"多云": "多雲", "阴": "陰", "阵雨": "陣雨", "台": "臺"}
        for k, v in trad_map.items():
            desc = desc.replace(k, v)
        
        date_str = (datetime.utcnow() + timedelta(hours=8)).strftime("%Y-%m-%d")

        return (
            f"🌍 氣象連線成功 ({date_str})\n"
            f"--------------------------\n"
            f"📍 地點：{location_name}\n"
            f"🌡️ 溫度：{temp}°C\n"
            f"☁️ 狀態：{desc}\n"
            f"😷 空氣：{aqi_desc}\n"
            f"--------------------------\n"
            f"💡 建議：數據更新完成！"
        )

    except Exception as e:
        print(f">>> [ERROR] 內部錯誤: {e}")
        return "⚠️ 氣象數據解析失敗，請重新輸入地名。"

@app.route('/webhook', methods=['POST'])
def webhook():
    req = request.get_json(silent=True, force=True)
    query_text = req.get('queryResult', {}).get('queryText', '')
    params = req.get('queryResult', {}).get('parameters', {})
    
    # 優先從參數抓，抓不到就用 queryText
    city = params.get('location')
    if isinstance(city, dict):
        city = city.get('city') or city.get('admin-area')
    
    final_city = str(city) if city and str(city).lower() != 'none' else query_text
    
    reply = get_weather_info(final_city)
    return jsonify({"fulfillmentText": reply})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))