import os
import requests
from flask import Flask, request, jsonify
from datetime import datetime, timedelta, timezone

app = Flask(__name__)
API_KEY = os.environ.get("WEATHER_API_KEY")

def final_fix_text(text):
    if not text: return ""
    # 修正簡體與統一台字
    mapping = {"板桥": "板橋", "桥": "橋", "东": "東", "东京": "東京", "阴": "陰", "多云": "多雲", "阵雨": "陣雨", "臺": "台", "镇": "區", "县": "縣"}
    for s, t in mapping.items():
        text = text.replace(s, t)
    return text

def get_aqi_info(lat, lon):
    try:
        url = f"http://api.openweathermap.org/data/2.5/air_pollution?lat={lat}&lon={lon}&appid={API_KEY}"
        res = requests.get(url, timeout=3).json()
        pm25 = res['list'][0]['components'].get('pm2_5', 0)
        return "良好" if pm25 <= 15.4 else "普通" if pm25 <= 35.4 else "對敏感族群不健康"
    except: return "數據獲取中"

def get_weather_info(city_input, target_date_str=None):
    if not API_KEY: return "⚠️ 未偵測到 API 金鑰"
    
    # 1. 取得今天日期
    tw_now = datetime.now(timezone(timedelta(hours=8)))
    today_str = tw_now.strftime("%Y-%m-%d")
    is_query_today = True if (not target_date_str or target_date_str == today_str) else False
    display_date = target_date_str if target_date_str else today_str

    # 2. 搜尋地點 (不清洗，直接丟進去查)
    # 針對新北/板橋做特殊前綴優化
    search_q = f"{city_input},TW" if "新北" in city_input or "板橋" in city_input else city_input
    
    try:
        geo_url = f"http://api.openweathermap.org/geo/1.0/direct?q={search_q}&limit=1&appid={API_KEY}"
        geo_res = requests.get(geo_url, timeout=5).json()
        
        if not geo_res:
            return f"❓ 找不到「{city_input}」的地點資訊"

        target = geo_res[0]
        lat, lon = target['lat'], target['lon']
        
        # 3. 強制名稱導正
        location_name = final_fix_text(target.get('local_names', {}).get('zh', target['name']))
        if "新北" in city_input: location_name = "新北市"
        elif "板橋" in city_input: location_name = "板橋區"

        # 4. 抓取天氣
        if is_query_today:
            # 今天：使用 Weather API
            w_url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={API_KEY}&units=metric&lang=zh_tw"
            w_data = requests.get(w_url, timeout=5).json()
            temp = w_data['main']['temp']
            desc = final_fix_text(w_data['weather'][0]['description'])
        else:
            # 未來：使用 Forecast API
            f_url = f"https://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={API_KEY}&units=metric&lang=zh_tw"
            f_data = requests.get(f_url, timeout=5).json()
            # 尋找最接近明天的預報
            target_entry = f_data['list'][0]
            for entry in f_data['list']:
                if display_date in entry['dt_txt']:
                    target_entry = entry
                    if "12:00:00" in entry['dt_txt']: break
            temp = target_entry['main']['temp']
            desc = final_fix_text(target_entry['weather'][0]['description'])

        # 5. 組合訊息
        res = f"🌍 氣象服務連線成功！\n({display_date})\n--------------------------\n📍 地點：{location_name} [TW]\n🌡️ 溫度：{temp}°C\n☁️ 狀態：{desc}\n"
        
        if is_query_today:
            res += f"🌬️ 空氣品質：{get_aqi_info(lat, lon)}\n"
            
        res += "--------------------------\n💡 建議：😊 祝您有美好的一天！\n--------------------------"
        return res
    except Exception as e:
        return f"⚠️ 服務異常，請稍後再試。"

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        req = request.get_json(silent=True, force=True)
        query_res = req.get('queryResult', {})
        params = query_res.get('parameters', {})
        
        # 抓取日期
        date_raw = params.get('date', '')
        target_date = date_raw.split('T')[0] if date_raw else None

        # 抓取地點 (核心修正：若 Parameter 抓到的是垃圾，直接用 QueryText)
        city = ""
        loc_param = params.get('location')
        if isinstance(loc_param, dict):
            city = loc_param.get('subadmin-area') or loc_param.get('city') or loc_param.get('admin-area')
        elif isinstance(loc_param, str) and loc_param.strip():
            city = loc_param
            
        # 最終保險：如果 city 太長或抓不到，直接拿使用者的整句話 (過濾掉如何、天氣等詞)
        if not city or len(str(city)) > 10:
            city = query_res.get('queryText', '').replace("如何","").replace("？","").replace("天氣","").replace("明天","").strip()

        reply = get_weather_info(city, target_date_str=target_date)
        return jsonify({"fulfillmentText": reply})
    except:
        return jsonify({"fulfillmentText": "⚠️ 數據處理失敗。"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))