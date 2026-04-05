import os
import requests
from flask import Flask, request, jsonify
from datetime import datetime, timedelta

app = Flask(__name__)

# 從環境變數讀取 API Key
OPENWEATHER_API_KEY = os.environ.get("WEATHER_API_KEY")

def get_weather_info(city, date_str=None):
    print(f"\n>>> [LOG] 開始處理查詢。原始輸入城市: {city}")

    if not OPENWEATHER_API_KEY:
        print(">>> [ERROR] 找不到環境變數 WEATHER_API_KEY，請檢查 Render 設定！")
        return "⚠️ 伺服器配置錯誤，請檢查 API Key 設定。"

    # 1. 地名標準化與特殊補丁
    clean_city = city.replace("臺", "台")
    special_cases = {
        "淡水": "Tamsui", "淡水區": "Tamsui",
        "清水": "Qingshui", "清水區": "Qingshui",
        "羅東": "Luodong", "宜蘭": "Yilan"
    }
    
    if clean_city in special_cases:
        search_query = f"{special_cases[clean_city]},TW"
        print(f">>> [LOG] 觸發特殊補丁: {clean_city} -> {search_query}")
    else:
        tmp_city = clean_city
        for suffix in ["市", "縣", "區", "鄉", "鎮"]:
            if tmp_city.endswith(suffix):
                tmp_city = tmp_city[:-1]
        search_query = f"{tmp_city},TW" if not any(c.isalpha() for c in tmp_city) else tmp_city
        print(f">>> [LOG] 轉換搜尋關鍵字: {search_query}")

    try:
        # 2. 取得座標
        geo_url = f"http://api.openweathermap.org/geo/1.0/direct?q={search_query}&limit=1&appid={OPENWEATHER_API_KEY}"
        geo_res = requests.get(geo_url).json()
        
        if not geo_res:
            print(f">>> [WARNING] API 回傳空結果，找不到地點: {search_query}")
            return f"❓ 抱歉，找不到「{city}」的資料。"
            
        lat = geo_res[0]['lat']
        lon = geo_res[0]['lon']
        print(f">>> [LOG] 成功取得座標: {lat}, {lon}")

        # 3. 取得氣象預報
        weather_url = f"https://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={OPENWEATHER_API_KEY}&units=metric&lang=zh_tw"
        w_response = requests.get(weather_url)
        w_data = w_response.json()

        # 如果 API 回傳 code 不是 200，印出錯誤原因
        if w_data.get("cod") != "200":
            print(f">>> [ERROR] OpenWeather API 報錯: {w_data.get('message')}")
            return "⚠️ 氣象供應商連線異常。"

        current = w_data['list'][0]
        temp = current['main']['temp']
        desc = current['weather'][0]['description']
        
        # 時區與日期
        tw_time = datetime.utcnow() + timedelta(hours=8)
        today_date = tw_time.strftime("%Y-%m-%d")

        # 格式化繁體補丁
        desc = desc.replace("多云", "多雲").replace("阴", "陰").replace("阵雨", "陣雨")

        # 組合回覆
        response = (
            f"🌍 氣象服務連線成功！\n({today_date})\n"
            f"--------------------------\n"
            f"📍 地點：{city}\n🌡️ 溫度：{temp}°C\n☁️ 狀態：{desc}\n"
            f"--------------------------\n"
            f"💡 建議：天氣資訊更新完成！\n"
            f"--------------------------"
        )
        
        print(">>> [SUCCESS] 查詢完整結束，已回傳結果。")
        return response

    except Exception as e:
        # 這是最關鍵的一行：把真正的錯誤印在後台
        print(f">>> [CRITICAL] 程式碼執行崩潰！錯誤詳細內容: {str(e)}")
        return "⚠️ 數據解析發生致命錯誤。"

@app.route('/webhook', methods=['POST'])
def webhook():
    req = request.get_json(silent=True, force=True)
    query_result = req.get('queryResult', {})
    params = query_result.get('parameters', {})
    
    # 記錄 Dialogflow 傳過來的參數
    print(f"\n>>> [DEBUG] Dialogflow 傳來的參數: {params}")

    raw_location = params.get('location')
    query_city = ""
    
    # 強化解析地點邏輯
    if isinstance(raw_location, dict):
        query_city = raw_location.get('city') or raw_location.get('admin-area') or raw_location.get('subadmin-area')
    elif isinstance(raw_location, list) and len(raw_location) > 0:
        item = raw_location[0]
        query_city = item.get('city') if isinstance(item, dict) else str(item)
    else:
        query_city = str(raw_location)

    query_city = (query_city or "").strip()
    
    if not query_city or query_city.lower() == "none":
        print(">>> [WARNING] 解析不到城市名稱，結束 Webhook。")
        return jsonify({"fulfillmentText": "請問你想查詢哪個城市？"})

    reply_text = get_weather_info(query_city)
    return jsonify({"fulfillmentText": reply_text})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)