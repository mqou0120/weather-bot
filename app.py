import os
import requests
from flask import Flask, request, jsonify
from datetime import datetime, timedelta, timezone

app = Flask(__name__)

# 請確保在 Render 的 Environment Variables 設定好此金鑰
API_KEY = os.environ.get("WEATHER_API_KEY")

def final_fix_text(text):
    """修正翻譯與地名用詞"""
    if not text: return ""
    mapping = {
        "板桥": "板橋", "桥": "橋", "东": "東", "东京": "東京", 
        "阴": "陰", "多云": "多雲", "阵雨": "陣雨", "臺": "台", "街道": ""
    }
    for s, t in mapping.items():
        text = text.replace(s, t)
    return text

def get_smart_advice(temp, desc):
    """根據溫度與天氣狀態提供自動化建議"""
    advice_list = []
    
    # 1. 針對天氣狀態的建議
    if any(x in desc for x in ["雨", "雷", "陣"]):
        advice_list.append("☔ 記得帶把傘出門，路面濕滑請注意安全。")
    elif any(x in desc for x in ["雲", "陰"]):
        advice_list.append("☁️ 天氣較陰沉，建議帶件輕便外套防風。")
    elif "晴" in desc:
        advice_list.append("☀️ 陽光露臉，出門別忘了防曬或戴墨鏡。")
    elif "霧" in desc:
        advice_list.append("🌫️ 能見度較低，行車請注意安全。")

    # 2. 針對溫度的建議
    try:
        t = float(temp)
        if t >= 30:
            advice_list.append("🥵 天氣炎熱，請多補充水分以防中暑。")
        elif t <= 16:
            advice_list.append("🧣 氣溫偏低，出門請做好保暖禦寒。")
        elif 17 <= t <= 24:
            advice_list.append("👕 涼爽舒適，適合穿長袖薄外套。")
        else:
            advice_list.append("😊 氣溫適中，是個適合出遊的好日子！")
    except:
        advice_list.append("😊 祝您今天有個愉快的一天！")

    return " ".join(advice_list[:2])

def get_weather_info(city_name, target_date_str=None):
    if not API_KEY: return "⚠️ 未偵測到 API 金鑰"
    
    # 清理搜尋字串
    raw_query = city_name.replace("天氣", "").replace("如何", "").replace("？", "").strip()
    
    # 建立搜尋優先順序 (解決板橋、中和搜尋不到的問題)
    search_variants = [f"{raw_query},TW"]
    if "板橋" in raw_query: search_variants.insert(0, "Banqiao,TW")
    if "中和" in raw_query: search_variants.insert(0, "Zhonghe,TW")

    # 時區處理
    tw_now = datetime.now(timezone(timedelta(hours=8)))
    today_str = tw_now.strftime("%Y-%m-%d")
    is_query_today = (not target_date_str or target_date_str == today_str)
    display_date = target_date_str if target_date_str else today_str

    try:
        # --- 步驟 1: 地理編碼搜尋 ---
        geo_res = None
        for q in search_variants:
            geo_url = f"http://api.openweathermap.org/geo/1.0/direct?q={q}&limit=5&appid={API_KEY}"
            geo_res = requests.get(geo_url, timeout=5).json()
            if geo_res: break
        
        if not geo_res: return f"❓ 找不到「{raw_query}」的地點資訊。"

        # 篩選台灣經緯度範圍
        target = next((item for item in geo_res if (21.8 < item['lat'] < 25.5) and (119.5 < item['lon'] < 122.5)), geo_res[0])
        lat, lon = target['lat'], target['lon']
        location_name = target.get('local_names', {}).get('zh', target['name'])
        country_code = target.get('country', 'TW')

        # --- 步驟 2: 抓取天氣數據 ---
        if is_query_today:
            url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={API_KEY}&units=metric&lang=zh_tw"
            data = requests.get(url, timeout=5).json()
            temp, desc = data['main']['temp'], data['weather'][0]['description']
        else:
            url = f"https://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={API_KEY}&units=metric&lang=zh_tw"
            data = requests.get(url, timeout=5).json()
            # 尋找目標日期的中午預報
            target_entry = next((e for e in data['list'] if display_date in e['dt_txt']), data['list'][0])
            for e in data['list']:
                if display_date in e['dt_txt'] and "12:00:00" in e['dt_txt']:
                    target_entry = e
                    break
            temp, desc = target_entry['main']['temp'], target_entry['weather'][0]['description']

        # --- 步驟 3: 組合回覆內容 ---
        res = f"🌍 氣象服務連線成功！\n({display_date})\n--------------------------\n📍 地點：{final_fix_text(location_name)} [{country_code}]\n🌡️ 溫度：{temp}°C\n☁️ 狀態：{final_fix_text(desc)}\n"
        
        # 只有今天才抓空氣品質
        if is_query_today:
            try:
                aqi_url = f"http://api.openweathermap.org/data/2.5/air_pollution?lat={lat}&lon={lon}&appid={API_KEY}"
                aqi_res = requests.get(aqi_url, timeout=3).json()
                pm25 = aqi_res['list'][0]['components'].get('pm2_5', 0)
                aqi_str = "良好" if pm25 <= 15.4 else "普通" if pm25 <= 35.4 else "提醒注意 (AQI較高)"
                res += f"🌬️ 空氣品質：{aqi_str}\n"
            except:
                res += "🌬️ 空氣品質：暫時無法取得數據\n"
        
        smart_advice = get_smart_advice(temp, desc)
        res += f"--------------------------\n💡 建議：{smart_advice}\n--------------------------"
        return res

    except Exception as e:
        return "⚠️ 獲取氣象數據失敗，請稍後再試。"

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        req = request.get_json(silent=True, force=True)
        query_res = req.get('queryResult', {})
        params = query_res.get('parameters', {})
        
        # 日期解析
        date_input = params.get('date-time') or params.get('date') or ""
        target_date = str(date_input).split('T')[0] if date_input else None

        # 地點解析
        city = ""
        loc_param = params.get('location')
        if isinstance(loc_param, list) and len(loc_param) > 0:
            loc_data = loc_param[0]
            city = loc_data.get('city') if isinstance(loc_data, dict) else str(loc_data)
        
        if not city or city == "None":
            city = query_res.get('queryText', '')

        reply = get_weather_info(city, target_date_str=target_date)
        return jsonify({"fulfillmentText": reply})
    except:
        return jsonify({"fulfillmentText": "⚠️ 解析請求失敗。"})

if __name__ == '__main__':
    # Render 會自動設定 PORT 環境變數
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)