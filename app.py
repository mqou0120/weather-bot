import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# --- 從環境變數讀取 API Key ---
OPENWEATHER_API_KEY = os.environ.get("WEATHER_API_KEY")

def get_weather_info(city, date_str=None):
    """處理氣象抓取邏輯"""
    if not OPENWEATHER_API_KEY:
        print("ERROR: Environment variable 'WEATHER_API_KEY' is not set!")
        return "⚠️ 伺服器配置錯誤，請檢查環境變數。"

    try:
        # 1. 取得地理座標 (Geocoding)
        geo_url = f"http://api.openweathermap.org/geo/1.0/direct?q={city}&limit=1&appid={OPENWEATHER_API_KEY}"
        geo_res = requests.get(geo_url).json()
        
        if not geo_res or len(geo_res) == 0:
            return f"❓ 找不到「{city}」的地點資訊，請換個說法試試。"
            
        lat = geo_res[0]['lat']
        lon = geo_res[0]['lon']
        location_name = geo_res[0].get('local_names', {}).get('zh', geo_res[0]['name'])

        # 2. 取得氣象數據 (5 day forecast)
        weather_url = f"https://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={OPENWEATHER_API_KEY}&units=metric&lang=zh_tw"
        w_data = requests.get(weather_url).json()

        # 3. 解析日期與挑選資料 (簡單化處理：抓取清單中的第一筆)
        # 如果未來要精準對準「明天」，可以在這裡比對 date_str
        current = w_data['list'][0]
        temp = current['main']['temp']
        desc = current['weather'][0]['description']
        
        suggestion = "天氣不錯，出門走走吧！"
        if "雨" in desc:
            suggestion = "出門記得帶把傘喔！☔"
        elif temp < 18:
            suggestion = "天氣較冷，注意保暖。🧥"

        return f"🌍 地點：{location_name}\n🌡️ 溫度：{temp}°C\n☁️ 狀態：{desc}\n💡 建議：{suggestion}"

    except Exception as e:
        print(f"Runtime Error: {e}")
        return "⚠️ 氣象數據解析失敗，請稍後再試。"

@app.route('/')
def index():
    return "Weather Bot is Online and Secure!"

@app.route('/webhook', methods=['POST'])
def webhook():
    req = request.get_json(silent=True, force=True)
    query_result = req.get('queryResult', {})
    params = query_result.get('parameters', {})
    
    # --- 關鍵修正 1：處理多樣的地點格式 ---
    raw_location = params.get('location')
    query_city = ""
    if isinstance(raw_location, dict):
        query_city = raw_location.get('city') or raw_location.get('subadmin-area') or raw_location.get('admin-area') or raw_location.get('shortcut')
    elif isinstance(raw_location, list) and len(raw_location) > 0:
        # 如果傳來的是清單，抓第一個
        first_item = raw_location[0]
        if isinstance(first_item, dict):
            query_city = first_item.get('city') or first_item.get('admin-area')
        else:
            query_city = str(first_item)
    else:
        query_city = str(raw_location)

    # --- 關鍵修正 2：處理日期參數名稱變動 ---
    target_date = params.get('date') or params.get('date-time')

    # 檢查是否抓到城市名
    if not query_city or query_city.lower() == "none" or query_city == "":
        return jsonify({"fulfillmentText": "請問您想查詢哪個城市的天氣？"})

    # 執行查詢
    reply_text = get_weather_info(query_city, target_date)
    
    return jsonify({
        "fulfillmentText": reply_text
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)