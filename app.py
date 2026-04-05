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

def get_weather_info(user_input_city, target_date_str=None):
    """處理氣象邏輯"""
    if not API_KEY: return "⚠️ 未偵測到 API 金鑰"

    # 1. 時間判斷邏輯
    tw_now = datetime.now(timezone(timedelta(hours=8)))
    today_str = tw_now.strftime("%Y-%m-%d")
    
    # 判斷是否為查詢今天 (若無日期或日期等於今天)
    is_query_today = True if (not target_date_str or target_date_str == today_str) else False
    display_date = target_date_str if target_date_str else today_str

    # 2. 地點預處理
    display_city = user_input_city.strip()
    search_city = display_city.replace("臺", "台")
    
    # 強制導正新北市搜尋，避免跳至中國
    is_requesting_new_taipei = "新北" in display_city
    search_query = "New Taipei City,TW" if is_requesting_new_taipei else f"{search_city},TW"

    try:
        # 3. 獲取地理座標並篩選台灣範圍
        geo_url = f"http://api.openweathermap.org/geo/1.0/direct?q={search_query}&limit=5&appid={API_KEY}"
        geo_res = requests.get(geo_url, timeout=5).json()
        if not geo_res: return f"❓ 找不到「{user_input_city}」的地點資訊"

        target = geo_res[0]
        for item in geo_res:
            if (21.8 < item['lat'] < 25.5) and (119.5 < item['lon'] < 122.5):
                target = item
                break

        lat, lon = target['lat'], target['lon']
        country = "TW" if (21.8 < lat < 25.5) else target.get('country', '??')

        # 4. 強制名稱與繁體修正
        location_name = final_fix_text(target.get('local_names', {}).get('zh', target['name']))
        if is_requesting_new_taipei: location_name = "新北市"
        elif "板橋" in display_city: location_name = "板橋區"

        # 5. 根據日期調用不同 API
        if is_query_today:
            # 當前天氣
            w_url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={API_KEY}&units=metric&lang=zh_tw"
            w_res = requests.get(w_url, timeout=5).json()
            temp = w_res.get('main', {}).get('temp', "--")
            desc = final_fix_text(w_res.get('weather', [{}])[0].get('description', "未知"))
        else:
            # 未來預報
            f_url = f"https://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={API_KEY}&units=metric&lang=zh_tw"
            f_res = requests.get(f_url, timeout=5).json()
            forecast_list = f_res.get('list', [])
            target_data = forecast_list[0]
            # 尋找目標日期中午 12 點的預報數據
            for entry in forecast_list:
                if display_date in entry.get('dt_txt', ''):
                    target_data = entry
                    if "12:00:00" in entry.get('dt_txt', ''): break
            temp = target_data.get('main', {}).get('temp', "--")
            desc = final_fix_text(target_data.get('weather', [{}])[0].get('description', "未知"))

        # 6. 組合回應訊息格式
        res_text = (
            f"🌍 氣象服務連線成功！\n"
            f"({display_date})\n"
            f"--------------------------\n"
            f"📍 地點：{location_name} [{country}]\n"
            f"🌡️ 溫度：{temp}°C\n"
            f"☁️ 狀態：{desc}\n"
        )
        
        # 僅「今天」查詢時顯示空氣品質
        if is_query_today:
            aqi_val = get_aqi_info(lat, lon)
            res_text += f"🌬️ 空氣品質：{aqi_val}\n"
            
        res_text += f"--------------------------\n💡 建議：😊 氣溫舒適，是出門的好天氣。\n--------------------------"
        return res_text
    except Exception:
        return "⚠️ 系統異常，請稍後再試。"

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        req = request.get_json(silent=True, force=True)
        query_res = req.get('queryResult', {})
        params = query_res.get('parameters', {})
        
        # 解析日期參數
        raw_date = params.get('date', '')
        target_date = raw_date.split('T')[0] if raw_date else None

        # 解析地點參數
        loc_val = params.get('location', "")
        city = ""
        if isinstance(loc_val, dict):
            city = loc_val.get('city') or loc_val.get('subadmin-area') or loc_val.get('admin-area')
        elif isinstance(loc_val, list) and len(loc_val) > 0:
            city = loc_val[0]
        else:
            city = str(loc_val)

        if not city or city == "{}" or city.lower() == "none":
            city = query_res.get('queryText', '')

        reply = get_weather_info(city.replace("天氣", "").strip(), target_date_str=target_date)
        return jsonify({"fulfillmentText": reply})
    except Exception:
        return jsonify({"fulfillmentText": "⚠️ 數據解析失敗。"})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)