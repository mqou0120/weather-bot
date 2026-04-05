import os
import requests
from flask import Flask, request, jsonify
from datetime import datetime

app = Flask(__name__)

# 從環境變數讀取 OpenWeather API Key
OPENWEATHER_API_KEY = os.environ.get("WEATHER_API_KEY")

def get_weather_info(city, date_str=None):
    if not OPENWEATHER_API_KEY:
        return "⚠️ 伺服器配置錯誤，請檢查環境變數。"

    try:
        # 1. 取得地理座標 (Geocoding)
        # 邏輯：如果輸入不含英文，自動補上 ,TW 鎖定台灣，避免跑去日本或阿根廷
        search_query = city
        if not any(c.isalpha() for c in city): 
            search_query = f"{city},TW"

        geo_url = f"http://api.openweathermap.org/geo/1.0/direct?q={search_query}&limit=1&appid={OPENWEATHER_API_KEY}"
        geo_res = requests.get(geo_url).json()
        
        if not geo_res:
            return f"❓ 找不到「{city}」的地點資訊。"
            
        lat = geo_res[0]['lat']
        lon = geo_res[0]['lon']
        country = geo_res[0].get('country', '')
        
        # 繁體中文優化：優先抓取本地化名稱
        local_names = geo_res[0].get('local_names', {})
        location_name = local_names.get('zh-tw') or local_names.get('zh') or geo_res[0]['name']
        
        # 2. 取得氣象數據 (使用 5 day / 3 hour forecast)
        weather_url = f"https://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={OPENWEATHER_API_KEY}&units=metric&lang=zh_tw"
        w_data = requests.get(weather_url).json()

        # 抓取第一筆預報資料
        current = w_data['list'][0]
        temp = current['main']['temp']
        desc = current['weather'][0]['description']
        
        # 強制修正部分 API 回傳的簡體字補丁
        desc = desc.replace("多云", "多雲").replace("阴", "陰").replace("阵雨", "陣雨").replace("晴", "晴朗")
        
        # 取得今天日期
        today_date = datetime.now().strftime("%Y-%m-%d")
        
        # 3. 根據天氣給予建議與對應表情
        suggestion = "天氣不錯，出門走走吧！"
        suggest_emoji = "☀️"
        if "雨" in desc:
            suggestion = "記得帶把傘，別淋濕囉！"
            suggest_emoji = "☔"
        elif temp < 15:
            suggestion = "天氣寒冷，穿上厚大衣保暖喔！"
            suggest_emoji = "🥶"
        elif temp < 20:
            suggestion = "有些涼意，加件薄外套吧！"
            suggest_emoji = "🧥"

        # --- 依照要求格式進行排版 ---
        response = (
            f"🌍 氣象服務連線成功！\n"
            f"({today_date})\n"
            f"--------------------------\n"
            f"📍 地點：{location_name} [{country}]\n"
            f"🌡️ 溫度：{temp}°C\n"
            f"☁️ 狀態：{desc}\n"
            f"--------------------------\n"
            f"💡 建議：{suggest_emoji} {suggestion}\n"
            f"--------------------------"
        )
        return response

    except Exception as e:
        print(f"Runtime Error: {e}")
        return "⚠️ 氣象數據抓取失敗，請稍後再試。"

@app.route('/')
def index():
    return "Weather Bot is Online and Secure!"

@app.route('/webhook', methods=['POST'])
def webhook():
    req = request.get_json(silent=True, force=True)
    query_result = req.get('queryResult', {})
    params = query_result.get('parameters', {})
    
    # --- 深度解析地點參數 (解決只講地名沒反應的問題) ---
    raw_location = params.get('location')
    query_city = ""
    
    if isinstance(raw_location, dict):
        query_city = raw_location.get('city') or raw_location.get('admin-area') or raw_location.get('subadmin-area')
    elif isinstance(raw_location, list) and len(raw_location) > 0:
        item = raw_location[0]
        if isinstance(item, dict):
            query_city = item.get('city') or item.get('admin-area')
        else:
            query_city = str(item)
    else:
        query_city = str(raw_location)

    # 清理字串
    query_city = query_city.strip()
    if not query_city or query_city.lower() == "none" or query_city == "":
        return jsonify({"fulfillmentText": "請問您想查詢哪個城市的天氣？"})

    # 執行查詢
    reply_text = get_weather_info(query_city)
    
    return jsonify({
        "fulfillmentText": reply_text
    })

if __name__ == '__main__':
    # Render 環境會自動分配 PORT
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)