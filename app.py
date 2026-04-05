import os
import requests
from flask import Flask, request, jsonify
from datetime import datetime, timedelta, timezone

app = Flask(__name__)
API_KEY = os.environ.get("WEATHER_API_KEY")

def final_fix_text(text):
    if not text: return ""
    mapping = {"板桥": "板橋", "桥": "橋", "东": "東", "东京": "東京", "阴": "陰", "多云": "多雲", "阵雨": "陣雨", "臺": "台", "街道": ""}
    for s, t in mapping.items():
        text = text.replace(s, t)
    return text

def get_smart_advice(temp, desc):
    """根據溫度與天氣狀態提供自動化建議"""
    advice_list = []
    
    # 1. 針對天氣狀態的建議
    if "雨" in desc:
        advice_list.append("☔ 記得帶把傘出門，路面濕滑請注意安全。")
    elif "雲" in desc or "陰" in desc:
        advice_list.append("☁️ 天氣較陰沉，雖然不一定下雨但建議帶件輕便外套。")
    elif "晴" in desc:
        advice_list.append("☀️ 陽光露臉，出門別忘了防曬或戴太陽眼鏡。")
    elif "霧" in desc:
        advice_list.append("🌫️ 濃霧能見度低，開車請慢行並開啟霧燈。")

    # 2. 針對溫度的建議
    try:
        t = float(temp)
        if t >= 30:
            advice_list.append("🥵 天氣炎熱，請多補充水分以防中暑。")
        elif t <= 16:
            advice_list.append("🧣 氣溫偏低，出門請做好保暖禦寒。")
        elif 17 <= t <= 24:
            advice_list.append("👕 涼爽舒適，適合穿長袖薄外套。")
        else:
            advice_list.append("😊 氣溫適中，是個適合出遊的好日子！")
    except:
        advice_list.append("😊 祝您今天有個好心情！")

    # 隨機挑選或組合 (這裡取兩條建議組合)
    return " ".join(advice_list[:2])

def get_weather_info(city_name, target_date_str=None):
    if not API_KEY: return "⚠️ 未偵測到 API 金鑰"
    
    tw_now = datetime.now(timezone(timedelta(hours=8)))
    today_str = tw_now.strftime("%Y-%m-%d")
    is_query_today = True if (not target_date_str or target_date_str == today_str) else False
    display_date = target_date_str if target_date_str else today_str

    try:
        # 搜尋地點
        geo_url = f"http://api.openweathermap.org/geo/1.0/direct?q={city_name}&limit=5&appid={API_KEY}"
        geo_res = requests.get(geo_url, timeout=5).json()
        
        if not geo_res and any(x in city_name for x in ["板橋", "新北", "台北", "台中", "台南", "高雄"]):
            geo_url = f"http://api.openweathermap.org/geo/1.0/direct?q={city_name},TW&limit=1&appid={API_KEY}"
            geo_res = requests.get(geo_url, timeout=5).json()

        if not geo_res: return f"❓ 找不到「{city_name}」的地點資訊"

        target = geo_res[0]
        for item in geo_res:
            if (21.8 < item['lat'] < 25.5) and (119.5 < item['lon'] < 122.5):
                target = item
                break
        
        lat, lon = target['lat'], target['lon']
        location_name = final_fix_text(target.get('local_names', {}).get('zh', target['name']))
        if "新北" in city_name: location_name = "新北市"
        elif "板橋" in city_name: location_name = "板橋區"

        # 抓取天氣
        if is_query_today:
            url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={API_KEY}&units=metric&lang=zh_tw"
            data = requests.get(url, timeout=5).json()
            temp = data['main']['temp']
            desc = data['weather'][0]['description']
        else:
            url = f"https://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={API_KEY}&units=metric&lang=zh_tw"
            data = requests.get(url, timeout=5).json()
            target_entry = data['list'][0]
            for entry in data['list']:
                if display_date in entry['dt_txt']:
                    target_entry = entry
                    if "12:00:00" in entry['dt_txt']: break
            temp = target_entry['main']['temp']
            desc = target_entry['weather'][0]['description']

        # 獲取自動化建議
        smart_advice = get_smart_advice(temp, desc)

        res = f"🌍 氣象服務連線成功！\n({display_date})\n--------------------------\n📍 地點：{location_name} [{target.get('country','??')}]\n🌡️ 溫度：{temp}°C\n☁️ 狀態：{final_fix_text(desc)}\n"
        
        if is_query_today:
            aqi_url = f"http://api.openweathermap.org/data/2.5/air_pollution?lat={lat}&lon={lon}&appid={API_KEY}"
            aqi_data = requests.get(aqi_url, timeout=3).json()
            pm25 = aqi_data['list'][0]['components'].get('pm2_5', 0)
            aqi_str = "良好" if pm25 <= 15.4 else "普通" if pm25 <= 35.4 else "對敏感族群不健康"
            res += f"🌬️ 空氣品質：{aqi_str}\n"
            
        res += f"--------------------------\n💡 建議：{smart_advice}\n--------------------------"
        return res
    except:
        return "⚠️ 獲取氣象數據失敗。"

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        req = request.get_json(silent=True, force=True)
        query_res = req.get('queryResult', {})
        params = query_res.get('parameters', {})
        
        date_list = params.get('date-time') or params.get('date') or []
        target_date = None
        if isinstance(date_list, list) and len(date_list) > 0:
            target_date = str(date_list[0]).split('T')[0]
        elif isinstance(date_list, str):
            target_date = date_list.split('T')[0]

        city = ""
        loc_list = params.get('location', [])
        if isinstance(loc_list, list) and len(loc_list) > 0:
            item = loc_list[0]
            city = item.get('city') or item.get('subadmin-area') or item.get('admin-area') if isinstance(item, dict) else str(item)
        
        if not city or "None" in str(city):
            city = query_res.get('queryText', '').replace("明天","").replace("天氣","").replace("如何","").replace("？","").strip()

        reply = get_weather_info(city, target_date_str=target_date)
        return jsonify({"fulfillmentText": reply})
    except:
        return jsonify({"fulfillmentText": "⚠️ 解析失敗。"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))