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
    except Exception:
        advice_list.append("😊 祝您今天有個愉快的一天！")

    # 確保至少回傳兩條建議，並用空格隔開
    return " ".join(advice_list[:2])

def get_weather_info(city_name, target_date_str=None):
    if not API_KEY: return "⚠️ 未偵測到 API 金鑰"
    
    raw_query = city_name.replace("天氣", "").replace("如何", "").strip()
    search_variants = [f"{raw_query},TW"]
    if "板橋" in raw_query: search_variants.insert(0, "Banqiao,TW")
    if "中和" in raw_query: search_variants.insert(0, "Zhonghe,TW")

    tw_now = datetime.now(timezone(timedelta(hours=8)))
    today_str = tw_now.strftime("%Y-%m-%d")
    is_query_today = (not target_date_str or target_date_str == today_str)
    display_date = target_date_str if target_date_str else today_str

    try:
        geo_res = None
        for q in search_variants:
            geo_url = f"http://api.openweathermap.org/geo/1.0/direct?q={q}&limit=5&appid={API_KEY}"
            geo_res = requests.get(geo_url, timeout=5).json()
            if geo_res: break
        
        if not geo_res: return f"❓ 找不到「{raw_query}」的地點。"

        target = next((item for item in geo_res if (21.8 < item['lat'] < 25.5) and (119.5 < item['lon'] < 122.5)), geo_res[0])
        lat, lon = target['lat'], target['lon']
        location_name = target.get('local_names', {}).get('zh', target['name'])
        country_code = target.get('country', 'TW')

        # 抓取主天氣數據
        if is_query_today:
            url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={API_KEY}&units=metric&lang=zh_tw"
            data = requests.get(url, timeout=5).json()
            temp, desc = data['main']['temp'], data['weather'][0]['description']
        else:
            url = f"https://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={API_KEY}&units=metric&lang=zh_tw"
            data = requests.get(url, timeout=5).json()
            target_entry = next((e for e in data['list'] if display_date in e['dt_txt']), data['list'][0])
            temp, desc = target_entry['main']['temp'], target_entry['weather'][0]['description']

        # 建立回覆字串頭部
        res = f"🌍 氣象服務連線成功！\n({display_date})\n--------------------------\n📍 地點：{final_fix_text(location_name)} [{country_code}]\n🌡️ 溫度：{temp}°C\n☁️ 狀態：{final_fix_text(desc)}\n"
        
        # --- 重點：空氣品質處理 ---
        if is_query_today:
            try:
                aqi_url = f"http://api.openweathermap.org/data/2.5/air_pollution?lat={lat}&lon={lon}&appid={API_KEY}"
                aqi_res = requests.get(aqi_url, timeout=3).json()
                pm25 = aqi_res['list'][0]['components'].get('pm2_5', 0)
                
                if pm25 <= 15.4: aqi_str = "良好 (適合戶外活動)"
                elif pm25 <= 35.4: aqi_str = "普通 (敏感族群注意)"
                else: aqi_str = "對敏感族群不健康 (建議戴口罩)"
                
                res += f"🌬️ 空氣品質：{aqi_str}\n"
            except:
                res += "🌬️ 空氣品質：暫時無法取得數據\n"
        
        # --- 重點：智慧建議處理 ---
        smart_advice = get_smart_advice(temp, desc)
        res += f"--------------------------\n💡 建議：{smart_advice}\n--------------------------"
        
        return res
    except Exception as e:
        print(f"Error: {e}") # 在 Render 的 Log 裡可以看到具體錯誤
        return "⚠️ 獲取數據時發生錯誤，請稍後再試。"