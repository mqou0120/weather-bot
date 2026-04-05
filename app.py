import os
import requests
from flask import Flask, request, jsonify
from datetime import datetime, timedelta

app = Flask(__name__)
OPENWEATHER_API_KEY = os.environ.get("WEATHER_API_KEY")

def get_weather_info(city):
    if not OPENWEATHER_API_KEY:
        return "⚠️ 伺服器配置錯誤，請檢查 API KEY。"

    # 1. 地名標準化
    clean_city = city.replace("臺", "台").replace("市", "").replace("縣", "").replace("區", "").strip()
    special_cases = {"淡水": "Tamsui", "清水": "Qingshui", "板橋": "Banqiao", "新莊": "Xinzhuang"}
    
    search_query = f"{special_cases[clean_city]},TW" if clean_city in special_cases else f"{clean_city},TW"
    if any(c.isalpha() for c in clean_city): search_query = clean_city

    try:
        # 2. 取得座標
        geo_url = f"http://api.openweathermap.org/geo/1.0/direct?q={search_query}&limit=1&appid={OPENWEATHER_API_KEY}"
        geo_res = requests.get(geo_url).json()
        if not geo_res: return f"❓ 找不到「{city}」的地點資訊。"
        
        lat, lon = geo_res[0]['lat'], geo_res[0]['lon']
        location_name = geo_res[0].get('local_names', {}).get('zh', geo_res[0]['name'])

        # 3. 取得氣象數據
        w_url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={OPENWEATHER_API_KEY}&units=metric&lang=zh_tw"
        w_data = requests.get(w_url).json()
        temp = w_data['main']['temp']
        desc = w_data['weather'][0]['description']

        # 4. 取得空氣品質 (AQI) - 新增功能
        aqi_url = f"http://api.openweathermap.org/data/2.5/air_pollution?lat={lat}&lon={lon}&appid={OPENWEATHER_API_KEY}"
        aqi_data = requests.get(aqi_url).json()
        aqi_val = aqi_data['list'][0]['main']['aqi']
        aqi_map = {1: "良好", 2: "普通", 3: "對敏感族群不健康", 4: "不健康", 5: "非常不健康"}
        aqi_desc = aqi_map.get(aqi_val, "未知")

        # 5. 強制繁體轉換補丁
        trad_map = {"多云": "多雲", "阴": "陰", "阵雨": "陣雨", "晴": "晴朗", "区": "區", "县": "縣"}
        for k, v in trad_map.items():
            desc = desc.replace(k, v)
            location_name = location_name.replace(k, v)

        # 6. 建議邏輯
        suggest_txt, emoji = ("天氣舒適，出門走走吧！", "✨")
        if "雨" in desc: suggest_txt, emoji = ("記得帶傘，別淋濕囉！", "☔")
        elif temp >= 28: suggest_txt, emoji = ("天氣炎熱，多補充水分！", "🥤")
        elif temp <= 18: suggest_txt, emoji = ("氣溫較低，穿件外套保暖。", "🧥")

        tw_time = datetime.utcnow() + timedelta(hours=8)
        date_str = tw_time.strftime("%Y-%m-%d")

        return (
            f"🌍 氣象服務連線成功！\n({date_str})\n"
            f"--------------------------\n"
            f"📍 地點：{location_name}\n"
            f"🌡️ 溫度：{temp}°C\n"
            f"☁️ 狀態：{desc}\n"
            f"🌬️ 空氣：{aqi_desc}\n"
            f"--------------------------\n"
            f"💡 建議：{emoji} {suggest_txt}\n"
            f"--------------------------"
        )
    except Exception as e:
        return "⚠️ 數據解析失敗。"

@app.route('/webhook', methods=['POST'])
def webhook():
    req = request.get_json(silent=True, force=True)
    res = req.get('queryResult', {})
    params = res.get('parameters', {})
    city = params.get('location')
    if isinstance(city, dict): city = city.get('city') or city.get('admin-area')
    elif isinstance(city, list) and city: city = city[0]
    
    query_city = str(city) if city and str(city).lower() != 'none' else res.get('queryText', '')
    query_city = query_city.replace("天氣", "").strip()

    return jsonify({"fulfillmentText": get_weather_info(query_city)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))