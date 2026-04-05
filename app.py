import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# --- 【專業版：從環境變數讀取 API Key】 ---
# 這裡不再寫死金鑰，而是去抓系統中名為 "WEATHER_API_KEY" 的變數
OPENWEATHER_API_KEY = os.environ.get("WEATHER_API_KEY")

def get_weather_info(city, date_str=None):
    """處理氣象抓取邏輯"""
    # 如果沒設定 API Key，先回傳錯誤提示
    if not OPENWEATHER_API_KEY:
        return "⚠️ 系統尚未配置 API Key，請檢查環境變數。"

    try:
        # 1. 取得地理座標 (Geocoding)
        geo_url = f"http://api.openweathermap.org/geo/1.0/direct?q={city}&limit=1&appid={OPENWEATHER_API_KEY}"
        geo_res = requests.get(geo_url).json()
        
        if not geo_res:
            return f"❓ 找不到「{city}」的地點資訊，請檢查名稱是否正確。"
            
        lat = geo_res[0]['lat']
        lon = geo_res[0]['lon']
        location_name = geo_res[0].get('local_names', {}).get('zh', geo_res[0]['name'])

        # 2. 取得氣象數據
        weather_url = f"https://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={OPENWEATHER_API_KEY}&units=metric&lang=zh_tw"
        w_data = requests.get(weather_url).json()

        # 抓取第一筆資料
        current = w_data['list'][0]
        temp = current['main']['temp']
        desc = current['weather'][0]['description']
        
        # 3. 建議邏輯
        suggestion = "天氣不錯，出門走走吧！"
        if "雨" in desc:
            suggestion = "出門記得帶把傘喔！☔"
        elif temp < 18:
            suggestion = "天氣較冷，多穿件外套吧！🧥"

        return f"🌍 地點：{location_name}\n🌡️ 溫度：{temp}°C\n☁️ 狀態：{desc}\n💡 建議：{suggestion}"

    except Exception as e:
        print(f"Error: {e}")
        return "⚠️ 氣象系統連線異常，請稍後再試。"

@app.route('/')
def index():
    return "Weather Bot is Running Securely!"

@app.route('/webhook', methods=['POST'])
def webhook():
    req = request.get_json(silent=True, force=True)
    query_result = req.get('queryResult', {})
    params = query_result.get('parameters', {})
    
    raw_location = params.get('location')
    
    # 處理地點參數解析
    query_city = ""
    if isinstance(raw_location, dict):
        query_city = raw_location.get('city') or raw_location.get('subadmin-area') or raw_location.get('admin-area')
    elif isinstance(raw_location, list) and len(raw_location) > 0:
        query_city = raw_location[0]
    else:
        query_city = str(raw_location)

    if not query_city or query_city == "None" or query_city == "":
        return jsonify({"fulfillmentText": "請問您想查詢哪個城市的天氣？"})

    # 執行查詢
    reply_text = get_weather_info(query_city)
    return jsonify({"fulfillmentText": reply_text})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)