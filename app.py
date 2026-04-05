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

def get_weather_info(city_name, target_date_str=None):
    if not API_KEY: return "⚠️ 未偵測到 API 金鑰"
    
    tw_now = datetime.now(timezone(timedelta(hours=8)))
    today_str = tw_now.strftime("%Y-%m-%d")
    is_query_today = True if (not target_date_str or target_date_str == today_str) else False
    display_date = target_date_str if target_date_str else today_str

    try:
        # 1. 第一輪嘗試：直接搜尋 (支援國外)
        geo_url = f"http://api.openweathermap.org/geo/1.0/direct?q={city_name}&limit=5&appid={API_KEY}"
        geo_res = requests.get(geo_url, timeout=5).json()
        
        # 2. 如果直接搜不到，且包含台灣地名，嘗試加上 TW 鎖定
        if not geo_res and any(x in city_name for x in ["板橋", "新北", "台北", "台中", "台南", "高雄"]):
            geo_url = f"http://api.openweathermap.org/geo/1.0/direct?q={city_name},TW&limit=1&appid={API_KEY}"
            geo_res = requests.get(geo_url, timeout=5).json()

        if not geo_res:
            return f"❓ 找不到「{city_name}」的地點資訊"

        # 3. 台灣優先篩選策略
        target = geo_res[0]
        for item in geo_res:
            # 如果結果中有台灣的座標，優先選擇台灣
            if (21.8 < item['lat'] < 25.5) and (119.5 < item['lon'] < 122.5):
                target = item
                break
        
        lat, lon = target['lat'], target['lon']
        country = target.get('country', '??')
        
        # 4. 名稱修正 (處理新北變台北問題)
        location_name = final_fix_text(target.get('local_names', {}).get('zh', target['name']))
        if "新北" in city_name: location_name = "新北市"
        elif "板橋" in city_name: location_name = "板橋區"

        # 5. 抓取天氣數據
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

        # 6. 組合訊息
        res = f"🌍 氣象服務連線成功！\n({display_date})\n--------------------------\n📍 地點：{location_name} [{country}]\n🌡️ 溫度：{temp}°C\n☁️ 狀態：{final_fix_text(desc)}\n"
        
        if is_query_today:
            aqi_url = f"http://api.openweathermap.org/data/2.5/air_pollution?lat={lat}&lon={lon}&appid={API_KEY}"
            aqi_data = requests.get(aqi_url, timeout=3).json()
            pm25 = aqi_data['list'][0]['components'].get('pm2_5', 0)
            aqi_str = "良好" if pm25 <= 15.4 else "普通" if pm25 <= 35.4 else "對敏感族群不健康"
            res += f"🌬️ 空氣品質：{aqi_str}\n"
            
        res += "--------------------------\n💡 建議：😊 祝您有美好的一天！\n--------------------------"
        return res
    except:
        return "⚠️ 獲取氣象數據失敗。"

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        req = request.get_json(silent=True, force=True)
        query_res = req.get('queryResult', {})
        params = query_res.get('parameters', {})
        
        # 解析日期 (支援 date-time 陣列)
        date_list = params.get('date-time') or params.get('date') or []
        target_date = None
        if isinstance(date_list, list) and len(date_list) > 0:
            target_date = str(date_list[0]).split('T')[0]
        elif isinstance(date_list, str):
            target_date = date_list.split('T')[0]

        # 解析地點 (支援多層 location 結構)
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