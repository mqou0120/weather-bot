import os
import requests
from flask import Flask, request, jsonify
from datetime import datetime, timedelta

app = Flask(__name__)

# --- 安全提醒：請確保在 Render 的 Environment Variables 設定 WEATHER_API_KEY ---
# 不要直接把 Key 寫在程式碼字串裡，避免 GitHub 安全警告
OPENWEATHER_API_KEY = os.environ.get("WEATHER_API_KEY")

def get_weather_info(city, date_str=None):
    if not OPENWEATHER_API_KEY:
        return "⚠️ 伺服器配置錯誤，請檢查環境變數 (API KEY)。"

    # --- 1. 地名洗滌邏輯：解決「淡水」、「台南」找不到的問題 ---
    # 統一繁體「臺」為「台」，並移除行政區劃後綴，增加 API 搜尋成功率
    clean_city = city.replace("臺", "台")
    for suffix in ["市", "縣", "區", "鄉", "鎮"]:
        if clean_city.endswith(suffix):
            clean_city = clean_city[:-1]

    try:
        # --- 2. 時區校正：強制轉換為台灣時間 (UTC+8) ---
        tw_time = datetime.utcnow() + timedelta(hours=8)
        today_date = tw_time.strftime("%Y-%m-%d")

        # --- 3. 地理座標抓取 (Geocoding) ---
        # 如果是中文地名，自動加上 ,TW 鎖定台灣區域
        search_query = f"{clean_city},TW" if not any(c.isalpha() for c in clean_city) else clean_city
        
        geo_url = f"http://api.openweathermap.org/geo/1.0/direct?q={search_query}&limit=1&appid={OPENWEATHER_API_KEY}"
        geo_res = requests.get(geo_url).json()
        
        # 如果洗滌後找不到，嘗試用原始名稱再找一次作為保險
        if not geo_res:
            geo_url = f"http://api.openweathermap.org/geo/1.0/direct?q={city}&limit=1&appid={OPENWEATHER_API_KEY}"
            geo_res = requests.get(geo_url).json()
            if not geo_res:
                return f"❓ 抱歉，找不到「{city}」的氣象資料。"
            
        lat = geo_res[0]['lat']
        lon = geo_res[0]['lon']
        
        # 抓取繁體中文名稱標籤
        local_names = geo_res[0].get('local_names', {})
        location_name = local_names.get('zh-tw') or local_names.get('zh') or geo_res[0]['name']
        location_name = location_name.replace("区", "區").replace("县", "縣") # 補丁
        
        country = geo_res[0].get('country', '')

        # --- 4. 氣象預報抓取 ---
        weather_url = f"https://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={OPENWEATHER_API_KEY}&units=metric&lang=zh_tw"
        w_data = requests.get(weather_url).json()

        current = w_data['list'][0]
        temp = current['main']['temp']
        desc = current['weather'][0]['description']
        
        # 狀態字串繁體補丁
        desc = desc.replace("多云", "多雲").replace("阴", "陰").replace("阵雨", "陣雨").replace("晴", "晴朗")
        
        # --- 5. 天氣建議邏輯 ---
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

        # --- 6. 格式化回覆字串 (依照要求排版) ---
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
        return "⚠️ 數據解析發生錯誤，請稍後再試。"

@app.route('/')
def index():
    return "Weather Bot is Online!"

@app.route('/webhook', methods=['POST'])
def webhook():
    req = request.get_json(silent=True, force=True)
    query_result = req.get('queryResult', {})
    params = query_result.get('parameters', {})
    
    # 抓取地點參數
    raw_location = params.get('location')
    query_city = ""
    
    if isinstance(raw_location, dict):
        query_city = raw_location.get('city') or raw_location.get('admin-area') or raw_location.get('subadmin-area')
    elif isinstance(raw_location, list) and len(raw_location) > 0:
        item = raw_location[0]
        query_city = item.get('city') if isinstance(item, dict) else str(item)
    else:
        query_city = str(raw_location)

    query_city = query_city.strip()
    if not query_city or query_city.lower() == "none" or query_city == "":
        return jsonify({"fulfillmentText": "請問您想查詢哪個城市？"})

    # 呼叫氣象函式並回傳
    reply = get_weather_info(query_city)
    return jsonify({"fulfillmentText": reply})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)