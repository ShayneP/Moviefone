from dataclasses import dataclass
from datetime import datetime
import json
import requests
from typing import List, Optional, Dict, Any
import logging
import asyncio
import aiohttp

logger = logging.getLogger(__name__)

@dataclass
class Showtime:
    start_time: datetime
    seats_remaining: int
    is_sold_out: bool

@dataclass
class Movie:
    title: str
    genre: str
    rating: str
    runtime: int
    showtimes: List[Showtime]

@dataclass
class TheatreMovies:
    theatres: List[Dict[str, Any]]  # List of theatre data with movies

class MovieAPI:
    def __init__(self):
        self.api_key = "dcdac5601d864addbc2675a2e96cb1f8"
        self.base_url = "https://apis.cineplex.com/prod/cpx/theatrical/api/v1"
        self.theatres = []
        
        try:
            # Load theatres data
            with open("theatres.json", "r", encoding='utf-8') as f:
                data = json.load(f)
                # Combine all theatre lists into one list for searching
                if isinstance(data, dict):
                    if "nearbyTheatres" in data:
                        self.theatres.extend(data["nearbyTheatres"])
                        logger.info(f"Loaded {len(data['nearbyTheatres'])} nearby theatres from data.")
                    if "otherTheatres" in data:
                        self.theatres.extend(data["otherTheatres"])
                        logger.info(f"Loaded {len(data['otherTheatres'])} other theatres from data.")
                    else:
                        logger.warning("No 'otherTheatres' found in theatres.json.")
                elif isinstance(data, list):
                    self.theatres.extend(data)
                    logger.info(f"Loaded {len(data)} theatres from data.")
                else:
                    logger.error("Theatres data is not in expected format (neither dict nor list).")
                    raise ValueError("Invalid theatres data format")
                
                logger.info(f"Total theatres loaded: {len(self.theatres)}")
        except Exception as e:
            logger.error(f"Error loading theatres.json: {e}")
            raise

    def _get_theatre_info(self, city: str, province: str) -> List[Dict[str, Any]]:
        """Find all theatre info for a given city and province."""
        city_lower = city.lower()
        province_lower = province.lower()
        matching_theatres = []
        
        for theatre in self.theatres:
            try:
                theatre_city = theatre["location"]["city"].lower()
                theatre_province = theatre["location"]["provinceCode"].lower()
                
                if theatre_city == city_lower and theatre_province == province_lower:
                    matching_theatres.append({
                        "id": theatre["theatreId"],
                        "name": theatre.get("theatreName", "Unknown Theatre")
                    })
            except KeyError as e:
                logger.warning(f"Missing expected field in theatre data: {e}")
                continue
                
        logger.info(f"Found {len(matching_theatres)} theatres matching city '{city}' and province '{province}'.")
        return matching_theatres

    async def _fetch_theatre_movies(self, theatre_info: Dict[str, Any], date: datetime) -> Optional[Dict[str, Any]]:
        """Fetch movies for a specific theatre."""
        formatted_date = date.strftime("%m/%d/%Y")
        logger.info(f"Fetching movies for theatre: {theatre_info['name']} (ID: {theatre_info['id']})")
        
        url = f"{self.base_url}/showtimes"
        params = {
            "language": "en",
            "locationId": theatre_info["id"],
            "date": formatted_date
        }
        headers = {
            "Ocp-Apim-Subscription-Key": self.api_key
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, headers=headers) as response:
                    if response.status != 200:
                        logger.error(f"API request failed for theatre {theatre_info['name']} with status {response.status}")
                        return None  # Return None to indicate failure
                    
                    data = await response.json()
                    movies = []
                    
                    try:
                        if not data or not isinstance(data, list) or not data[0].get('dates'):
                            logger.error(f"Unexpected API response format for theatre {theatre_info['name']}")
                            raise ValueError("Invalid API response format")

                        movies_data = data[0]['dates'][0].get('movies', [])
                        
                        for movie_data in movies_data:
                            showtimes = []
                            seen_times = set()
                            
                            for exp in movie_data.get('experiences', []):
                                for session in exp.get('sessions', []):
                                    start_time = datetime.strptime(session['showStartDateTime'], "%Y-%m-%dT%H:%M:%S")
                                    
                                    time_key = start_time.strftime("%H:%M")
                                    if time_key in seen_times:
                                        continue
                                    seen_times.add(time_key)
                                    
                                    showtime = Showtime(
                                        start_time=start_time,
                                        seats_remaining=session.get('seatsRemaining', 0),
                                        is_sold_out=session.get('isSoldOut', False)
                                    )
                                    showtimes.append(showtime)
                            
                            showtimes.sort(key=lambda x: x.start_time)
                            
                            genres = ", ".join(movie_data.get("genres", [])) if movie_data.get("genres") else "N/A"
                            movies.append(Movie(
                                title=movie_data.get("name", "Unknown"),
                                genre=genres,
                                rating=movie_data.get("localRating", "N/A"),
                                runtime=movie_data.get("runtimeInMinutes", 0),
                                showtimes=showtimes
                            ))
                        
                        # After processing all movies, log the results in table format
                        if movies:
                            log_lines = [
                                f"\nTheatre: {theatre_info['name']}",
                                "\n| Movie | Genre | Rating | Runtime | Showtimes |",
                                "|-------|--------|---------|----------|-----------|"
                            ]
                            
                            for movie in movies:
                                showtimes = ", ".join([
                                    f"{st.start_time.strftime('%I:%M %p').lstrip('0')}" +
                                    (" (Sold Out)" if st.is_sold_out else f" ({st.seats_remaining} seats)")
                                    for st in movie.showtimes
                                ])
                                
                                log_lines.append(
                                    f"| {movie.title} | {movie.genre} | {movie.rating} | "
                                    f"{movie.runtime} mins | {showtimes} |"
                                )
                            
                            logger.info("\n".join(log_lines) + "\n")
                        
                        return {
                            "theatre_name": theatre_info["name"],
                            "movies": movies
                        }
                    except (KeyError, IndexError) as e:
                        logger.error(f"Unexpected API response format for theatre {theatre_info['name']}: {e}")
                        return None  # Return None to indicate failure
        except Exception as e:
            logger.error(f"Exception occurred while fetching movies for theatre {theatre_info['name']}: {e}")
            return None  # Return None to indicate failure

    async def get_movies(self, city: str, province: str, date: Optional[datetime] = None) -> TheatreMovies:
        """Get movies showing at all theatres in the specified location."""
        theatres_info = self._get_theatre_info(city, province)
        if not theatres_info:
            raise ValueError(f"No theatres found in {city}, {province}")

        if date is None:
            date = datetime.now()
        
        # Fetch movies from all theatres concurrently
        tasks = [self._fetch_theatre_movies(theatre, date) for theatre in theatres_info]
        theatre_results = await asyncio.gather(*tasks)
        
        # Filter out any None results due to failed fetches
        successful_theatre_results = [result for result in theatre_results if result is not None]
        
        logger.info(f"Successfully fetched movies from {len(successful_theatre_results)} out of {len(theatres_info)} theatres in {city}")
        return TheatreMovies(theatres=successful_theatre_results)
