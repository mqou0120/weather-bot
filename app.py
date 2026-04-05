import os
import requests
from flask import Flask, request, jsonify
from datetime import datetime, timedelta

app = Flask(__name__)

OPENWEATHER_API_KEY = os.environ.get("WEATHER_API_KEY")

def get_weather_info(city, date_str=None):
    if not OPENWEATHER_API_KEY:
        return "⚠️ 伺服器配置錯誤，請檢查環境變數。"

    try:
        # --- 修正 1：時區校正 (強制加 8 小時得到台灣時間) ---
        # 這樣就不會因為伺服器在國外而日期顯示昨天
        tw_time = datetime.utcnow() + timedelta(hours=8)
        today_date = tw_time.strftime("%Y-%m-%d")

        # --- 修正 2：地點鎖定與繁體補強 ---
        # 如果使用者輸入板橋、台北等中文，強制加上 ,TW
        search_query = city
        if not any(c.isalpha() for c in city):
            search_query = f"{city},TW"

        geo_url = f"http://api.openweathermap.org/geo/1.0/direct?q={search_query}&limit=1&appid={OPENWEATHER_API_KEY}"
        geo_res = requests.get(geo_url).json()
        
        if not geo_res:
            return f"❓ 找不到「{city}」的地點資訊。"
            
        lat = geo_res[0]['lat']
        lon = geo_res[0]['lon']
        
        # 抓取繁體中文名稱並過濾簡體
        local_names = geo_res[0].get('local_names', {})
        location_name = local_names.get('zh-tw') or local_names.get('zh') or geo_res[0]['name']
        location_name = location_name.replace("多云", "多雲").replace("阴", "陰")
        
        country = geo_res[0].get('country', '')

        # --- 修正 3：氣象數據與繁體中文強轉 ---
        weather_url = f"https://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={OPENWEATHER_API_KEY}&units=metric&lang=zh_tw"
        w_data = requests.get(weather_url).json()

        current = w_data['list'][0]
        temp = current['main']['temp']
        desc = current['weather'][0]['description']
        
        # 針對回傳字串做最後的繁體補丁
        desc = desc.replace("多云", "多雲").replace("阴", "陰").replace("阵雨", "陣雨").replace("晴", "晴朗")
        
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

        return (
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

    except Exception as e:
        return "⚠️ 數據解析失敗，請確認 API 配置。"

@app.route('/webhook', methods=['POST'])
def webhook():
    # (此部分維持之前的解析邏輯)
    req = request.get_json(silent=True, force=True)
    params = req.get('queryResult', {}).get('parameters', {})
    raw_location = params.get('location')
    
    query_city = ""
    if isinstance(raw_location, dict):
        query_city = raw_location.get('city') or raw_location.get('admin-area')
    elif isinstance(raw_location, list) and len(raw_location) > 0:
        item = raw_location[0]
        query_city = item.get('city') if isinstance(item, dict) else str(item)
    else:
        query_city = str(raw_location)

    if not query_city or query_city.lower() == "none":
        return jsonify({"fulfillmentText": "請問您想查詢哪個城市？"})

    return jsonify({"fulfillmentText": get_weather_info(query_city)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))