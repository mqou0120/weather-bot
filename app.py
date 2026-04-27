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
    advice_list = []
    if "雨" in desc:
        advice_list.append("☔ 記得帶把傘出門，路面濕滑請注意安全。")
    elif "雲" in desc or "陰" in desc:
        advice_list.append("☁️ 天氣較陰沉，建議帶件輕便外套。")
    elif "晴" in desc:
        advice_list.append("☀️ 陽光露臉，別忘了防曬。")
    
    try:
        t = float(temp)
        if t >= 30: advice_list.append("🥵 氣溫炎熱，請多補水。")
        elif t <= 16: advice_list.append("🧣 氣溫偏低，請做好保暖。")
        else: advice_list.append("😊 氣溫適中，祝你有個好心情！")
    except:
        pass
    return " ".join(advice_list[:2])

def get_weather_info(city_name, target_date_str=None):
    if not API_KEY: return "⚠️ 未偵測到 API 金鑰"
    
    # 1. 清理城市名稱，移除贅字並強制加上台灣代碼
    search_query = city_name.replace("區", "").replace("市", "").replace("天氣", "").strip()
    if not search_query: return "❓ 請問您想查詢哪個地區的天氣？"

    tw_now = datetime.now(timezone(timedelta(hours=8)))
    today_str = tw_now.strftime("%Y-%m-%d")
    is_query_today = True if (not target_date_str or target_date_str == today_str) else False
    display_date = target_date_str if target_date_str else today_str

    try:
        # 2. 地理編碼搜尋：強制加上 ,TW 限制在台灣
        geo_url = f"http://api.openweathermap.org/geo/1.0/direct?q={search_query},TW&limit=5&appid={API_KEY}"
        geo_res = requests.get(geo_url, timeout=5).json()
        
        if not geo_res:
            return f"❓ 找不到「{city_name}」在台灣的地點資訊。"

        # 3. 嚴格經緯度過濾 (確保在台灣範圍內)
        target = None
        for item in geo_res:
            lat, lon = item['lat'], item['lon']
            if (21.8 < lat < 25.5) and (119.5 < lon < 122.5):
                target = item
                break
        
        if not target: target = geo_res[0] # 若無過濾結果則取第一個

        lat, lon = target['lat'], target['lon']
        location_name = final_fix_text(target.get('local_names', {}).get('zh', target['name']))

        # 4. 抓取天氣數據
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

        smart_advice = get_smart_advice(temp, desc)
        res = f"🌍 氣象服務連線成功！\n({display_date})\n--------------------------\n📍 地點：{location_name}\n🌡️ 溫度：{temp}°C\n☁️ 狀態：{final_fix_text(desc)}\n"
        
        if is_query_today:
            aqi_url = f"http://api.openweathermap.org/data/2.5/air_pollution?lat={lat}&lon={lon}&appid={API_KEY}"
            aqi_data = requests.get(aqi_url, timeout=3).json()
            pm25 = aqi_data['list'][0]['components'].get('pm2_5', 0)
            aqi_str = "良好" if pm25 <= 15.4 else "普通" if pm25 <= 35.4 else "對敏感族群不健康"
            res += f"🌬️ 空氣品質：{aqi_str}\n"
            
        res += f"--------------------------\n💡 建議：{smart_advice}\n--------------------------"
        return res
    except Exception as e:
        return f"⚠️ 獲取數據失敗，請稍後再試。"

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        req = request.get_json(silent=True, force=True)
        query_res = req.get('queryResult', {})
        params = query_res.get('parameters', {})
        
        # 解析日期
        date_input = params.get('date-time') or params.get('date') or ""
        target_date = str(date_input).split('T')[0] if date_input else None

        # 優先從 Dialogflow Location 參數提取
        city = ""
        loc_param = params.get('location')
        if isinstance(loc_param, list) and len(loc_param) > 0:
            loc_data = loc_param[0]
            if isinstance(loc_data, dict):
                city = loc_data.get('city') or loc_data.get('subadmin-area') or loc_data.get('admin-area') or ""
            else:
                city = str(loc_data)
        
        # 如果參數沒抓到，改從原始對話內容解析
        if not city:
            city = query_res.get('queryText', '')

        reply = get_weather_info(city, target_date_str=target_date)
        return jsonify({"fulfillmentText": reply})
    except:
        return jsonify({"fulfillmentText": "⚠️ 拍謝，我暫時沒辦法解析這個地點。"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))