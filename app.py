import os
import requests
from flask import Flask, request, jsonify
from datetime import datetime, timedelta

app = Flask(__name__)

# 請確保 Render 的 Environment Variables 有設定 WEATHER_API_KEY
OPENWEATHER_API_KEY = os.environ.get("WEATHER_API_KEY")

def get_weather_info(city):
    # --- 1. 極致地名標準化 ---
    # 先把贅字和常見異體字清乾淨
    clean_city = city.replace("臺", "台").replace("市", "").replace("縣", "").replace("區", "").replace("鄉", "").replace("鎮", "").strip()
    
    # 針對 API 較難識別的地點進行翻譯補丁
    special_cases = {
        "淡水": "Tamsui", "清水": "Qingshui", "羅東": "Luodong", "宜蘭": "Yilan",
        "板橋": "Banqiao", "東京": "Tokyo", "倫敦": "London"
    }
    
    # 決定搜尋用的關鍵字 (如果是中文就鎖定台灣 ,TW)
    if clean_city in special_cases:
        search_query = f"{special_cases[clean_city]},TW" if clean_city != "東京" and clean_city != "倫敦" else special_cases[clean_city]
    else:
        search_query = f"{clean_city},TW" if not any(c.isalpha() for c in clean_city) else clean_city

    try:
        # --- 2. 地理座標查詢 (Geocoding) ---
        geo_url = f"http://api.openweathermap.org/geo/1.0/direct?q={search_query}&limit=1&appid={OPENWEATHER_API_KEY}"
        geo_res = requests.get(geo_url).json()
        
        if not geo_res:
            # [保險機制] 如果加了標籤找不到，嘗試用原始字串裸測
            geo_url = f"http://api.openweathermap.org/geo/1.0/direct?q={city}&limit=1&appid={OPENWEATHER_API_KEY}"
            geo_res = requests.get(geo_url).json()
            if not geo_res:
                return f"❓ 抱歉，找不到「{city}」的地點資訊。"

        lat = geo_res[0]['lat']
        lon = geo_res[0]['lon']
        # 取得繁體名稱
        location_name = geo_res[0].get('local_names', {}).get('zh', geo_res[0]['name'])
        country = geo_res[0].get('country', '')

        # --- 3. 取得氣象預報 ---
        weather_url = f"https://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={OPENWEATHER_API_KEY}&units=metric&lang=zh_tw"
        w_data = requests.get(weather_url).json()

        current = w_data['list'][0]
        temp = current['main']['temp']
        desc = current['weather'][0]['description'].replace("多云", "多雲").replace("阴", "陰")

        # --- 4. 氣溫建議邏輯 (確保建議內容一定會出現) ---
        if "雨" in desc:
            suggest_txt, emoji = "記得帶傘，別淋濕囉！", "☔"
        elif temp >= 28:
            suggest_txt, emoji = "天氣炎熱，多補充水分！", "🥤"
        elif temp <= 18:
            suggest_txt, emoji = "氣溫較低，穿件外套保暖。", "🧥"
        else:
            suggest_txt, emoji = "氣溫舒適，出門走走吧！", "✨"

        # --- 5. 格式化回覆 (修正日期與排版) ---
        tw_time = datetime.utcnow() + timedelta(hours=8)
        date_str = tw_time.strftime("%Y-%m-%d")

        return (
            f"🌍 氣象服務連線成功！\n"
            f"({date_str})\n"
            f"--------------------------\n"
            f"📍 地點：{location_name} [{country}]\n"
            f"🌡️ 溫度：{temp}°C\n"
            f"☁️ 狀態：{desc}\n"
            f"--------------------------\n"
            f"💡 建議：{emoji} {suggest_txt}\n"
            f"--------------------------"
        )
    except Exception as e:
        return "⚠️ 數據服務忙碌中，請稍後再試。"

@app.route('/webhook', methods=['POST'])
def webhook():
    req = request.get_json(silent=True, force=True)
    query_result = req.get('queryResult', {})
    params = query_result.get('parameters', {})
    
    # --- 重要核心：雙軌抓取地名 ---
    # 第一軌：從 Dialogflow 辨識出的實體抓 (參數)
    raw_loc = params.get('location')
    city = ""
    
    if isinstance(raw_loc, dict):
        city = raw_loc.get('city') or raw_loc.get('admin-area') or raw_loc.get('subadmin-area')
    elif isinstance(raw_loc, list) and len(raw_loc) > 0:
        city = raw_loc[0].get('city') if isinstance(raw_loc[0], dict) else str(raw_loc[0])
    else:
        city = str(raw_loc)

    # 第二軌：如果參數抓不到(None)或太短，直接拿使用者的對話文字
    if not city or city.lower() == "none" or len(city) < 1:
        city = query_result.get('queryText', '')

    # 清除多餘的「天氣」等字眼 (如果使用者輸入: 板橋天氣)
    city = city.replace("天氣", "").replace("如何", "").replace("的", "").strip()

    reply = get_weather_info(city)
    return jsonify({"fulfillmentText": reply})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))