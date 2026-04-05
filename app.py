from flask import Flask, request, jsonify
import requests
import re
from datetime import datetime

app = Flask(__name__)

# ==========================================
# 1. 設定區
# ==========================================
API_KEY = "7a1ca5902a4614def67da4309c6ee4af"

def save_log(user_text, city, date_param, mode, result):
    """【功能 5：記錄日誌】"""
    with open("weather_bot_log.txt", "a", encoding="utf-8") as f:
        time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        f.write(f"[{time_str}] 輸入: {user_text} | 城市: {city} | 模式: {mode} | 日期: {date_param} | 結果: {result[:10]}...\n")

def get_advice(temp, weather_desc):
    """【功能 2：生活建議】"""
    advice = ""
    if temp < 16: advice += "🥶 天氣寒冷，穿上厚大衣保暖喔！"
    elif temp < 22: advice += "⛅ 涼涼的，加件薄外套比較好。"
    elif temp > 30: advice += "🥵 天氣炎熱，多喝水注意防曬！"
    else: advice += "😊 氣溫舒適，是出門的好天氣。"
    
    if "雨" in weather_desc or "rain" in weather_desc.lower():
        advice += "\n☔ 提醒您，出門別忘了帶把傘！"
    return advice

def get_aqi(lat, lon):
    """【功能 3：空氣品質】"""
    aqi_url = f"http://api.openweathermap.org/data/2.5/air_pollution?lat={lat}&lon={lon}&appid={API_KEY}"
    try:
        res = requests.get(aqi_url).json()
        aqi = res['list'][0]['main']['aqi']
        aqi_map = {1: "良好 (Excellent)", 2: "普通 (Fair)", 3: "中度 (Moderate)", 4: "差 (Poor)", 5: "極差 (Very Poor)"}
        return aqi_map.get(aqi, "未知")
    except: return "暫無資料"

def get_weather_logic(user_input, original_text=None, target_date=None):
    """【功能 1：核心搜尋與預報邏輯】"""
    search_targets = []
    if original_text:
        eng_match = re.findall(r'[a-zA-Z]+', original_text)
        if eng_match: search_targets.append(" ".join(eng_match))
    
    clean_city = str(user_input).strip()
    search_targets.extend([clean_city, f"{clean_city},TW", f"{clean_city}市,TW"])

    # 解析日期
    date_str = ""
    if isinstance(target_date, list) and len(target_date) > 0:
        date_str = target_date[0][:10]
    elif isinstance(target_date, str):
        date_str = target_date[:10]
        
    today_str = datetime.now().strftime("%Y-%m-%d")
    is_today = (not date_str) or (date_str == today_str)
    mode = "weather" if is_today else "forecast"
    
    for target in search_targets:
        url = f"https://api.openweathermap.org/data/2.5/{mode}?q={target}&appid={API_KEY}&units=metric&lang=zh_tw"
        try:
            res = requests.get(url)
            if res.status_code == 200:
                data = res.json()
                
                if is_today:
                    city_name = data['name']
                    country = data['sys'].get('country', '??')
                    temp = data['main']['temp']
                    desc = data['weather'][0]['description']
                    lat, lon = data['coord']['lat'], data['coord']['lon']
                    aqi_val = get_aqi(lat, lon)
                    aqi_display = f"🌬️ 空氣品質：{aqi_val}\n"
                else:
                    city_name = data['city']['name']
                    country = data['city'].get('country', '??')
                    day_list = [i for i in data['list'] if date_str in i['dt_txt']]
                    if not day_list: continue 
                    target_data = next((i for i in day_list if "12:00:00" in i['dt_txt']), day_list[0])
                    temp = target_data['main']['temp']
                    desc = target_data['weather'][0]['description']
                    aqi_display = ""

                advice = get_advice(temp, desc)
                date_display = date_str if not is_today else "現在"

                final_reply = (
                    f"🌍 氣象服務連線成功！({date_display})\n"
                    f"----------------------------\n"
                    f"📍 地點：{city_name} [{country}]\n"
                    f"🌡️ 溫度：{temp}°C\n"
                    f"☁️ 狀態：{desc}\n"
                    f"{aqi_display}"
                    f"----------------------------\n"
                    f"💡 建議：{advice}\n"
                    f"----------------------------"
                )
                save_log(original_text, city_name, date_str, mode, "成功")
                return final_reply
        except: continue

    save_log(original_text, clean_city, date_str, mode, "失敗")
    return f"❓ 抱歉，我找不到「{clean_city}」在 {date_str if date_str else '現在'} 的氣象資料。"

# ==========================================
# 2. Webhook 路由 (含強大防呆邏輯)
# ==========================================
@app.route('/webhook', methods=['POST'])
def webhook():
    req = request.get_json(silent=True, force=True)
    query_result = req.get('queryResult', {})
    params = query_result.get('parameters', {})
    
    original_text = query_result.get('queryText')
    target_date = params.get('date') 
    raw_location = params.get('location')

    # 【關鍵修復】：處理 Dialogflow 回傳的 List 格式
    if isinstance(raw_location, list) and len(raw_location) > 0:
        raw_location = raw_location[0]

    # 解析地點
    if isinstance(raw_location, dict):
        query_city = (raw_location.get('city') or 
                      raw_location.get('subadmin-area') or 
                      raw_location.get('admin-area') or 
                      raw_location.get('street-address'))
    else:
        query_city = raw_location

    if not query_city:
        reply = "請告訴我您想查詢的城市名稱。"
    else:
        reply = get_weather_logic(query_city, original_text, target_date)
        
    return jsonify({"fulfillmentText": reply})

if __name__ == "__main__":
    app.run(port=5000, debug=True)