def get_weather_info(user_input_city, is_today=True):
    if not API_KEY: return "⚠️ 未偵測到 WEATHER_API_KEY"

    # 1. 搜尋預處理
    display_city = user_input_city.strip()
    search_city = display_city.replace("臺", "台")
    
    # 核心修正：針對新北市，搜尋詞改用英文全名，並標記搜尋意圖
    is_requesting_new_taipei = "新北" in display_city
    if is_requesting_new_taipei:
        search_query = "New Taipei City,TW"
    else:
        search_query = f"{search_city},TW" if not any(c.isalpha() for c in search_city) else search_city

    try:
        # 2. 地點搜尋 (抓取多個結果篩選台灣座標)
        geo_url = f"http://api.openweathermap.org/geo/1.0/direct?q={search_query}&limit=5&appid={API_KEY}"
        geo_res = requests.get(geo_url, timeout=3).json()
        
        if not geo_res:
            return f"❓ 找不到「{user_input_city}」的地點資訊"

        # 3. 台灣優先篩選邏輯 (物理座標鎖定)
        target = geo_res[0]
        is_in_taiwan = False
        for item in geo_res:
            lat, lon = item['lat'], item['lon']
            if (21.8 < lat < 25.5) and (119.5 < lon < 122.5):
                target = item
                is_in_taiwan = True
                break

        lat, lon = target['lat'], target['lon']
        country = "TW" if is_in_taiwan else target.get('country', '??')

        # 4. 地名顯示優化：強制覆寫新北名稱
        api_name = target.get('local_names', {}).get('zh', target['name'])
        location_name = final_fix_text(api_name)
        
        # --- 解決新北變台北的關鍵代碼 ---
        if is_requesting_new_taipei:
            location_name = "新北市"
        elif "板橋" in display_city:
            location_name = "板橋區"
        # -----------------------------

        # 5. 抓取天氣數據
        w_url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={API_KEY}&units=metric&lang=zh_tw"
        w_data = requests.get(w_url, timeout=3).json()
        
        temp = w_data.get('main', {}).get('temp', "--")
        desc = final_fix_text(w_data.get('weather', [{}])[0].get('description', "未知"))

        # 6. 建議
        suggest = "😊 氣溫舒適，是出門的好天氣。"
        if "雨" in desc: suggest = "☔ 記得帶把傘，注意安全。"
        elif isinstance(temp, (int, float)):
            if temp >= 28: suggest = "🥵 天氣炎熱，請多補充水分。"
            elif temp <= 18: suggest = "🧥 氣溫偏低，記得穿件外套。"

        # 7. 格式化輸出
        date_str = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d")
        
        res_text = (
            f"🌍 氣象服務連線成功！\n"
            f"({date_str})\n"
            f"--------------------------\n"
            f"📍 地點：{location_name} [{country}]\n"
            f"🌡️ 溫度：{temp}°C\n"
            f"☁️ 狀態：{desc}\n"
        )
        
        if is_today:
            aqi_val = get_aqi_info(lat, lon)
            res_text += f"🌬️ 空氣品質：{aqi_val}\n"
            
        res_text += (
            f"--------------------------\n"
            f"💡 建議：{suggest}\n"
            f"--------------------------"
        )
        return res_text
    except:
        return "⚠️ 系統連線異常，請稍後再試。"