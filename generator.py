import pandas as pd
import re
from datetime import datetime

def preprocess_weather_data(weather_data: dict, user_time_str: str) -> dict:
    try:
        
        # make datetime objects for each period start time
        start_times = [
            datetime.fromisoformat(t) 
            for t in weather_data['time']['startValidTime']
        ]

        user_dt = datetime.fromisoformat(user_time_str)
        
        # finds the latest period that starts before or at user_dt
        period_index = 0
        for i, start_time in enumerate(start_times):
            if user_dt >= start_time:
                period_index = i #correct start time index in json file
            else:
                break

        period_name = weather_data['time']['startPeriodName'][period_index]

        # weather data for that period
        period_data = weather_data['data']
        
        # get temp
        temperature = int(period_data['temperature'][period_index])
        
        # main forecast keyword
        weather_short_desc = period_data['weather'][period_index].lower()
        
        forecast_condition = "cloudy" # default to cloudy,,,, 
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

        # make rain boolean
        is_rainy = (forecast_condition == "rain")
        
        # make wind boolean
        weather_long_desc = weather_data['data']['text'][period_index].lower()
        is_windy = "wind" in weather_long_desc or "gust" in weather_long_desc
        
        wind_speed_match = re.search(r'(\d+)\s+mph', weather_long_desc)
        if wind_speed_match:
            wind_speed = int(wind_speed_match.group(1))
            if wind_speed >= 15: #wind speed threshold to be "windy"
                is_windy = True
                if forecast_condition not in ["rain", "snow"]:
                    forecast_condition = "wind" 

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
    
    final_outfit = {}
    # check if its a full-body item
    full_body_items = candidates_df[candidates_df['category'] == 'full-body']
    
    if not full_body_items.empty:
        final_outfit['full-body'] = full_body_items.sample(1)['name'].values[0]
    else:
        # top and bottom items
        top_items = candidates_df[candidates_df['category'] == 'top']
        if not top_items.empty:
            final_outfit['top'] = top_items.sample(1)['name'].values[0]
            
        bottom_items = candidates_df[candidates_df['category'] == 'bottom']
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

# if __name__ == "__main__":
    
#     # user inputs
#     USER_TIME_INPUT = "2025-11-05T14:00:00-05:00"
#     USER_GENRE_INPUT = ["Casual", "Masculine"] 
#     # end
    
#     try:
#         with open('weather.json', 'r') as f:
#             weather_data = json.load(f)
        
#         with open('outfits.json', 'r') as f:
#             outfits_data = json.load(f)
            
#     except FileNotFoundError as e:
#         print(f"Error: {e}. Make sure weather.json and outfits.json are in the same directory.")
#         exit()
        
#     print(f"processing weather for user time {USER_TIME_INPUT}...")
#     conditions = preprocess_weather_data(weather_data, USER_TIME_INPUT)
#     print(f"Weather conditions for '{conditions.get('period_name')}': {conditions}")
    
#     print("\nprocessing outfit database ")
#     outfits_df = preprocess_outfits_data(outfits_data)
#     print(f"{len(outfits_df)} outfit items ")
    
#     print(f"\ngenerating recommendation for genres {USER_GENRE_INPUT}...")
#     recommended_outfit = recommend_outfit(conditions, outfits_df, USER_GENRE_INPUT)
    
#     # 3. Output
#     print("\n--- OUTFIT RAHHHH ---")
#     if "Error" in recommended_outfit or "Message" in recommended_outfit:
#         print(recommended_outfit)
#     else:
#         for category, item in recommended_outfit.items():
#             print(f"  - {category.capitalize()}: {item}")
#     print("-------------------------------")