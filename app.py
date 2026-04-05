import os
import requests
from flask import Flask, request, jsonify
from datetime import datetime, timedelta

app = Flask(__name__)

# 從 Render 環境變數讀取 API Key (請確保 Render 已設定 WEATHER_API_KEY)
API_KEY = os.environ.get("WEATHER_API_KEY")

def get_weather_info(city):
    print(f"\n>>> [LOG] 收到查詢請求: {city}")
    if not API_KEY:
        print(">>> [ERROR] 缺少 WEATHER_API_KEY 環境變數")
        return "⚠️ 系統設定錯誤：伺服器缺少 API Key。"

    # 1. 地名洗滌：處理繁簡體並移除行政區後綴 (如：臺南市 -> 台南)
    clean_city = str(city).replace("臺", "台").replace("市", "").replace("縣", "").replace("區", "").replace("天氣", "").strip()
    
    # 2. 搜尋策略：中文預設鎖定台灣 (,TW)，英文則全球搜尋
    # 這解決了「板橋」優先跑去日本的問題
    search_query = f"{clean_city},TW" if not any(c.isalpha() for c in clean_city) else clean_city
    
    # 針對特定難找的地名做補丁
    special_cases = {"淡水": "Tamsui", "清水": "Qingshui", "羅東": "Luodong"}
    if clean_city in special_cases:
        search_query = f"{special_cases[clean_city]},TW"

    try:
        # 3. 獲取座標 (Geocoding API)
        geo_url = f"http://api.openweathermap.org/geo/1.0/direct?q={search_query}&limit=1&appid={API_KEY}"
        geo_res = requests.get(geo_url, timeout=5).json()
        
        # 備援機制：如果加了 ,TW 找不到，則裸搜原名
        if not geo_res:
            geo_url = f"http://api.openweathermap.org/geo/1.0/direct?q={clean_city}&limit=1&appid={API_KEY}"
            geo_res = requests.get(geo_url, timeout=5).json()
            
        if not geo_res:
            print(f">>> [WARNING] 找不到地點: {search_query}")
            return f"❓ 抱歉，找不到「{city}」的地點資訊。"

        lat, lon = geo_res[0]['lat'], geo_res[0]['lon']
        location_name = geo_res[0].get('local_names', {}).get('zh', geo_res[0]['name'])
        country = geo_res[0].get('country', '')

        # 4. 獲取當前天氣 (Current Weather API)
        w_url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={API_KEY}&units=metric&lang=zh_tw"
        w_data = requests.get(w_url, timeout=5).json()
        temp = w_data.get('main', {}).get('temp', "--")
        desc = w_data.get('weather', [{}])[0].get('description', "未知")

        # 5. 獲取空氣品質 (Air Pollution API) - 獨立 try 以防 API 斷訊
        aqi_desc = "數據維護中"
        try:
            aqi_url = f"http://api.openweathermap.org/data/2.5/air_pollution?lat={lat}&lon={lon}&appid={API_KEY}"
            aqi_res = requests.get(aqi_url, timeout=3).json()
            aqi_val = aqi_res['list'][0]['main']['aqi']
            # OpenWeather AQI 1=Good, 2=Fair, 3=Moderate, 4=Poor, 5=Very Poor
            aqi_map = {1: "良好", 2: "普通", 3: "對敏感族群不健康", 4: "不健康", 5: "危害"}
            aqi_desc = aqi_map.get(aqi_val, "未知")
        except Exception as e:
            print(f">>> [AQI LOG] 空氣品質抓取失敗: {e}")

        # 6. 狀態繁體化補丁與建議邏輯
        desc = desc.replace("多云", "多雲").replace("阴", "陰").replace("阵雨", "陣雨")
        
        suggest_txt, emoji = ("天氣舒適，出門走走吧！", "✨")
        if "雨" in desc:
            suggest_txt, emoji = ("記得帶傘，別淋濕囉！", "☔")
        elif isinstance(temp, (int, float)):
            if temp >= 28: suggest_txt, emoji = ("天氣炎熱，記得多補充水分！", "🥤")
            elif temp <= 18: suggest_txt, emoji = ("氣溫較低，穿件外套保暖喔。", "🧥")

        # 7. 台灣時區校正 (UTC+8)
        tw_time = datetime.utcnow() + timedelta(hours=8)
        date_str = tw_time.strftime("%Y-%m-%d")

        # 組合最終回覆格式
        response = (
            f"🌍 氣象服務連線成功！\n"
            f"({date_str})\n"
            f"--------------------------\n"
            f"📍 地點：{location_name} [{country}]\n"
            f"🌡️ 溫度：{temp}°C\n"
            f"☁️ 狀態：{desc}\n"
            f"😷 空氣：{aqi_desc}\n"
            f"--------------------------\n"
            f"💡 建議：{emoji} {suggest_txt}\n"
            f"--------------------------"
        )
        print(f">>> [SUCCESS] 查詢成功: {location_name}")
        return response

    except Exception as e:
        print(f">>> [CRITICAL ERROR] 內部錯誤: {e}")
        return "⚠️ 氣象數據解析失敗，請稍後再試。"

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        req = request.get_json(silent=True, force=True)
        query_result = req.get('queryResult', {})
        params = query_result.get('parameters', {})
        
        # 強化地點抓取：參數優先，原文補位
        city_param = params.get('location')
        city = ""
        if isinstance(city_param, dict):
            city = city_param.get('city') or city_param.get('admin-area')
        elif isinstance(city_param, list) and city_param:
            city = city_param[0]
        else:
            city = str(city_param)

        final_city = city if city and city.lower() != 'none' else query_result.get('queryText', '')
        
        if not final_city:
            return jsonify({"fulfillmentText": "請問你想查詢哪個城市？"})

        reply = get_weather_info(final_city)
        return jsonify({"fulfillmentText": reply})
    except Exception as e:
        print(f">>> [WEBHOOK ERROR] {e}")
        return jsonify({"fulfillmentText": "系統忙碌中，請重新輸入地名。"})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)