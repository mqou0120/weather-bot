import os
import requests
from flask import Flask, request, jsonify
from datetime import datetime, timedelta

app = Flask(__name__)
OPENWEATHER_API_KEY = os.environ.get("WEATHER_API_KEY")

def get_weather_info(city):
    print(f"\n>>> [LOG] 啟動查詢: {city}")
    if not OPENWEATHER_API_KEY:
        return "⚠️ 伺服器配置錯誤，請檢查 API KEY。"

    # 1. 地名標準化 (移除贅字)
    clean_city = city.replace("臺", "台").replace("市", "").replace("縣", "").replace("區", "").replace("天氣", "").strip()
    special_cases = {"淡水": "Tamsui", "清水": "Qingshui", "板橋": "Banqiao", "新莊": "Xinzhuang"}
    
    search_query = f"{special_cases[clean_city]},TW" if clean_city in special_cases else f"{clean_city},TW"
    if any(c.isalpha() for c in clean_city): search_query = clean_city

    try:
        # 2. 取得座標
        geo_url = f"http://api.openweathermap.org/geo/1.0/direct?q={search_query}&limit=1&appid={OPENWEATHER_API_KEY}"
        geo_res = requests.get(geo_url).json()
        if not geo_res:
            print(f">>> [WARNING] 找不到地點座標: {search_query}")
            return f"❓ 找不到「{city}」的地點資訊。"
        
        lat, lon = geo_res[0]['lat'], geo_res[0]['lon']
        location_name = geo_res[0].get('local_names', {}).get('zh', geo_res[0]['name'])

        # 3. 取得氣象數據
        w_url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={OPENWEATHER_API_KEY}&units=metric&lang=zh_tw"
        w_data = requests.get(w_url).json()
        temp = w_data.get('main', {}).get('temp', "N/A")
        desc = w_data.get('weather', [{}])[0].get('description', "無資料")

        # 4. 取得空氣品質 (加入防崩潰保護)
        aqi_desc = "暫無資料"
        try:
            aqi_url = f"http://api.openweathermap.org/data/2.5/air_pollution?lat={lat}&lon={lon}&appid={OPENWEATHER_API_KEY}"
            aqi_res = requests.get(aqi_url).json()
            aqi_val = aqi_res['list'][0]['main']['aqi']
            aqi_map = {1: "良好", 2: "普通", 3: "不健康(敏感)", 4: "不健康", 5: "危害"}
            aqi_desc = aqi_map.get(aqi_val, "未知")
        except Exception as aqi_err:
            print(f">>> [AQI ERROR] {aqi_err}")

        # 5. 強制繁體轉換補丁
        trad_map = {"多云": "多雲", "阴": "陰", "阵雨": "陣雨", "晴": "晴朗", "区": "區", "县": "縣", "台": "臺"}
        for k, v in trad_map.items():
            desc = desc.replace(k, v)
            location_name = location_name.replace(k, v)

        # 6. 建議邏輯
        suggest_txt, emoji = ("天氣舒適，出門走走吧！", "✨")
        if "雨" in desc: suggest_txt, emoji = ("記得帶傘，別淋濕囉！", "☔")
        elif isinstance(temp, (int, float)) and temp >= 28: suggest_txt, emoji = ("天氣炎熱，多補充水分！", "🥤")
        elif isinstance(temp, (int, float)) and temp <= 18: suggest_txt, emoji = ("氣溫較低，穿件外套保暖。", "🧥")

        tw_time = datetime.utcnow() + timedelta(hours=8)
        date_str = tw_time.strftime("%Y-%m-%d")

        print(f">>> [SUCCESS] 成功解析 {location_name}")
        return (
            f"🌍 氣象服務連線成功！\n({date_str})\n"
            f"--------------------------\n"
            f"📍 地點：{location_name}\n"
            f"🌡️ 溫度：{temp}°C\n"
            f"☁️ 狀態：{desc}\n"
            f"😷 空氣：{aqi_desc}\n"
            f"--------------------------\n"
            f"💡 建議：{emoji} {suggest_txt}\n"
            f"--------------------------"
        )
    except Exception as e:
        print(f">>> [CRITICAL ERROR] {str(e)}")
        return f"⚠️ 數據解析失敗，請稍後再試。"

@app.route('/webhook', methods=['POST'])
def webhook():
    req = request.get_json(silent=True, force=True)
    res = req.get('queryResult', {})
    params = res.get('parameters', {})
    
    # 嘗試從多個欄位抓取城市名稱
    city_obj = params.get('location')
    city = ""
    if isinstance(city_obj, dict):
        city = city_obj.get('city') or city_obj.get('admin-area') or city_obj.get('subadmin-area')
    elif isinstance(city_obj, list) and city_obj:
        city = city_obj[0]
    else:
        city = str(city_obj)

    # 保險：如果參數抓不到，拿對話原文
    if not city or city.lower() == 'none' or len(city) < 1:
        city = res.get('queryText', '')

    reply = get_weather_info(city)
    return jsonify({"fulfillmentText": reply})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))