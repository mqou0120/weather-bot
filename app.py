def get_weather_info(city_name, target_date_str=None):
    if not API_KEY: return "⚠️ 未偵測到 API 金鑰"
    
    # 1. 整理搜尋字串：處理「板橋」這種容易失敗的關鍵字
    raw_query = city_name.replace("天氣", "").replace("如何", "").strip()
    
    # 建立搜尋優先順序清單 (解決板橋搜尋不到的問題)
    search_variants = [f"{raw_query},TW"]
    if "板橋" in raw_query:
        search_variants.insert(0, "Banqiao,TW") # 優先用英文拼音搜尋板橋
    if "中和" in raw_query:
        search_variants.insert(0, "Zhonghe,TW")

    tw_now = datetime.now(timezone(timedelta(hours=8)))
    today_str = tw_now.strftime("%Y-%m-%d")
    is_query_today = True if (not target_date_str or target_date_str == today_str) else False
    display_date = target_date_str if target_date_str else today_str

    try:
        geo_res = None
        # 嘗試多種搜尋變體直到找到結果
        for q in search_variants:
            geo_url = f"http://api.openweathermap.org/geo/1.0/direct?q={q}&limit=5&appid={API_KEY}"
            geo_res = requests.get(geo_url, timeout=5).json()
            if geo_res: break
        
        if not geo_res:
            return f"❓ 找不到「{raw_query}」的地點資訊，請試著輸入更具體的名稱（例如：新北市板橋區）。"

        # 2. 嚴格經緯度過濾
        target = None
        for item in geo_res:
            lat, lon = item['lat'], item['lon']
            if (21.8 < lat < 25.5) and (119.5 < lon < 122.5):
                target = item
                break
        
        if not target: target = geo_res[0]

        lat, lon = target['lat'], target['lon']
        # 取得中文名稱，若無則顯示原始名稱
        location_name = target.get('local_names', {}).get('zh', target['name'])
        location_name = final_fix_text(location_name)
        country_code = target.get('country', 'TW') # 獲取國家代碼

        # 3. 抓取天氣數據 (同前...)
        if is_query_today:
            url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={API_KEY}&units=metric&lang=zh_tw"
            data = requests.get(url, timeout=5).json()
            temp = data['main']['temp']
            desc = data['weather'][0]['description']
        else:
            url = f"https://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={API_KEY}&units=metric&lang=zh_tw"
            data = requests.get(url, timeout=5).json()
            target_entry = data['list'][0]
            for entry in data['list']:
                if display_date in entry['dt_txt']:
                    target_entry = entry
                    if "12:00:00" in entry['dt_txt']: break
            temp = target_entry['main']['temp']
            desc = target_entry['weather'][0]['description']

        smart_advice = get_smart_advice(temp, desc)
        
        # 4. 恢復包含國家代碼的輸出格式
        res = f"🌍 氣象服務連線成功！\n({display_date})\n--------------------------\n📍 地點：{location_name} [{country_code}]\n🌡️ 溫度：{temp}°C\n☁️ 狀態：{final_fix_text(desc)}\n"
        
        if is_query_today:
            aqi_url = f"http://api.openweathermap.org/data/2.5/air_pollution?lat={lat}&lon={lon}&appid={API_KEY}"
            aqi_data = requests.get(aqi_url, timeout=3).json()
            pm25 = aqi_data['list'][0]['components'].get('pm2_5', 0)
            aqi_str = "良好" if pm25 <= 15.4 else "普通" if pm25 <= 35.4 else "對敏感族群不健康"
            res += f"🌬️ 空氣品質：{aqi_str}\n"
            
        res += f"--------------------------\n💡 建議：{smart_advice}\n--------------------------"
        return res
    except Exception as e:
        return "⚠️ 獲取數據時發生錯誤。"