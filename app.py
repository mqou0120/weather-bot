import os
import requests
from flask import Flask, request, jsonify
from datetime import datetime, timedelta, timezone

app = Flask(__name__)
API_KEY = os.environ.get("WEATHER_API_KEY")

def force_traditional(text):
    """徹底轉換簡體字、大陸用語及統一台字"""
    if not text: return ""
    mapping = {
        "板桥": "板橋", "东京": "東京", "东": "東", "桥": "橋",
        "阴": "陰", "多云": "多雲", "阵雨": "陣雨", "镇": "區", 
        "县": "縣", "国": "國", "华": "華", "湾": "灣", 
        "臺": "台", "层": "層", "雾": "霧", "雷": "雷",
        "实": "實", "气": "氣", "观": "觀", "测": "測",
        "区": "區", "广": "廣", "街道": "", "，": " ", 
        "晴间多云": "晴時多雲"
    }
    for s, t in mapping.items():
        text = text.replace(s, t)
    return text

def get_aqi_info(lat, lon):
    try:
        url = f"http://api.openweathermap.org/data/2.5/air_pollution?lat={lat}&lon={lon}&appid={API_KEY}"
        res = requests.get(url, timeout=2).json()
        pm25 = res['list'][0]['components'].get('pm2_5', 0)
        if pm25 <= 15.4: return "良好"
        elif pm25 <= 35.4: return "普通"
        elif pm25 <= 54.4: return "對敏感族群不健康"
        else: return "不健康"
    except:
        return "數據獲取中"

def get_weather_info(user_input, is_today=True):
    if not API_KEY: return "⚠️ 未偵測到 API KEY"

    raw_input = str(user_input).strip()
    
    # --- 核心修正：新北市專屬座標鎖定 ---
    # 如果使用者輸入包含「新北」，直接跳過搜尋，使用新北市政府座標
    if "新北" in raw_input:
        lat, lon = 25.012, 121.465  # 新北市政府精準座標
        location_name = "新北市"
        country = "TW"
    else:
        # 一般搜尋邏輯
        clean_city = raw_input.replace("臺", "台").replace("市", "").replace("縣", "").replace("區", "").strip()
        search_query = f"{clean_city},TW"
        
        try:
            geo_url = f"http://api.openweathermap.org/geo/1.0/direct?q={search_query}&limit=5&appid={API_KEY}"
            geo_res = requests.get(geo_url, timeout=3).json()
            if not geo_res: return f"❓ 找不到「{user_input}」"

            # 挑選在台灣範圍內的結果
            target = geo_res[0]
            for item in geo_res:
                if (21.8 < item['lat'] < 25.5) and (119.5 < item['lon'] < 122.5):
                    target = item
                    break
            
            lat, lon = target['lat'], target['lon']
            country = "TW" if (21.8 < lat < 25.5) and (119.5 < lon < 122.5) else target.get('country', '??')
            location_name = force_traditional(target.get('local_names', {}).get('zh', target['name']))
            
            # 二次校正：避免搜尋板橋回傳 CN
            if "板橋" in raw_input: location_name = "板橋區"

        except:
            return "⚠️ 地點搜尋失敗"

    try:
        # 抓取天氣數據
        w_url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={API_KEY}&units=metric&lang=zh_tw"
        w_data = requests.get(w_url, timeout=3).json()
        
        temp = w_data.get('main', {}).get('temp', "--")
        desc = force_traditional(w_data.get('weather', [{}])[0].get('description', "未知"))

        suggest = "😊 氣溫舒適，是出門的好天氣。"
        if "雨" in desc: suggest = "☔ 記得帶把傘，注意安全。"
        elif isinstance(temp, (int, float)):
            if temp >= 28: suggest = "🥵 天氣炎熱，請多補充水分。"
            elif temp <= 18: suggest = "🧥 氣溫偏低，記得穿件外套。"

        date_str = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d")
        
        res = (
            f"🌍 氣象服務連線成功！\n"
            f"({date_str})\n"
            f"--------------------------\n"
            f"📍 地點：{location_name} [{country}]\n"
            f"🌡️ 溫度：{temp}°C\n"
            f"☁️ 狀態：{desc}\n"
        )
        if is_today:
            res += f"🌬️ 空氣品質：{get_aqi_info(lat, lon)}\n"
        res += f"--------------------------\n💡 建議：{suggest}\n--------------------------"
        return res
    except:
        return "⚠️ 天氣數據抓取失敗"

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        req = request.get_json(silent=True, force=True)
        query_res = req.get('queryResult', {})
        params = query_res.get('parameters', {})
        
        # 日期判斷
        is_today = True
        date_param = params.get('date', '')
        if date_param:
            today = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d")
            if today not in str(date_param): is_today = False

        # 地名獲取
        loc_val = params.get('location', "")
        if isinstance(loc_val, list) and loc_val:
            city = loc_val[0].get('subadmin-area') or loc_val[0].get('city') if isinstance(loc_val[0], dict) else str(loc_val[0])
        elif isinstance(loc_val, dict):
            city = loc_val.get('subadmin-area') or loc_val.get('city')
        else:
            city = str(loc_val)

        if not city or city.lower() == "none" or "{}" in city:
            city = query_res.get('queryText', '')

        return jsonify({"fulfillmentText": get_weather_info(city.replace("天氣", ""), is_today)})
    except:
        return jsonify({"fulfillmentText": "系統錯誤"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))