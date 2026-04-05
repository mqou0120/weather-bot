import os
import requests
from flask import Flask, request, jsonify
from datetime import datetime, timedelta

app = Flask(__name__)

OPENWEATHER_API_KEY = os.environ.get("WEATHER_API_KEY")

def get_weather_info(city, date_str=None):
    print(f"\n>>> [LOG] 進入查詢函式。處理地名: {city}")
    
    if not OPENWEATHER_API_KEY:
        return "⚠️ 伺服器配置錯誤，請檢查環境變數。"

    # 1. 地名標準化與淡水/清水專屬補丁
    clean_city = city.replace("臺", "台").replace("區", "").replace("市", "").replace("縣", "")
    special_cases = {
        "淡水": "Tamsui", "清水": "Qingshui", "羅東": "Luodong", "宜蘭": "Yilan"
    }
    
    search_query = f"{special_cases[clean_city]},TW" if clean_city in special_cases else f"{clean_city},TW"
    print(f">>> [LOG] 最終搜尋關鍵字: {search_query}")

    try:
        # 2. 取得座標
        geo_url = f"http://api.openweathermap.org/geo/1.0/direct?q={search_query}&limit=1&appid={OPENWEATHER_API_KEY}"
        geo_res = requests.get(geo_url).json()
        
        if not geo_res:
            print(f">>> [WARNING] 找不到地點: {search_query}")
            return f"❓ 抱歉，找不到「{city}」的地點資訊。"
            
        lat, lon = geo_res[0]['lat'], geo_res[0]['lon']
        location_name = geo_res[0].get('local_names', {}).get('zh', geo_res[0]['name'])

        # 3. 取得氣象
        weather_url = f"https://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={OPENWEATHER_API_KEY}&units=metric&lang=zh_tw"
        w_data = requests.get(weather_url).json()

        if w_data.get("cod") != "200":
            return "⚠️ 氣象供應商回傳錯誤。"

        current = w_data['list'][0]
        temp = current['main']['temp']
        desc = current['weather'][0]['description'].replace("多云", "多雲").replace("阴", "陰")
        
        # 4. 建議內容與表情 (確保內容一定會噴出來)
        if "雨" in desc:
            suggest_txt = "記得帶傘，別淋濕囉！"
            emoji = "☔"
        elif temp > 28:
            suggest_txt = "天氣炎熱，多補充水分！"
            emoji = "🥤"
        elif temp < 18:
            suggest_txt = "氣溫較低，穿件外套保暖。"
            emoji = "🧥"
        else:
            suggest_txt = "氣溫舒適，出門走走吧！"
            emoji = "✨"

        tw_time = datetime.utcnow() + timedelta(hours=8)
        date_str = tw_time.strftime("%Y-%m-%d")

        # 5. 嚴格格式化 (確保 LINE 顯示不跑版)
        response = (
            f"🌍 氣象服務連線成功！\n"
            f"({date_str})\n"
            f"--------------------------\n"
            f"📍 地點：{location_name}\n"
            f"🌡️ 溫度：{temp}°C\n"
            f"☁️ 狀態：{desc}\n"
            f"--------------------------\n"
            f"💡 建議：{emoji} {suggest_txt}\n"
            f"--------------------------"
        )
        print(">>> [SUCCESS] 已生成回覆內容")
        return response

    except Exception as e:
        print(f">>> [ERROR] 發生崩潰: {str(e)}")
        return "⚠️ 數據解析失敗，請重新輸入城市。"

@app.route('/webhook', methods=['POST'])
def webhook():
    req = request.get_json(silent=True, force=True)
    query_result = req.get('queryResult', {})
    params = query_result.get('parameters', {})
    
    # --- 強化地點抓取邏輯 ---
    # 優先從 location 抓，如果沒有，就抓使用者原始輸入的內容 (queryText)
    raw_loc = params.get('location')
    city = ""
    
    if isinstance(raw_loc, dict):
        city = raw_loc.get('city') or raw_loc.get('admin-area') or raw_loc.get('subadmin-area')
    elif isinstance(raw_loc, list) and len(raw_loc) > 0:
        city = raw_loc[0].get('city') if isinstance(raw_loc[0], dict) else str(raw_loc[0])
    else:
        city = str(raw_loc)

    # 保險：如果解析出來太短或空的，直接拿原始對話文字 (例如使用者只打「淡水」)
    if not city or city.lower() == "none" or len(city) < 2:
        city = query_result.get('queryText', '')

    print(f">>> [DEBUG] Webhook 解析到的城市: {city}")
    
    reply = get_weather_info(city)
    return jsonify({"fulfillmentText": reply})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))