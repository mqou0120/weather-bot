import os
import requests
import re
from flask import Flask, request, jsonify
from datetime import datetime, timedelta

app = Flask(__name__)

# ==========================================
# 1. 設定區 (安全讀取環境變數)
# ==========================================
API_KEY = os.environ.get("WEATHER_API_KEY")

def get_tw_time():
    """修正 Render 伺服器時區問題，強制轉為台灣時間"""
    return datetime.utcnow() + timedelta(hours=8)

def get_advice(temp, weather_desc):
    """生活建議邏輯"""
    advice = ""
    if temp < 16: advice += "🥶 天氣寒冷，穿上厚大衣保暖喔！"
    elif temp < 22: advice += "🧥 有些涼意，加件薄外套吧。"
    elif temp > 30: advice += "🥵 天氣炎熱，多喝水注意防曬！"
    else: advice += "😊 氣溫舒適，是出門的好天氣。"
    
    if "雨" in weather_desc or "rain" in weather_desc.lower():
        advice += "\n☔ 提醒您，出門別忘了帶把傘！"
    return advice

def get_aqi(lat, lon):
    """空氣品質查詢"""
    aqi_url = f"http://api.openweathermap.org/data/2.5/air_pollution?lat={lat}&lon={lon}&appid={API_KEY}"
    try:
        res = requests.get(aqi_url).json()
        aqi = res['list'][0]['main']['aqi']
        aqi_map = {1: "良好", 2: "普通", 3: "中度", 4: "差", 5: "極差"}
        return aqi_map.get(aqi, "未知")
    except: return "暫無資料"

def get_weather_logic(user_input, original_text=None, target_date=None):
    """核心搜尋與預報邏輯"""
    if not API_KEY:
        return "⚠️ 伺服器配置錯誤，請檢查環境變數。"

    # 建立多重搜尋目標，解決 [JP] [AR] 亂跳問題
    search_targets = []
    clean_city = str(user_input).strip()
    
    # 如果含有英文，優先搜尋英文名
    if original_text:
        eng_match = re.findall(r'[a-zA-Z]+', original_text)
        if eng_match: search_targets.append(" ".join(eng_match))
    
    # 強制加上台灣代碼增加精確度
    search_targets.extend([f"{clean_city},TW", f"{clean_city}市,TW", clean_city])

    # 解析日期
    tw_now = get_tw_time()
    today_str = tw_now.strftime("%Y-%m-%d")
    
    date_str = ""
    if isinstance(target_date, list) and len(target_date) > 0:
        date_str = target_date[0][:10]
    elif isinstance(target_date, str):
        date_str = target_date[:10]
    
    is_today = (not date_str) or (date_str == today_str)
    mode = "weather" if is_today else "forecast"
    
    for target in search_targets:
        url = f"https://api.openweathermap.org/data/2.5/{mode}?q={target}&appid={API_KEY}&units=metric&lang=zh_tw"
        try:
            res = requests.get(url)
            if res.status_code == 200:
                data = res.json()
                
                # 處理繁體中文與國家標籤
                if is_today:
                    city_name = data.get('name')
                    country = data['sys'].get('country', '??')
                    temp = data['main']['temp']
                    desc = data['weather'][0]['description']
                    lat, lon = data['coord']['lat'], data['coord']['lon']
                    aqi_val = get_aqi(lat, lon)
                    aqi_display = f"🌬️ 空氣品質：{aqi_val}\n"
                else:
                    city_name = data['city']['name']
                    country = data['city'].get('country', '??')
                    # 找尋預報清單中符合日期的資料
                    day_list = [i for i in data['list'] if date_str in i['dt_txt']]
                    if not day_list: continue 
                    # 優先抓中午 12 點的預報
                    target_data = next((i for i in day_list if "12:00:00" in i['dt_txt']), day_list[0])
                    temp = target_data['main']['temp']
                    desc = target_data['weather'][0]['description']
                    aqi_display = ""

                # 強制繁體補丁
                desc = desc.replace("多云", "多雲").replace("阴", "陰").replace("阵雨", "陣雨")
                advice = get_advice(temp, desc)
                date_display = date_str if not is_today else today_str

                return (
                    f"🌍 氣象服務連線成功！\n"
                    f"({date_display})\n"
                    f"--------------------------\n"
                    f"📍 地點：{city_name} [{country}]\n"
                    f"🌡️ 溫度：{temp}°C\n"
                    f"☁️ 狀態：{desc}\n"
                    f"{aqi_display}"
                    f"--------------------------\n"
                    f"💡 建議：{advice}\n"
                    f"--------------------------"
                )
        except: continue

    return f"❓ 抱歉，找不到「{clean_city}」的氣象資料。"

# ==========================================
# 2. Webhook 路由
# ==========================================
@app.route('/webhook', methods=['POST'])
def webhook():
    req = request.get_json(silent=True, force=True)
    query_result = req.get('queryResult', {})
    params = query_result.get('parameters', {})
    
    original_text = query_result.get('queryText')
    target_date = params.get('date') or params.get('date-time')
    raw_location = params.get('location')

    # 地點解析防呆
    if isinstance(raw_location, list) and len(raw_location) > 0:
        raw_location = raw_location[0]

    if isinstance(raw_location, dict):
        query_city = (raw_location.get('city') or 
                      raw_location.get('subadmin-area') or 
                      raw_location.get('admin-area'))
    else:
        query_city = str(raw_location)

    if not query_city or query_city.lower() == "none":
        reply = "請問您想查詢哪個城市的天氣？"
    else:
        reply = get_weather_logic(query_city, original_text, target_date)
        
    return jsonify({"fulfillmentText": reply})

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)