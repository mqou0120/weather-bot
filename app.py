from flask import Flask, request, jsonify
import requests
import re
import os
from datetime import datetime, timedelta

app = Flask(__name__)

# ==========================================
# 1. 設定區
# ==========================================
# 建議從環境變數讀取，若無則使用你提供的 Key
API_KEY = os.environ.get("WEATHER_API_KEY") or "7a1ca5902a4614def67da4309c6ee4af"

def save_log(user_text, city, date_param, mode, result):
    """【功能 5：記錄日誌】(Render 環境下建議搭配 print 使用)"""
    time_str = (datetime.utcnow() + timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S")
    log_msg = f"[{time_str}] 輸入: {user_text} | 城市: {city} | 模式: {mode} | 日期: {date_param} | 結果: {result[:10]}..."
    print(f">>> [LOG] {log_msg}")
    try:
        with open("weather_bot_log.txt", "a", encoding="utf-8") as f:
            f.write(log_msg + "\n")
    except:
        pass

def get_advice(temp, weather_desc):
    """【功能 2：生活建議】"""
    advice = ""
    if temp < 16: advice += "🥶 天氣寒冷，穿上厚大衣保暖喔！"
    elif temp < 22: advice += "⛅ 涼涼的，加件薄外套比較好。"
    elif temp > 30: advice += "🥵 天氣炎熱，多喝水注意防曬！"
    else: advice += "😊 氣溫舒適，是出門的好天氣。"
    
    if "雨" in weather_desc:
        advice += "\n☔ 提醒您，出門別忘了帶把傘！"
    return advice

def get_aqi(lat, lon):
    """【功能 3：空氣品質整合】"""
    aqi_url = f"http://api.openweathermap.org/data/2.5/air_pollution?lat={lat}&lon={lon}&appid={API_KEY}"
    try:
        res = requests.get(aqi_url, timeout=3).json()
        aqi = res['list'][0]['main']['aqi']
        # 繁體化與對應
        aqi_map = {
            1: "良好 (Good)", 
            2: "普通 (Fair)", 
            3: "對敏感族群不健康 (Moderate)", 
            4: "不健康 (Poor)", 
            5: "危害 (Very Poor)"
        }
        return aqi_map.get(aqi, "未知")
    except: 
        return "暫無資料"

def get_weather_logic(user_input, original_text=None, target_date=None):
    """【功能 1：核心搜尋與預報邏輯】"""
    # 地名清洗：統一繁體、移除行政區後綴
    clean_city = str(user_input).replace("臺", "台").replace("市", "").replace("區", "").replace("縣", "").strip()
    
    # 建立搜尋優先級：優先搜尋台灣地區
    search_targets = [f"{clean_city},TW", clean_city]
    if original_text:
        eng_match = re.findall(r'[a-zA-Z]+', original_text)
        if eng_match: search_targets.insert(0, " ".join(eng_match))

    # 解析日期邏輯
    date_str = ""
    if isinstance(target_date, list) and len(target_date) > 0:
        date_str = target_date[0][:10]
    elif isinstance(target_date, str):
        date_str = target_date[:10]
    
    # 台灣時間校正
    tw_now = datetime.utcnow() + timedelta(hours=8)
    today_str = tw_now.strftime("%Y-%m-%d")
    is_today = (not date_str) or (date_str == today_str)
    mode = "weather" if is_today else "forecast"
    
    for target in search_targets:
        url = f"https://api.openweathermap.org/data/2.5/{mode}?q={target}&appid={API_KEY}&units=metric&lang=zh_tw"
        try:
            res = requests.get(url, timeout=5)
            if res.status_code == 200:
                data = res.json()
                
                # 關鍵修正：不論現在或預報，都要抓座標來算 AQI
                if is_today:
                    city_name = data['name']
                    country = data['sys'].get('country', '??')
                    temp = data['main']['temp']
                    desc = data['weather'][0]['description']
                    lat, lon = data['coord']['lat'], data['coord']['lon']
                else:
                    city_name = data['city']['name']
                    country = data['city'].get('country', '??')
                    lat, lon = data['city']['coord']['lat'], data['city']['coord']['lon']
                    
                    # 篩選預報日期
                    day_list = [i for i in data['list'] if date_str in i['dt_txt']]
                    if not day_list: continue 
                    # 優先抓取中午數據，若無則抓該日第一筆
                    target_data = next((i for i in day_list if "12:00:00" in i['dt_txt']), day_list[0])
                    temp = target_data['main']['temp']
                    desc = target_data['weather'][0]['description']

                # 統一繁體修正
                desc = desc.replace("多云", "多雲").replace("阴", "陰").replace("阵雨", "陣雨")
                city_name = city_name.replace("区", "區").replace("县", "縣")

                # 抓取空氣品質 (AQI)
                aqi_val = get_aqi(lat, lon)
                advice = get_advice(temp, desc)
                date_display = date_str if not is_today else today_str

                final_reply = (
                    f"🌍 氣象服務連線成功！({date_display})\n"
                    f"----------------------------\n"
                    f"📍 地點：{city_name} [{country}]\n"
                    f"🌡️ 溫度：{temp}°C\n"
                    f"☁️ 狀態：{desc}\n"
                    f"🌬️ 空氣品質：{aqi_val}\n"
                    f"----------------------------\n"
                    f"💡 建議：{advice}\n"
                    f"----------------------------"
                )
                save_log(original_text, city_name, date_display, mode, "成功")
                return final_reply
        except Exception as e:
            print(f">>> [DEBUG] 搜尋 {target} 時發生錯誤: {e}")
            continue

    save_log(original_text, clean_city, date_str, mode, "失敗")
    return f"❓ 抱歉，我找不到「{clean_city}」的氣象資料。"

# ==========================================
# 2. Webhook 路由
# ==========================================
@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        req = request.get_json(silent=True, force=True)
        query_result = req.get('queryResult', {})
        params = query_result.get('parameters', {})
        
        original_text = query_result.get('queryText')
        target_date = params.get('date') 
        raw_location = params.get('location')

        # 處理 Dialogflow 的 List/Dict 複合格式
        if isinstance(raw_location, list) and len(raw_location) > 0:
            raw_location = raw_location[0]

        if isinstance(raw_location, dict):
            query_city = (raw_location.get('city') or 
                          raw_location.get('subadmin-area') or 
                          raw_location.get('admin-area'))
        else:
            query_city = raw_location

        # 防呆：如果參數抓不到地名，直接用原文搜尋
        if not query_city or str(query_city).lower() == 'none':
            query_city = original_text.replace("天氣", "").replace("如何", "").strip()

        reply = get_weather_logic(query_city, original_text, target_date)
        return jsonify({"fulfillmentText": reply})
    except Exception as e:
        print(f">>> [ERROR] Webhook 崩潰: {e}")
        return jsonify({"fulfillmentText": "系統忙碌中，請稍後再試。"})

if __name__ == "__main__":
    # Render 部署需讀取 PORT 環境變數
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)