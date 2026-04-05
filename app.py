import os
import requests
from flask import Flask, request, jsonify
from datetime import datetime, timedelta, timezone

app = Flask(__name__)
API_KEY = os.environ.get("WEATHER_API_KEY")

def force_tr(text):
    """更全面的強制繁體轉換表"""
    if not text: return ""
    tr_map = {
        "东": "東", "东京": "東京", "阴": "陰", "多云": "多雲", 
        "阵雨": "陣雨", "镇": "區", "县": "縣", "国": "國",
        "华": "華", "龙": "龍", "湾": "灣", "义": "義",
        "台": "台", "台北": "台北", "台南": "台南", "台中": "台中",
        "台東": "台東", "层": "層", "雾": "霧", "雷": "雷",
        "实": "實", "气": "氣", "观": "觀", "测": "測"
    }
    for s, t in tr_map.items():
        text = text.replace(s, t)
    return text

def get_aqi_info(lat, lon):
    try:
        url = f"http://api.openweathermap.org/data/2.5/air_pollution?lat={lat}&lon={lon}&appid={API_KEY}"
        res = requests.get(url, timeout=2).json()
        pm25 = res['list'][0]['components'].get('pm2_5', 0)
        
        # 依照台灣環境部 PM2.5 分級
        if pm25 <= 15.4: return "良好"
        elif pm25 <= 35.4: return "普通"
        elif pm25 <= 54.4: return "對敏感族群不健康"
        else: return "不健康"
    except:
        return "數據獲取中"

def get_weather_info(city, is_today=True):
    if not API_KEY: return "⚠️ 請設定 API KEY"

    # 1. 地名清洗 (避免搜尋時帶有行政單位)
    clean_city = str(city).replace("臺", "台").replace("市", "").replace("縣", "").replace("區", "").strip()
    search_query = f"{clean_city},TW" if not any(c.isalpha() for c in clean_city) else clean_city

    try:
        # 2. 地點轉換
        geo_url = f"http://api.openweathermap.org/geo/1.0/direct?q={search_query}&limit=1&appid={API_KEY}"
        geo_res = requests.get(geo_url, timeout=3).json()
        if not geo_res: return f"❓ 找不到「{city}」的地點資訊"

        data = geo_res[0]
        lat, lon = data['lat'], data['lon']
        country = data.get('country', '??')
        
        # 優先抓取繁體中文名，並強制轉換簡轉繁
        loc_name = data.get('local_names', {}).get('zh', data['name'])
        loc_name = force_tr(loc_name)

        # 3. 天氣數據
        w_url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={API_KEY}&units=metric&lang=zh_tw"
        w_data = requests.get(w_url, timeout=3).json()
        
        temp = w_data.get('main', {}).get('temp', "--")
        desc = force_tr(w_data.get('weather', [{}])[0].get('description', "未知"))

        # 4. 建議內容
        suggest = "😊 氣溫舒適，是出門的好天氣。"
        if "雨" in desc: suggest = "☔ 記得帶把傘，注意安全。"
        elif isinstance(temp, (int, float)):
            if temp >= 29: suggest = "🥵 天氣炎熱，請多補充水分。"
            elif temp <= 17: suggest = "🧥 氣溫偏低，記得穿件外套。"

        # 5. 格式組合
        tw_date = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d")
        
        output = (
            f"🌍 氣象服務連線成功！\n"
            f"({tw_date})\n"
            f"--------------------------\n"
            f"📍 地點：{loc_name} [{country}]\n"
            f"🌡️ 溫度：{temp}°C\n"
            f"☁️ 狀態：{desc}\n"
        )
        
        # 判斷是否顯示空氣品質 (非當天不顯示)
        if is_today:
            aqi_val = get_aqi_info(lat, lon)
            output += f"🌬️ 空氣品質：{aqi_val}\n"
            
        output += (
            f"--------------------------\n"
            f"💡 建議：{suggest}\n"
            f"--------------------------"
        )
        return output
    except Exception:
        return "⚠️ 服務連線超時，請稍後再試。"

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        req = request.get_json(silent=True, force=True)
        query_res = req.get('queryResult', {})
        params = query_res.get('parameters', {})
        
        # 處理 Dialogflow 傳來的各種地點格式
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
            city = query_res.get('queryText', '')

        # 檢查日期參數，判定是否為「今天」
        date_param = params.get('date') or params.get('date-time')
        is_today = True if not date_param else False

        reply = get_weather_info(city.replace("天氣", "").strip(), is_today=is_today)
        return jsonify({"fulfillmentText": reply})
    except:
        return jsonify({"fulfillmentText": "系統忙碌中，請重新輸入。"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))