import os
import requests
from flask import Flask, request, jsonify
from datetime import datetime, timedelta, timezone

app = Flask(__name__)

API_KEY = os.environ.get("WEATHER_API_KEY")

# 簡單的簡轉繁字典（針對常見天氣關鍵字與地名）
TC_MAP = {
    "多云": "多雲", "阴": "陰", "阵雨": "陣雨", "晴": "晴", "小雨": "小雨",
    "中雨": "中雨", "大雨": "大雨", "雷阵雨": "雷陣雨", "雾": "霧",
    "板桥镇": "板橋區", "东京都": "東京都", "台": "臺"
}

def translate_to_tc(text):
    for k, v in TC_MAP.items():
        text = text.replace(k, v)
    return text

def get_weather_info(city_input):
    if not API_KEY: return "⚠️ 請設定 WEATHER_API_KEY"

    # 清洗輸入
    clean_city = str(city_input).replace("臺", "台").replace("市", "").replace("縣", "").strip()
    search_query = f"{clean_city},TW" if not any(c.isalpha() for c in clean_city) else clean_city

    try:
        # 1. 座標轉換
        geo_url = f"http://api.openweathermap.org/geo/1.0/direct?q={search_query}&limit=1&appid={API_KEY}"
        geo_res = requests.get(geo_url, timeout=3).json()
        
        if not geo_res:
            return f"❓ 找不到「{city_input}」"

        data = geo_res[0]
        lat, lon = data['lat'], data['lon']
        
        # 處理地點名稱並轉繁體，補上 [TW]
        raw_location = data.get('local_names', {}).get('zh', data['name'])
        location_name = translate_to_tc(raw_location)
        if "TW" in search_query or "Taiwan" in search_query:
            location_name += " [TW]"

        # 2. 氣象抓取
        w_url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={API_KEY}&units=metric&lang=zh_tw"
        w_data = requests.get(w_url, timeout=3).json()
        
        temp = w_data.get('main', {}).get('temp', "--")
        desc = translate_to_tc(w_data.get('weather', [{}])[0].get('description', "未知"))
        
        # 3. 建議邏輯
        suggest = "天氣舒適，出門走走吧！ ✨"
        if "雨" in desc:
            suggest = "☔ 記得帶把傘，別淋濕囉！"
        elif isinstance(temp, (int, float)):
            if temp >= 29: suggest = "🥵 天氣炎熱，多補充水分！"
            elif temp <= 17: suggest = "🧣 氣溫偏低，記得穿暖一點。"

        # 4. 時間格式
        tw_date = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d")

        # --- 依照你要求的格式組合字串 ---
        reply = (
            f"🌍 氣象服務連線成功！\n"
            f"({tw_date})\n"
            f"--------------------------\n"
            f"📍 地點：{location_name}\n"
            f"🌡️ 溫度：{temp}°C\n"
            f"☁️ 狀態：{desc}\n"
            f"--------------------------\n"
            f"💡 建議：{suggest}\n"
            f"--------------------------"
        )
        return reply

    except Exception as e:
        return f"⚠️ 系統繁忙，請稍後再試。"

@app.route('/webhook', methods=['POST'])
def webhook():
    req = request.get_json(silent=True, force=True)
    query_res = req.get('queryResult', {})
    params = query_res.get('parameters', {})
    
    # 擷取地名邏輯 (修正列表問題)
    loc_val = params.get('location')
    city = ""
    if isinstance(loc_val, list) and loc_val:
        item = loc_val[0]
        city = item.get('subadmin-area') or item.get('city') if isinstance(item, dict) else str(item)
    elif isinstance(loc_val, dict):
        city = loc_val.get('subadmin-area') or loc_val.get('city')
    else:
        city = str(loc_val)

    if not city or city == "None":
        city = query_res.get('queryText', '')

    final_city = city.replace("天氣", "").strip()
    return jsonify({"fulfillmentText": get_weather_info(final_city)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))