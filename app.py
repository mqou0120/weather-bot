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
        "县": "縣", "国": "國", "华": "華", "龙": "龍", 
        "湾": "灣", "义": "義", "臺": "台", "层": "層", 
        "雾": "霧", "雷": "雷", "实": "實", "气": "氣", 
        "观": "觀", "测": "測", "晴间多云": "晴時多雲", 
        "，": " ", "区": "區", "街道": "" # 移除錯誤的「街道」後綴
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

def get_weather_info(city, is_today=True):
    if not API_KEY: return "⚠️ 請設定 API KEY"

    # 1. 強化搜尋策略：如果使用者打「新北/新北市」，強制轉換為精準搜尋詞
    raw_city = str(city).strip()
    if "新北" in raw_city:
        search_query = "New Taipei City,TW"
    else:
        # 一般地名清洗，並加上 ,TW 強制鎖定台灣
        clean_city = raw_city.replace("臺", "台").replace("市", "").replace("縣", "").replace("區", "").strip()
        search_query = f"{clean_city},TW" if not any(c.isalpha() for c in clean_city) else clean_city

    try:
        # 2. 地點搜尋 (增加回傳數量以供篩選)
        geo_url = f"http://api.openweathermap.org/geo/1.0/direct?q={search_query}&limit=5&appid={API_KEY}"
        geo_res = requests.get(geo_url, timeout=3).json()
        
        if not geo_res:
            return f"❓ 找不到「{city}」的地點資訊"

        # 3. 台灣優先篩選邏輯：從結果中挑選座標在台灣範圍內的
        target_data = geo_res[0] # 預設選第一個
        for item in geo_res:
            lat, lon = item['lat'], item['lon']
            if (21.8 < lat < 25.5) and (119.5 < lon < 122.5):
                target_data = item
                break # 找到台灣的就跳出

        lat, lon = target_data['lat'], target_data['lon']
        country = target_data.get('country', '??')
        
        # 強制校正台灣座標的國碼 (針對板橋回傳 CN 的錯誤)
        if (21.8 < lat < 25.5) and (119.5 < lon < 122.5):
            country = "TW"

        # 取得名稱並校正（處理新北被標為台北或新北街道的問題）
        location_name = target_data.get('local_names', {}).get('zh', target_data['name'])
        location_name = force_traditional(location_name)
        
        # 特殊修正：如果搜新北卻回傳台北，手動校正顯示名稱
        if "新北" in raw_city and "台北" in location_name:
            location_name = "新北市"

        # 4. 天氣數據
        w_url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={API_KEY}&units=metric&lang=zh_tw"
        w_data = requests.get(w_url, timeout=3).json()
        
        temp = w_data.get('main', {}).get('temp', "--")
        desc = force_traditional(w_data.get('weather', [{}])[0].get('description', "未知"))

        # 5. 建議內容
        suggest = "😊 氣溫舒適，是出門的好天氣。"
        if "雨" in desc: suggest = "☔ 記得帶把傘，注意安全。"
        elif isinstance(temp, (int, float)):
            if temp >= 28: suggest = "🥵 天氣炎熱，請多補充水分。"
            elif temp <= 18: suggest = "🧥 氣溫偏低，記得穿件外套。"

        # 6. 組合格式
        date_str = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d")
        
        output = (
            f"🌍 氣象服務連線成功！\n"
            f"({date_str})\n"
            f"--------------------------\n"
            f"📍 地點：{location_name} [{country}]\n"
            f"🌡️ 溫度：{temp}°C\n"
            f"☁️ 狀態：{desc}\n"
        )
        
        if is_today:
            aqi_val = get_aqi_info(lat, lon)
            output += f"🌬️ 空氣品質：{aqi_val}\n"
            
        output += (
            f"--------------------------\n"
            f"💡 建議：{suggest}\n"
            f"--------------------------"
        )
        return output
    except:
        return "⚠️ 服務連線超時，請稍後再試。"

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        req = request.get_json(silent=True, force=True)
        query_res = req.get('queryResult', {})
        params = query_res.get('parameters', {})
        
        date_param = params.get('date', '')
        is_today = True
        if date_param:
            today_str = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d")
            if today_str not in str(date_param):
                is_today = False

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

        reply = get_weather_info(city.replace("天氣", "").strip(), is_today=is_today)
        return jsonify({"fulfillmentText": reply})
    except:
        return jsonify({"fulfillmentText": "系統忙碌中。"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))