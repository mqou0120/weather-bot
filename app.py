import os
import requests
from flask import Flask, request, jsonify
from datetime import datetime, timedelta

app = Flask(__name__)
# 確保障候台能看到 API KEY 是否讀取成功
API_KEY = os.environ.get("WEATHER_API_KEY")

def get_weather_info(city):
    print(f">>> [LOG] 收到查詢請求: {city}")
    if not API_KEY:
        return "⚠️ 系統設定錯誤：缺少 API Key。"

    # 1. 基礎地名處理
    clean_city = city.replace("臺", "台").replace("市", "").replace("區", "").replace("天氣", "").strip()
    # 台灣熱門地點補丁
    special_cases = {"淡水": "Tamsui", "清水": "Qingshui", "板橋": "Banqiao"}
    search_query = f"{special_cases[clean_city]},TW" if clean_city in special_cases else f"{clean_city},TW"
    if any(c.isalpha() for c in clean_city): search_query = clean_city

    try:
        # 2. 取得座標 (設定 3 秒超時)
        geo_url = f"http://api.openweathermap.org/geo/1.0/direct?q={search_query}&limit=1&appid={API_KEY}"
        geo_res = requests.get(geo_url, timeout=3).json()
        
        if not geo_res:
            return f"❓ 抱歉，找不到「{city}」的地點資訊。"

        lat, lon = geo_res[0]['lat'], geo_res[0]['lon']
        location_name = geo_res[0].get('local_names', {}).get('zh', geo_res[0]['name'])

        # 3. 取得氣象 (設定 3 秒超時)
        w_url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={API_KEY}&units=metric&lang=zh_tw"
        w_data = requests.get(w_url, timeout=3).json()
        
        temp = w_data.get('main', {}).get('temp', "--")
        desc = w_data.get('weather', [{}])[0].get('description', "未知")

        # 4. 嘗試取得 AQI (如果失敗不影響整體回傳)
        aqi_desc = "暫無資料"
        try:
            aqi_url = f"http://api.openweathermap.org/data/2.5/air_pollution?lat={lat}&lon={lon}&appid={API_KEY}"
            aqi_res = requests.get(aqi_url, timeout=2).json()
            aqi_val = aqi_res['list'][0]['main']['aqi']
            aqi_map = {1: "良好", 2: "普通", 3: "不健康(敏感)", 4: "不健康", 5: "危害"}
            aqi_desc = aqi_map.get(aqi_val, "未知")
        except:
            print(">>> [AQI] 抓取失敗或超時")

        # 5. 繁體字修正補丁
        trad_map = {"多云": "多雲", "阴": "陰", "阵雨": "陣雨", "晴": "晴朗", "区": "區", "县": "縣"}
        for k, v in trad_map.items():
            desc = desc.replace(k, v)
            location_name = location_name.replace(k, v)

        # 6. 氣溫建議
        suggest = "天氣舒適，出門走走吧！ ✨"
        if "雨" in desc: suggest = "記得帶傘喔！ ☔"
        elif isinstance(temp, (int, float)):
            if temp >= 28: suggest = "天氣熱，多喝水！ 🥤"
            elif temp <= 18: suggest = "天氣涼，加外套。 🧥"

        date_str = (datetime.utcnow() + timedelta(hours=8)).strftime("%Y-%m-%d")

        return (
            f"🌍 氣象連線成功 ({date_str})\n"
            f"--------------------------\n"
            f"📍 地點：{location_name}\n"
            f"🌡️ 溫度：{temp}°C\n"
            f"☁️ 狀態：{desc}\n"
            f"😷 空氣：{aqi_desc}\n"
            f"--------------------------\n"
            f"💡 建議：{suggest}"
        )

    except Exception as e:
        print(f">>> [CRITICAL] 崩潰原因: {e}")
        return "⚠️ 氣象數據抓取超時，請再試一次。"

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        req = request.get_json(silent=True, force=True)
        res = req.get('queryResult', {})
        params = res.get('parameters', {})
        
        # 抓取地名
        city = params.get('location')
        if isinstance(city, dict):
            city = city.get('city') or city.get('admin-area')
        elif isinstance(city, list) and city:
            city = city[0]
        
        query_city = str(city) if city and str(city).lower() != 'none' else res.get('queryText', '')
        
        if not query_city:
            return jsonify({"fulfillmentText": "請問你想查詢哪個城市？"})

        reply = get_weather_info(query_city)
        return jsonify({"fulfillmentText": reply})
    except:
        return jsonify({"fulfillmentText": "系統忙碌中，請稍後再輸入地名。"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))