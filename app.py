import os
import requests
from flask import Flask, request, jsonify
from datetime import datetime, timedelta, timezone

app = Flask(__name__)
API_KEY = os.environ.get("WEATHER_API_KEY")

def get_aqi_info(lat, lon):
    """台灣標準 PM2.5 分級"""
    try:
        url = f"http://api.openweathermap.org/data/2.5/air_pollution?lat={lat}&lon={lon}&appid={API_KEY}"
        res = requests.get(url, timeout=2).json()
        pm25 = res['list'][0]['components'].get('pm2_5', 0)
        
        if pm25 <= 15.4: return "良好 ✨"
        elif pm25 <= 35.4: return "普通 ☁️"
        elif pm25 <= 54.4: return "對敏感族群不健康 ⚠️"
        else: return "不健康 😷"
    except:
        return "數據獲取中"

def get_weather_info(city, is_today=True):
    if not API_KEY: return "⚠️ 請設定 API KEY"

    # 1. 地名清洗與繁體校正
    clean_city = str(city).replace("臺", "台").replace("市", "").replace("縣", "").replace("區", "").strip()
    search_query = f"{clean_city},TW" if not any(c.isalpha() for c in clean_city) else clean_city

    try:
        # 2. 座標轉換
        geo_url = f"http://api.openweathermap.org/geo/1.0/direct?q={search_query}&limit=1&appid={API_KEY}"
        geo_res = requests.get(geo_url, timeout=3).json()
        if not geo_res: return f"❓ 找不到「{city}」的地點資訊"

        data = geo_res[0]
        lat, lon = data['lat'], data['lon']
        
        # 3. 抓取天氣
        w_url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={API_KEY}&units=metric&lang=zh_tw"
        w_data = requests.get(w_url, timeout=3).json()
        
        # 地點名稱繁體轉換 (處理簡體回傳)
        location_name = data.get('local_names', {}).get('zh', data['name'])
        location_name = location_name.replace("东", "東").replace("镇", "鎮").replace("区", "區").replace("县", "縣")
        
        temp = w_data.get('main', {}).get('temp', "--")
        desc = w_data.get('weather', [{}])[0].get('description', "未知")
        # 氣象狀態文字繁體化
        desc = desc.replace("多云", "多雲").replace("阴", "陰").replace("阵雨", "陣雨").replace("晴间多云", "晴時多雲")
        
        # 4. 判斷是否顯示空氣品質 (僅限詢問今天)
        aqi_row = ""
        if is_today:
            aqi_val = get_aqi_info(lat, lon)
            aqi_row = f"🌬️ 空氣品質：{aqi_val}\n"

        # 5. 建議邏輯
        suggest = "😊 氣溫舒適，是出門的好天氣。"
        if "雨" in desc: suggest = "☔ 記得帶把傘，注意安全。"
        elif isinstance(temp, (int, float)):
            if temp >= 30: suggest = "☀️ 天氣炎熱，多喝水小心中暑。"
            elif temp <= 16: suggest = "🧥 氣溫偏低，出門多穿件外套。"

        # 6. 組合格式
        date_str = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d")
        
        output = (
            f"🌍 氣象服務連線成功！\n"
            f"({date_str})\n"
            f"--------------------------\n"
            f"📍 地點：{location_name}\n"
            f"🌡️ 溫度：{temp}°C\n"
            f"☁️ 狀態：{desc}\n"
            f"{aqi_row}"  # 如果非今天，這一行會是空的
            f"--------------------------\n"
            f"💡 建議：{suggest}\n"
            f"--------------------------"
        )
        return output
    except:
        return "⚠️ 伺服器忙碌中，請稍後再試。"

@app.route('/webhook', methods=['POST'])
def webhook():
    req = request.get_json(silent=True, force=True)
    query_res = req.get('queryResult', {})
    params = query_res.get('parameters', {})
    
    # 判斷使用者是否詢問「非當天」的天氣 (透過 Dialogflow 的 date 參數)
    # 通常 Dialogflow 的 sys.date 會回傳日期字串
    date_param = params.get('date', '')
    is_today = True
    if date_param:
        # 如果日期參數存在且不是今天，就設為 False
        today_str = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d")
        # 只取日期部分比較 (排除時間)
        if today_str not in str(date_param):
            is_today = False

    # 地名抓取 (使用上一版強化邏輯)
    loc_val = params.get('location')
    city = ""
    if isinstance(loc_val, list) and loc_val:
        item = loc_val[0]
        city = item.get('subadmin-area') or item.get('city') if isinstance(item, dict) else str(item)
    elif isinstance(loc_val, dict):
        city = loc_val.get('subadmin-area') or loc_val.get('city')
    else:
        city = str(loc_val)

    if not city or city.lower() == "none" or city == "{}":
        city = query_res.get('queryText', '').replace("天氣", "").strip()

    reply = get_weather_info(city, is_today=is_today)
    return jsonify({"fulfillmentText": reply})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))