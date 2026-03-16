"""
JARVIS - Weather Service
Provides real-time weather information using free APIs
"""
import json
from typing import Optional, Dict, Any, Tuple
from datetime import datetime

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


class WeatherService:
    """Weather service using wttr.in (free, no API key required)"""

    WTTR_URL = "https://wttr.in"
    OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
    GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"

    def __init__(self):
        self._cache: Dict[str, Tuple[datetime, Dict]] = {}
        self._cache_duration = 600  # 10 minutes

    def _is_cache_valid(self, key: str) -> bool:
        """Check if cached data is still valid"""
        if key not in self._cache:
            return False
        cached_time, _ = self._cache[key]
        return (datetime.now() - cached_time).total_seconds() < self._cache_duration

    def get_weather(self, location: str = "auto") -> Dict[str, Any]:
        """
        Get current weather for a location

        Args:
            location: City name or 'auto' for automatic detection

        Returns:
            Weather data dictionary
        """
        if not HAS_REQUESTS:
            return {"error": "requests library not installed", "success": False}

        cache_key = f"weather_{location}"
        if self._is_cache_valid(cache_key):
            _, data = self._cache[cache_key]
            return data

        try:
            # Use wttr.in for simple weather data
            url = f"{self.WTTR_URL}/{location}?format=j1"
            response = requests.get(url, timeout=10, headers={
                'User-Agent': 'JARVIS/1.0'
            })
            response.raise_for_status()

            data = response.json()
            result = self._parse_wttr_response(data, location)

            # Cache the result
            self._cache[cache_key] = (datetime.now(), result)

            return result

        except requests.exceptions.Timeout:
            return {"error": "Weather service timeout", "success": False}
        except requests.exceptions.RequestException as e:
            return {"error": f"Network error: {str(e)}", "success": False}
        except (json.JSONDecodeError, KeyError) as e:
            return {"error": f"Failed to parse weather data: {str(e)}", "success": False}

    def _parse_wttr_response(self, data: Dict, location: str) -> Dict[str, Any]:
        """Parse wttr.in JSON response"""
        try:
            current = data.get('current_condition', [{}])[0]
            area = data.get('nearest_area', [{}])[0]

            # Get location info
            city = area.get('areaName', [{}])[0].get('value', location)
            country = area.get('country', [{}])[0].get('value', '')
            region = area.get('region', [{}])[0].get('value', '')

            # Get weather details
            temp_c = current.get('temp_C', 'N/A')
            temp_f = current.get('temp_F', 'N/A')
            feels_like_c = current.get('FeelsLikeC', temp_c)
            feels_like_f = current.get('FeelsLikeF', temp_f)
            humidity = current.get('humidity', 'N/A')
            description = current.get('weatherDesc', [{}])[0].get('value', 'Unknown')
            wind_kmph = current.get('windspeedKmph', 'N/A')
            wind_mph = current.get('windspeedMiles', 'N/A')
            wind_dir = current.get('winddir16Point', '')
            visibility = current.get('visibility', 'N/A')
            uv_index = current.get('uvIndex', 'N/A')
            pressure = current.get('pressure', 'N/A')
            cloud_cover = current.get('cloudcover', 'N/A')

            # Get forecast
            forecast = []
            for day in data.get('weather', [])[:3]:
                date = day.get('date', '')
                max_temp_c = day.get('maxtempC', 'N/A')
                min_temp_c = day.get('mintempC', 'N/A')
                avg_temp_c = day.get('avgtempC', 'N/A')
                hourly = day.get('hourly', [])

                # Get main condition from midday
                midday = hourly[4] if len(hourly) > 4 else hourly[0] if hourly else {}
                condition = midday.get('weatherDesc', [{}])[0].get('value', 'Unknown')

                forecast.append({
                    'date': date,
                    'max_temp_c': max_temp_c,
                    'min_temp_c': min_temp_c,
                    'avg_temp_c': avg_temp_c,
                    'condition': condition
                })

            return {
                'success': True,
                'location': {
                    'city': city,
                    'region': region,
                    'country': country
                },
                'current': {
                    'temperature_c': temp_c,
                    'temperature_f': temp_f,
                    'feels_like_c': feels_like_c,
                    'feels_like_f': feels_like_f,
                    'humidity': humidity,
                    'description': description,
                    'wind_kmph': wind_kmph,
                    'wind_mph': wind_mph,
                    'wind_direction': wind_dir,
                    'visibility_km': visibility,
                    'uv_index': uv_index,
                    'pressure_mb': pressure,
                    'cloud_cover': cloud_cover
                },
                'forecast': forecast
            }

        except Exception as e:
            return {"error": f"Parse error: {str(e)}", "success": False}

    def get_weather_summary(self, location: str = "auto") -> str:
        """Get a human-readable weather summary"""
        data = self.get_weather(location)

        if not data.get('success'):
            return f"Unable to get weather: {data.get('error', 'Unknown error')}"

        loc = data['location']
        curr = data['current']

        location_str = loc['city']
        if loc['country']:
            location_str += f", {loc['country']}"

        summary = f"Current weather in {location_str}:\n"
        summary += f"  Temperature: {curr['temperature_c']}°C ({curr['temperature_f']}°F)\n"
        summary += f"  Feels like: {curr['feels_like_c']}°C\n"
        summary += f"  Condition: {curr['description']}\n"
        summary += f"  Humidity: {curr['humidity']}%\n"
        summary += f"  Wind: {curr['wind_kmph']} km/h {curr['wind_direction']}\n"

        if data.get('forecast'):
            summary += "\nForecast:\n"
            for day in data['forecast'][:3]:
                summary += f"  {day['date']}: {day['condition']}, {day['min_temp_c']}°C - {day['max_temp_c']}°C\n"

        return summary

    def format_for_speech(self, location: str = "auto") -> str:
        """Format weather for voice output"""
        data = self.get_weather(location)

        if not data.get('success'):
            return f"I couldn't get the weather information. {data.get('error', '')}"

        loc = data['location']
        curr = data['current']

        speech = f"The current weather in {loc['city']} is {curr['description'].lower()}, "
        speech += f"with a temperature of {curr['temperature_c']} degrees Celsius, "
        speech += f"feeling like {curr['feels_like_c']} degrees. "
        speech += f"Humidity is at {curr['humidity']} percent, "
        speech += f"and winds are blowing {curr['wind_direction']} at {curr['wind_kmph']} kilometers per hour."

        # Add forecast hint
        if data.get('forecast') and len(data['forecast']) > 1:
            tomorrow = data['forecast'][1]
            speech += f" Tomorrow, expect {tomorrow['condition'].lower()} with temperatures between {tomorrow['min_temp_c']} and {tomorrow['max_temp_c']} degrees."

        return speech


# Singleton instance
_weather_service: Optional[WeatherService] = None


def get_weather_service() -> WeatherService:
    """Get singleton weather service instance"""
    global _weather_service
    if _weather_service is None:
        _weather_service = WeatherService()
    return _weather_service


def get_weather(location: str = "auto") -> str:
    """Quick function to get weather summary"""
    return get_weather_service().get_weather_summary(location)


def get_weather_speech(location: str = "auto") -> str:
    """Quick function to get weather for speech"""
    return get_weather_service().format_for_speech(location)
