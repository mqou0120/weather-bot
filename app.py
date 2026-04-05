import os
import requests
from flask import Flask, request, jsonify
from datetime import datetime, timedelta, timezone

app = Flask(__name__)
API_KEY = os.environ.get("WEATHER_API_KEY")

def final_fix_text(text):
    if not text: return ""
    mapping = {"板桥": "板橋", "桥": "橋", "东": "東", "东京": "東京", "阴": "陰", "多云": "多雲", "阵雨": "陣雨", "镇": "區", "县": "縣", "国": "國", "华": "華", "湾": "灣", "臺": "台", "區": "區", "街道": "", "，": " "}
    for s, t in mapping.items():
        text = text.replace(s, t)
    return text

def get_aqi_info(lat, lon):
    try:
        url = f"http://api.openweathermap.org/data/2.5/air_pollution?lat={lat}&lon={lon}&appid={API_KEY}"
        res = requests.get(url, timeout=2).json()
        pm25 = res['list'][0]['components'].get('pm2_5', 0)
        return "良好" if pm25 <= 15.4 else "普通" if pm25 <= 35.4 else "對敏感族群不健康"
    except: return "數據獲取中"

def get_weather_info(raw_input_city, target_date_str=None):
    if not API_KEY: return "⚠️ 未偵測到 API 金鑰"
    
    # 1. 徹底清洗地點字串 (移除常見贅字)
    clean_city = raw_input_city.replace("天氣", "").replace("如何", "").replace("？", "").replace("?", "").replace("明天", "").strip()
    if not clean_city: return "❓ 請輸入正確的地點名稱。"

    tw_now = datetime.now(timezone(timedelta(hours=8)))
    today_str = tw_now.strftime("%Y-%m-%d")
    is_query_today = True if (not target_date_str or target_date_str == today_str) else False
    display_date = target_date_str if target_date_str else today_str

    # 針對新北市/板橋的搜尋強化
    is_new_taipei = "新北" in clean_city
    search_query = "New Taipei City,TW" if is_new_taipei else f"{clean_city.replace('臺','台')},TW"

    try:
        # 2. 地點搜尋 (增加 limit 確保能過濾台灣座標)
        geo_url = f"http://api.openweathermap.org/geo/1.0/direct?q={search_query}&limit=5&appid={API_KEY}"
        geo_res = requests.get(geo_url, timeout=5).json()
        if not geo_res: return f"❓ 找不到「{clean_city}」的地點資訊"

        # 3. 台灣座標鎖定
        target = geo_res[0]
        for item in geo_res:
            if (21.8 < item['lat'] < 25.5) and (119.5 < item['lon'] < 122.5):
                target = item
                break
        
        lat, lon = target['lat'], target['lon']
        country = "TW" if (21.8 < lat < 25.5) else target.get('country', '??')
        
        # 4. 名稱強制修正 (解決新北變台北的問題)
        location_name = "新北市" if is_new_taipei else final_fix_text(target.get('local_names', {}).get('zh', target['name']))
        if "板橋" in clean_city: location_name = "板橋區"

        # 5. 抓取數據 (今天 vs 未來)
        if is_query_today:
            w_url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={API_KEY}&units=metric&lang=zh_tw"
            data = requests.get(w_url, timeout=5).json()
            temp, desc = data['main']['temp'], data['weather'][0]['description']
        else:
            f_url = f"https://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={API_KEY}&units=metric&lang=zh_tw"
            f_data = requests.get(f_url, timeout=5).json()
            target_entry = f_data['list'][0]
            for entry in f_data['list']:
                if display_date in entry['dt_txt']:
                    target_entry = entry
                    if "12:00:00" in entry['dt_txt']: break
            temp, desc = target_entry['main']['temp'], target_entry['weather'][0]['description']

        # 6. 回傳組合
        res = f"🌍 氣象服務連線成功！\n({display_date})\n--------------------------\n📍 地點：{location_name} [{country}]\n🌡️ 溫度：{temp}°C\n☁️ 狀態：{final_fix_text(desc)}\n"
        if is_query_today:
            res += f"🌬️ 空氣品質：{get_aqi_info(lat, lon)}\n"
        res += "--------------------------\n💡 建議：😊 氣溫舒適，是出門的好天氣。\n--------------------------"
        return res
    except: return "⚠️ 獲取氣象數據失敗，請稍後再試。"

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        req = request.get_json(silent=True, force=True)
        query_res = req.get('queryResult', {})
        params = query_res.get('parameters', {})
        
        # 1. 抓日期
        raw_date = params.get('date', '')
        target_date = raw_date.split('T')[0] if (raw_date and 'T' in str(raw_date)) else None

        # 2. 萬能地點提取 (確保不崩潰)
        loc = params.get('location', '')
        city = ""
        if isinstance(loc, dict):
            city = loc.get('city') or loc.get('subadmin-area') or loc.get('admin-area')
        elif isinstance(loc, list) and len(loc) > 0:
            item = loc[0]
            city = item.get('subadmin-area') if isinstance(item, dict) else str(item)
        else:
            city = str(loc)

        # 如果 Parameters 還是空的，拿使用者的話來當地點
        if not city or "None" in str(city) or "{}" in str(city):
            city = query_res.get('queryText', '')

        reply = get_weather_info(city, target_date_str=target_date)
        return jsonify({"fulfillmentText": reply})
    except:
        return jsonify({"fulfillmentText": "⚠️ 數據解析失敗。"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))