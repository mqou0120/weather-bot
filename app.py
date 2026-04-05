import os
import requests
from flask import Flask, request, jsonify
from datetime import datetime, timedelta

app = Flask(__name__)

# 請務必在 Render 的 Environment Variables 設定 WEATHER_API_KEY
OPENWEATHER_API_KEY = os.environ.get("WEATHER_API_KEY")

def get_weather_info(city):
    print(f"\n>>> [LOG] 收到地名: {city}")
    if not OPENWEATHER_API_KEY:
        return "⚠️ 伺服器配置錯誤，請檢查 API KEY 設定。"

    # 1. 地名標準化：統一繁簡並移除「市、縣、區」
    clean_city = city.replace("臺", "台").replace("市", "").replace("縣", "").replace("區", "").replace("天氣", "").strip()
    
    # 2. 智慧型搜尋策略：中文強制鎖定台灣，英文開放全球
    is_chinese = not any(c.isalpha() for c in clean_city)
    search_query = f"{clean_city},TW" if is_chinese else clean_city
    print(f">>> [LOG] 最終搜尋關鍵字: {search_query}")

    try:
        # 3. 第一階段：座標抓取 (Geocoding)
        geo_url = f"http://api.openweathermap.org/geo/1.0/direct?q={search_query}&limit=1&appid={OPENWEATHER_API_KEY}"
        geo_res = requests.get(geo_url, timeout=5).json()
        
        # [救援機制] 如果鎖定台灣搜尋失敗，則嘗試全球裸搜 (處理國際城市)
        if not geo_res:
            print(f">>> [LOG] 台灣鎖定搜尋失敗，嘗試全球裸搜: {city}")
            geo_url = f"http://api.openweathermap.org/geo/1.0/direct?q={city}&limit=1&appid={OPENWEATHER_API_KEY}"
            geo_res = requests.get(geo_url, timeout=5).json()

        if not geo_res:
            return f"❓ 抱歉，找不到「{city}」的地點資訊。"

        lat, lon = geo_res[0]['lat'], geo_res[0]['lon']
        location_name = geo_res[0].get('local_names', {}).get('zh', geo_res[0]['name'])
        country = geo_res[0].get('country', '')

        # 4. 第二階段：天氣數據抓取
        w_url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={OPENWEATHER_API_KEY}&units=metric&lang=zh_tw"
        w_data = requests.get(w_url, timeout=5).json()
        
        temp = w_data.get('main', {}).get('temp', "--")
        desc = w_data.get('weather', [{}])[0].get('description', "未知")

        # 5. 第三階段：空氣品質 (AQI)
        aqi_desc = "暫無資料"
        try:
            aqi_url = f"http://api.openweathermap.org/data/2.5/air_pollution?lat={lat}&lon={lon}&appid={OPENWEATHER_API_KEY}"
            aqi_res = requests.get(aqi_url, timeout=3).json()
            aqi_val = aqi_res['list'][0]['main']['aqi']
            aqi_map = {1: "良好", 2: "普通", 3: "不健康(敏感)", 4: "不健康", 5: "危害"}
            aqi_desc = aqi_map.get(aqi_val, "未知")
        except:
            pass

        # 6. 強制繁體字補丁
        trad_map = {"多云": "多雲", "阴": "陰", "阵雨": "陣雨", "晴": "晴朗"}
        for k, v in trad_map.items():
            desc = desc.replace(k, v)

        # 7. 建議邏輯
        suggest = "天氣舒適，出門走走吧！ ✨"
        if "雨" in desc: suggest = "記得帶傘喔！ ☔"
        elif isinstance(temp, (int, float)):
            if temp >= 28: suggest = "天氣熱，多補充水分！ 🥤"
            elif temp <= 18: suggest = "天氣涼，穿件外套吧。 🧥"

        # 8. 格式化輸出
        date_str = (datetime.utcnow() + timedelta(hours=8)).strftime("%Y-%m-%d")
        
        return (
            f"🌍 氣象服務連線成功！\n({date_str})\n"
            f"--------------------------\n"
            f"📍 地點：{location_name} [{country}]\n"
            f"🌡️ 溫度：{temp}°C\n"
            f"☁️ 狀態：{desc}\n"
            f"😷 空氣：{aqi_desc}\n"
            f"--------------------------\n"
            f"💡 建議：{suggest}\n"
            f"--------------------------"
        )

    except Exception as e:
        print(f">>> [ERROR] 發生異常: {e}")
        return "⚠️ 數據解析失敗，請稍後再試。"

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        req = request.get_json(silent=True, force=True)
        res = req.get('queryResult', {})
        params = res.get('parameters', {})
        
        # 提取城市名稱：優先從 Dialogflow 參數拿，拿不到就拿對話原文
        loc = params.get('location')
        if isinstance(loc, dict):
            city = loc.get('city') or loc.get('admin-area')
        elif isinstance(loc, list) and loc:
            city = loc[0]
        else:
            city = str(loc) if loc else ""

        if not city or city.lower() == "none":
            city = res.get('queryText', '')

        reply = get_weather_info(city)
        return jsonify({"fulfillmentText": reply})
    except Exception as e:
        print(f">>> [WEBHOOK ERROR] {e}")
        return jsonify({"fulfillmentText": "系統忙碌中，請稍後再試。"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))