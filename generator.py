import pandas as pd
import re
from datetime import datetime

def preprocess_weather_data(period: dict, user_time_str: str) -> dict:   
    try:
        period_start = datetime.fromisoformat(period['startTime'].replace('Z', '+00:00'))
        hour = period_start.hour
        
        if 5 <= hour < 12:
            period_name = "Morning"
        elif 12 <= hour < 17:
            period_name = "Afternoon"
        elif 17 <= hour < 21:
            period_name = "Evening"
        else:
            period_name = "Night"
        
        temperature = int(period['temperature'])
        weather_short_desc = period['shortForecast'].lower()
        
        forecast_condition = "cloudy"
        if "snow" in weather_short_desc:
            forecast_condition = "snow"
        elif "rain" in weather_short_desc or "showers" in weather_short_desc or "thunderstorm" in weather_short_desc:
            forecast_condition = "rain"
        elif "sunny" in weather_short_desc or "clear" in weather_short_desc or "partly sunny" in weather_short_desc:
            forecast_condition = "sunny"
        elif "cloudy" in weather_short_desc or "overcast" in weather_short_desc or "mostly cloudy" in weather_short_desc:
            forecast_condition = "cloudy"
        elif "windy" in weather_short_desc or "breezy" in weather_short_desc:
            forecast_condition = "wind"

        is_rainy = (forecast_condition == "rain")
        weather_long_desc = period.get('detailedForecast', period['shortForecast']).lower()
        is_windy = "wind" in weather_long_desc or "gust" in weather_long_desc
 
        wind_speed_str = period.get('windSpeed', '').lower()
        wind_speed_match = re.search(r'(\d+)\s+mph', wind_speed_str)
        if wind_speed_match:
            wind_speed = int(wind_speed_match.group(1))
            if wind_speed >= 15:  # Arbitrary thresh for actually being windy
                is_windy = True
                if forecast_condition not in ["rain", "snow"]:
                    forecast_condition = "wind"
        
        if "wind" in weather_short_desc or "breezy" in weather_short_desc:
            is_windy = True

        return {
            "period_name": period_name,
            "temperature": temperature,
            "forecast_condition": forecast_condition,
            "is_rainy": is_rainy,
            "is_windy": is_windy
        }

    except Exception as e:
        print(f"Error processing weather data: {e}")
        return {}

def preprocess_outfits_data(outfits_data: dict) -> pd.DataFrame:
    try:
        outfits_list = outfits_data['outfits']
        
        for item in outfits_list:
            item['temp_min'] = item['temperature_range']['min']
            item['temp_max'] = item['temperature_range']['max']
            del item['temperature_range']
            
        df = pd.DataFrame(outfits_list)
        return df

    except Exception as e:
        print(f"Error processing outfits data: {e}")
        return pd.DataFrame()

def recommend_outfit(
    weather_conditions: dict, 
    outfits_df: pd.DataFrame, 
    user_genres: list = None
) -> dict:
    if not weather_conditions or outfits_df.empty:
        return {"Error": "Could not generate recommendation."}

    temp = weather_conditions['temperature']
    forecast = weather_conditions['forecast_condition']
    rain = weather_conditions['is_rainy']
    wind = weather_conditions['is_windy']
    
    # 1. filter by temp
    temp_ok = (outfits_df['temp_min'] <= temp) & (outfits_df['temp_max'] >= temp)

    # 2. filter by forecast condition
    forecast_ok = outfits_df['suitable_forecasts'].apply(lambda x: forecast in x)

    # 3. filter by rain
    rain_ok = outfits_df['rain'].apply(lambda r: rain in r if isinstance(r, list) else rain == r)

    # 4. filter by wind
    wind_ok = outfits_df['wind'].apply(lambda w: wind in w if isinstance(w, list) else wind == w)

    # 5. filter by genre
    if user_genres:
        user_genres_lower = [g.lower() for g in user_genres]
        
        # checks if ANY of the user's preferred genres are in the item's genre list
        genre_ok = outfits_df['genre'].apply(
            lambda outfit_genres: any(g in outfit_genres for g in user_genres_lower)
        )
    else:
        # if no genre specified, do not filter by it
        genre_ok = pd.Series(True, index=outfits_df.index)

    # combines filters
    candidates_df = outfits_df[temp_ok & forecast_ok & rain_ok & wind_ok & genre_ok]
    print(f"DEBUG: Total candidates after all filters: {len(candidates_df)}")

    final_outfit = {}
    # check if its a full-body item
    full_body_items = candidates_df[candidates_df['category'] == 'full-body']
    top_items = candidates_df[candidates_df['category'] == 'top']
    bottom_items = candidates_df[candidates_df['category'] == 'bottom']
 
    if not full_body_items.empty:
        final_outfit['full-body'] = full_body_items.sample(1)['name'].values[0]
    else:
        # top and bottom items
        if not top_items.empty:
            final_outfit['top'] = top_items.sample(1)['name'].values[0]
            
        if not bottom_items.empty:
            final_outfit['bottom'] = bottom_items.sample(1)['name'].values[0]

    # other categories
    for category in ['shoes', 'layer', 'accessories', 'weather-specific']:
        items = candidates_df[candidates_df['category'] == category]
        if not items.empty:
            final_outfit[category] = items.sample(1)['name'].values[0]
            
    if not final_outfit:
        return {"Message": "No suitable outfit items found for these conditions and genres."}

    return final_outfit 