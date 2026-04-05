import os
import requests
from flask import Flask, request, jsonify
from datetime import datetime, timedelta

app = Flask(__name__)

OPENWEATHER_API_KEY = os.environ.get("WEATHER_API_KEY")

def get_weather_info(city, date_str=None):
    # 後台日誌：記錄開始查詢
    print(f">>> [LOG] 開始查詢城市: {city}") 

    if not OPENWEATHER_API_KEY:
        print(">>> [ERROR] 缺少 API KEY 環境變數")
        return "⚠️ 伺服器配置錯誤，請檢查環境變數。"

    clean_city = city.replace("臺", "台")
    special_cases = {
        "淡水": "Tamsui", "淡水區": "Tamsui",
        "清水": "Qingshui", "清水區": "Qingshui",
        "羅東": "Luodong", "宜蘭": "Yilan"
    }
    
    if clean_city in special_cases:
        search_query = f"{special_cases[clean_city]},TW"
        print(f">>> [LOG] 觸發特殊地點補丁: {clean_city} -> {search_query}")
    else:
        tmp_city = clean_city
        for suffix in ["市", "縣", "區", "鄉", "鎮"]:
            if tmp_city.endswith(suffix):
                tmp_city = tmp_city[:-1]
        search_query = f"{tmp_city},TW" if not any(c.isalpha() for c in tmp_city) else tmp_city

    try:
        tw_time = datetime.utcnow() + timedelta(hours=8)
        today_date = tw_time.strftime("%Y-%m-%d")

        # 請求座標
        geo_url = f"http://api.openweathermap.org/geo/1.0/direct?q={search_query}&limit=1&appid={OPENWEATHER_API_KEY}"
        geo_res = requests.get(geo_url).json()
        
        if not geo_res:
            print(f">>> [WARNING] 地理編碼找不到地點: {search_query}")
            return f"❓ 抱歉，找不到「{city}」的地點資訊。"
            
        lat = geo_res[0]['lat']
        lon = geo_res[0]['lon']
        print(f">>> [LOG] 成功取得座標: {lat}, {lon}")

        # 請求氣象
        weather_url = f"https://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={OPENWEATHER_API_KEY}&units=metric&lang=zh_tw"
        w_data = requests.get(weather_url).json()

        current = w_data['list'][0]
        temp = current['main']['temp']
        desc = current['weather'][0]['description']
        
        # 組合回傳字串
        response = (
            f"🌍 氣象服務連線成功！\n({today_date})\n"
            f"--------------------------\n"
            f"📍 地點：{city}\n🌡️ 溫度：{temp}°C\n☁️ 狀態：{desc}\n"
            f"--------------------------"
        )
        
        # 後台日誌：記錄最終噴給使用者的結果
        print(f">>> [SUCCESS] 查詢成功，回傳結果:\n{response}")
        return response

    except Exception as e:
        print(f">>> [CRITICAL] 執行時發生崩潰: {str(e)}")
        return "⚠️ 氣象數據解析失敗。"

@app.route('/webhook', methods=['POST'])
def webhook():
    req = request.get_json(silent=True, force=True)
    # 記錄 Dialogflow 傳來的原始 JSON (除錯神助手)
    # print(f">>> [DEBUG] Dialogflow Request: {req}") 
    
    params = req.get('queryResult', {}).get('parameters', {})
    raw_location = params.get('location')
    
    # 提取城市... (省略重複邏輯)
    query_city = str(raw_location) # 簡化示範

    reply = get_weather_info(query_city)
    return jsonify({"fulfillmentText": reply})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))