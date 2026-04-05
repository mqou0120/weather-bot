import os
import requests
from flask import Flask, request, jsonify
from datetime import datetime, timedelta

app = Flask(__name__)
# 取得 Render 環境變數中的 API Key
API_KEY = os.environ.get("WEATHER_API_KEY")

def get_weather_info(city):
    print(f">>> [LOG] 嘗試查詢城市: {city}")
    if not API_KEY:
        return "⚠️ 系統錯誤：請在 Render 設定 WEATHER_API_KEY。"

    # 1. 地名標準化：統一繁體並移除行政區字眼
    clean_city = str(city).replace("臺", "台").replace("市", "").replace("縣", "").replace("區", "").replace("天氣", "").strip()
    
    # 2. 搜尋策略：中文優先找台灣，英文找全球
    search_query = f"{clean_city},TW" if not any(c.isalpha() for c in clean_city) else clean_city

    try:
        # 3. 獲取座標 (加上 5 秒超時保護)
        geo_url = f"http://api.openweathermap.org/geo/1.0/direct?q={search_query}&limit=1&appid={API_KEY}"
        geo_res = requests.get(geo_url, timeout=5).json()
        
        # 備援：如果加了 ,TW 找不到，就直接搜原名
        if not geo_res:
            geo_url = f"http://api.openweathermap.org/geo/1.0/direct?q={clean_city}&limit=1&appid={API_KEY}"
            geo_res = requests.get(geo_url, timeout=5).json()
            
        if not geo_res:
            return f"❓ 找不到「{city}」的地點資訊。"

        lat, lon = geo_res[0]['lat'], geo_res[0]['lon']
        # 優先抓取繁體中文地名
        location_name = geo_res[0].get('local_names', {}).get('zh', geo_res[0]['name'])

        # 4. 獲取氣象
        w_url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={API_KEY}&units=metric&lang=zh_tw"
        w_data = requests.get(w_url, timeout=5).json()
        
        temp = w_data.get('main', {}).get('temp', "--")
        desc = w_data.get('weather', [{}])[0].get('description', "未知")

        # 5. 空氣品質 (獨立 try，出錯不影響主程式)
        aqi_desc = "暫無資料"
        try:
            aqi_url = f"http://api.openweathermap.org/data/2.5/air_pollution?lat={lat}&lon={lon}&appid={API_KEY}"
            aqi_res = requests.get(aqi_url, timeout=3).json()
            aqi_val = aqi_res['list'][0]['main']['aqi']
            aqi_map = {1: "良好", 2: "普通", 3: "不健康(敏感)", 4: "不健康", 5: "危害"}
            aqi_desc = aqi_map.get(aqi_val, "未知")
        except Exception as a_e:
            print(f">>> [AQI Error] {a_e}")

        # 6. 繁體補丁與格式化
        desc = desc.replace("多云", "多雲").replace("阴", "陰").replace("阵雨", "陣雨")
        location_name = location_name.replace("台", "臺") # 回傳給使用者時用正式字
        
        tw_time = datetime.utcnow() + timedelta(hours=8)
        date_str = tw_time.strftime("%Y-%m-%d")

        return (
            f"🌍 氣象連線成功 ({date_str})\n"
            f"--------------------------\n"
            f"📍 地點：{location_name}\n"
            f"🌡️ 溫度：{temp}°C\n"
            f"☁️ 狀態：{desc}\n"
            f"😷 空氣：{aqi_desc}\n"
            f"--------------------------\n"
            f"💡 建議：數據更新完成！"
        )

    except Exception as e:
        print(f">>> [CRITICAL ERROR] {e}")
        return "⚠️ 抱歉，數據處理發生問題，請再試一次。"

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        req = request.get_json(silent=True, force=True)
        query_result = req.get('queryResult', {})
        params = query_result.get('parameters', {})
        
        # --- 核心修正：多重路徑抓取地點 ---
        city = ""
        loc_param = params.get('location')
        
        if isinstance(loc_param, dict):
            # 如果 location 是物件，嘗試多個常見 Key
            city = loc_param.get('city') or loc_param.get('admin-area') or loc_param.get('subadmin-area')
        elif isinstance(loc_param, list) and loc_param:
            city = loc_param[0]
        else:
            city = str(loc_param)

        # 如果參數抓不到，最後保險：拿對話原文
        final_city = city if city and city.lower() != 'none' else query_result.get('queryText', '')
        
        if not final_city:
            return jsonify({"fulfillmentText": "請問你想查詢哪個城市？"})

        reply = get_weather_info(final_city)
        return jsonify({"fulfillmentText": reply})
    except Exception as web_e:
        print(f">>> [WEBHOOK ERROR] {web_e}")
        return jsonify({"fulfillmentText": "系統忙碌中，請稍後再輸入。"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))