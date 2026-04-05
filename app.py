import os
import requests
from flask import Flask, request, jsonify
from datetime import datetime, timedelta

app = Flask(__name__)

OPENWEATHER_API_KEY = os.environ.get("WEATHER_API_KEY")

def get_weather_info(city_name):
    # --- 1. 地名標準化 (處理「臺/台」與贅字) ---
    clean_city = city_name.replace("臺", "台")
    for suffix in ["市", "縣", "區", "鄉", "鎮"]:
        if clean_city.endswith(suffix):
            clean_city = clean_city[:-1]

    # 特殊地名硬編碼補丁 (確保精準度)
    special_cases = {"淡水": "Tamsui", "清水": "Qingshui", "羅東": "Luodong"}
    search_query = f"{special_cases[clean_city]},TW" if clean_city in special_cases else f"{clean_city},TW"

    try:
        # 取得台灣時間
        tw_time = datetime.utcnow() + timedelta(hours=8)
        today_date = tw_time.strftime("%Y-%m-%d")

        # 請求座標
        geo_url = f"http://api.openweathermap.org/geo/1.0/direct?q={search_query}&limit=1&appid={OPENWEATHER_API_KEY}"
        geo_res = requests.get(geo_url).json()
        
        if not geo_res:
            print(f">>> [WARNING] 找不到地點: {search_query}")
            return f"❓ 抱歉，系統找不到「{city_name}」的地點資訊。"

        lat, lon = geo_res[0]['lat'], geo_res[0]['lon']
        
        # 請求氣象 (修正 zh_tw 語系)
        weather_url = f"https://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={OPENWEATHER_API_KEY}&units=metric&lang=zh_tw"
        w_data = requests.get(weather_url).json()

        current = w_data['list'][0]
        temp = current['main']['temp']
        desc = current['weather'][0]['description'].replace("多云", "多雲").replace("阴", "陰")
        
        return (
            f"🌍 氣象服務連線成功！\n({today_date})\n"
            f"--------------------------\n"
            f"📍 地點：{city_name} [TW]\n"
            f"🌡️ 溫度：{temp}°C\n"
            f"☁️ 狀態：{desc}\n"
            f"--------------------------\n"
            f"💡 建議：💡 天氣多變，出門請留意！\n"
            f"--------------------------"
        )
    except Exception as e:
        print(f">>> [ERROR] 氣象抓取失敗: {e}")
        return "⚠️ 服務暫時無法取得數據。"

@app.route('/webhook', methods=['POST'])
def webhook():
    req = request.get_json(silent=True, force=True)
    params = req.get('queryResult', {}).get('parameters', {})
    raw_location = params.get('location')

    # --- 關鍵修正：解析 Dialogflow 的複雜地點字典 ---
    query_city = ""
    if isinstance(raw_location, dict):
        # 按照優先順序抓取可能存在的欄位
        query_city = raw_location.get('subadmin-area') or \
                     raw_location.get('city') or \
                     raw_location.get('admin-area') or \
                     raw_location.get('business-name')
    else:
        query_city = str(raw_location)

    print(f">>> [LOG] 解析出的城市名: {query_city}")

    if not query_city or query_city.strip() == "" or query_city.lower() == "none":
        return jsonify({"fulfillmentText": "請問您想查詢哪個城市？"})

    reply = get_weather_info(query_city)
    return jsonify({"fulfillmentText": reply})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))