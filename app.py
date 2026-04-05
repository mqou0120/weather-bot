import os
import requests
from flask import Flask, request, jsonify
from datetime import datetime, timedelta, timezone

app = Flask(__name__)
API_KEY = os.environ.get("WEATHER_API_KEY")

def final_fix_text(text):
    """徹底轉換簡體字、大陸用語及統一台字"""
    if not text: return ""
    mapping = {
        "板桥": "板橋", "桥": "橋", "东": "東", "东京": "東京",
        "阴": "陰", "多云": "多雲", "阵雨": "陣雨", "镇": "區", 
        "县": "縣", "国": "國", "华": "華", "湾": "灣", 
        "臺": "台", "层": "層", "雾": "霧", "雷": "雷",
        "实": "實", "气": "氣", "区": "區", "广": "廣",
        "街道": "", "，": " ", "晴间多云": "晴時多雲"
    }
    for s, t in mapping.items():
        text = text.replace(s, t)
    return text

def get_aqi_info(lat, lon):
    """台灣環境部 PM2.5 分級標準 (純文字)"""
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

def get_weather_info(user_input_city, is_today=True):
    if not API_KEY: return "⚠️ 未偵測到 API 金鑰"

    display_city = user_input_city.strip()
    search_city = display_city.replace("臺", "台")
    
    # 處理新北市特別邏輯
    is_requesting_new_taipei = "新北" in display_city
    if is_requesting_new_taipei:
        search_query = "New Taipei City,TW"
    else:
        search_query = f"{search_city},TW" if not any(c.isalpha() for c in search_city) else search_city

    try:
        # 1. 地點搜尋
        geo_url = f"http://api.openweathermap.org/geo/1.0/direct?q={search_query}&limit=5&appid={API_KEY}"
        geo_res = requests.get(geo_url, timeout=3).json()
        if not geo_res: return f"❓ 找不到「{user_input_city}」的地點資訊"

        # 2. 篩選台灣座標
        target = geo_res[0]
        is_in_taiwan = False
        for item in geo_res:
            lat, lon = item['lat'], item['lon']
            if (21.8 < lat < 25.5) and (119.5 < lon < 122.5):
                target = item
                is_in_taiwan = True
                break

        lat, lon = target['lat'], target['lon']
        country = "TW" if is_in_taiwan else target.get('country', '??')

        # 3. 強制修正顯示名稱 (解決新北變台北的問題)
        location_name = final_fix_text(target.get('local_names', {}).get('zh', target['name']))
        if is_requesting_new_taipei:
            location_name = "新北市"
        elif "板橋" in display_city:
            location_name = "板橋區"

        # 4. 抓取氣象數據
        w_url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={API_KEY}&units=metric&lang=zh_tw"
        w_res = requests.get(w_url, timeout=3).json()
        temp = w_res.get('main', {}).get('temp', "--")
        desc = final_fix_text(w_res.get('weather', [{}])[0].get('description', "未知"))

        # 5. 建議
        suggest = "😊 氣溫舒適，是出門的好天氣。"
        if "雨" in desc: suggest = "☔ 記得帶把傘，注意安全。"
        elif isinstance(temp, (int, float)):
            if temp >= 28: suggest = "🥵 天氣炎熱，請多補充水分。"
            elif temp <= 18: suggest = "🧥 氣溫偏低，記得穿件外套。"

        # 6. 組合回應格式
        date_str = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d")
        res_text = (
            f"🌍 氣象服務連線成功！\n"
            f"({date_str})\n"
            f"--------------------------\n"
            f"📍 地點：{location_name} [{country}]\n"
            f"🌡️ 溫度：{temp}°C\n"
            f"☁️ 狀態：{desc}\n"
        )
        if is_today:
            aqi_val = get_aqi_info(lat, lon)
            res_text += f"🌬️ 空氣品質：{aqi_val}\n"
        res_text += f"--------------------------\n💡 建議：{suggest}\n--------------------------"
        return res_text
    except:
        return "⚠️ 系統連線異常，請稍後再試。"

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        req = request.get_json(silent=True, force=True)
        query_res = req.get('queryResult', {})
        params = query_res.get('parameters', {})
        
        # 判斷時間
        date_param = params.get('date', '')
        is_today = True
        if date_param:
            today_str = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d")
            if today_str not in str(date_param): is_today = False

        # 抓取地名
        loc_val = params.get('location', "")
        city = ""
        if isinstance(loc_val, list) and loc_val:
            item = loc_val[0]
            city = item.get('subadmin-area') or item.get('city') if isinstance(item, dict) else str(item)
        elif isinstance(loc_val, dict):
            city = loc_val.get('subadmin-area') or loc_val.get('city')
        else:
            city = str(loc_val)

        if not city or str(city).lower() == "none" or city == "{}":
            city = query_res.get('queryText', '')

        reply = get_weather_info(city.replace("天氣", "").strip(), is_today=is_today)
        return jsonify({"fulfillmentText": reply})
    except:
        return jsonify({"fulfillmentText": "數據解析失敗，請稍後再試。"})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)