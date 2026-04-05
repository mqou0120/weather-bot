import os
import requests
from flask import Flask, request, jsonify
from datetime import datetime, timedelta, timezone

app = Flask(__name__)

# 從環境變數讀取 API KEY
API_KEY = os.environ.get("WEATHER_API_KEY")

def get_aqi_info(lat, lon):
    """根據 OpenWeather 的 PM2.5 數值，依照台灣環境部標準換算"""
    try:
        if not API_KEY: return "無金鑰"
        url = f"http://api.openweathermap.org/data/2.5/air_pollution?lat={lat}&lon={lon}&appid={API_KEY}"
        res = requests.get(url, timeout=2).json()
        
        # 取得 PM2.5 濃度 (單位: μg/m³)
        pm25 = res['list'][0]['components'].get('pm2_5', 0)
        
        # 台灣環境部 PM2.5 分級標準 (細分版)
        if pm25 <= 15.4:
            return f"良好 ✨ ({pm25} μg/m³)"
        elif pm25 <= 35.4:
            return f"普通 ☁️ ({pm25} μg/m³)"
        elif pm25 <= 54.4:
            return f"對敏感族群不健康 ⚠️ ({pm25} μg/m³)"
        elif pm25 <= 150.4:
            return f"不健康 😷 ({pm25} μg/m³)"
        else:
            return f"危害 🚨 ({pm25} μg/m³)"
    except Exception:
        return "數據獲取中"

def get_weather_info(city):
    if not API_KEY: return "⚠️ 請在後台設定 WEATHER_API_KEY"

    # 1. 地名清洗
    clean_city = str(city).replace("臺", "台").replace("市", "").replace("縣", "").replace("區", "").strip()
    search_query = f"{clean_city},TW" if not any(c.isalpha() for c in clean_city) else clean_city

    try:
        # 2. 座標轉換 (Geo API)
        geo_url = f"http://api.openweathermap.org/geo/1.0/direct?q={search_query}&limit=1&appid={API_KEY}"
        geo_res = requests.get(geo_url, timeout=3)
        
        if geo_res.status_code != 200 or not geo_res.json():
            return f"❓ 找不到「{city}」的地點資訊，請輸入正確地名（如：板橋 或 台北）。"

        data = geo_res.json()[0]
        lat, lon = data['lat'], data['lon']
        location_name = data.get('local_names', {}).get('zh', data['name'])

        # 3. 抓取天氣數據
        w_url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={API_KEY}&units=metric&lang=zh_tw"
        w_data = requests.get(w_url, timeout=3).json()
        
        temp = w_data.get('main', {}).get('temp', "--")
        desc = w_data.get('weather', [{}])[0].get('description', "未知")
        desc = desc.replace("多云", "多雲").replace("阴", "陰").replace("阵雨", "陣雨")
        
        # 4. 呼叫空氣品質 (台灣標準)
        aqi_status = get_aqi_info(lat, lon)

        # 5. 天氣建議邏輯
        suggest = "天氣舒適，出門走走吧！ ✨"
        if "雨" in desc:
            suggest = "記得帶傘喔！ ☔"
        elif isinstance(temp, (int, float)):
            if temp >= 29: suggest = "天氣炎熱，注意防曬多喝水！ 🥤"
            elif temp <= 17: suggest = "天氣偏涼，穿件外套別感冒。 🧥"

        # 6. 取得台灣時間 (UTC+8)
        tw_time = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M")

        return (
            f"🌍 氣象服務 ({tw_time})\n"
            f"--------------------------\n"
            f"📍 地點：{location_name}\n"
            f"🌡️ 溫度：{temp}°C\n"
            f"☁️ 狀態：{desc}\n"
            f"😷 空氣：{aqi_status}\n"
            f"--------------------------\n"
            f"💡 建議：{suggest}"
        )
    except Exception as e:
        print(f">>> [ERROR]: {e}")
        return "⚠️ 氣象伺服器連線超時，請稍後再試。"

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        req = request.get_json(silent=True, force=True)
        query_res = req.get('queryResult', {})
        params = query_res.get('parameters', {})
        
        # --- 強健的地名抓取邏輯，專門應對截圖中的複雜結構 ---
        loc_val = params.get('location')
        city = ""

        if isinstance(loc_val, list) and len(loc_val) > 0:
            # 處理像 [{'subadmin-area': '板橋區', ...}] 這種結構
            item = loc_val[0]
            if isinstance(item, dict):
                city = item.get('subadmin-area') or item.get('city') or item.get('admin-area')
            else:
                city = str(item)
        elif isinstance(loc_val, dict):
            city = loc_val.get('subadmin-area') or loc_val.get('city') or loc_val.get('admin-area')
        else:
            city = str(loc_val)

        # 備援：如果 Dialogflow 參數解析失敗，直接拿使用者講的話
        if not city or city.strip().lower() == "none" or city == "{}":
            city = query_res.get('queryText', '')

        # 過濾掉「天氣」關鍵字
        final_city = city.replace("天氣", "").strip()
        
        reply = get_weather_info(final_city)
        return jsonify({"fulfillmentText": reply})

    except Exception as e:
        print(f">>> [WEBHOOK ERROR]: {e}")
        return jsonify({"fulfillmentText": "系統目前無法處理此地點，請直接輸入城市名稱（例如：台北）。"})

if __name__ == '__main__':
    # Render 會自動設定 PORT
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)