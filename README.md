# Moviefone AI Assistant

This AI Assistant is a LiveKit & OpenAI powered agent that helps users find movie showtimes at theaters across Canada.

<img src="kramer.png" alt="Moviefone Kramer" width="423" height="340">

## Features

- **Natural Language Interface**: Users can ask about movies in their city using a conversation with a Realtime agent.
- **Movie Information**: Provides movie details including:
  - Movie title and genre
  - Rating and runtime
  - Available showtimes
  - Seat availability for each showing
- **Multi-Theatre Support**: Fetches showtimes from all theaters in the specified location
- **Real-Time Data**: Uses the Cineplex API to get current, up-to-date showtimes and seat availability


## Prerequisites

- Python 3.8 or higher
- LiveKit account and credentials
- OpenAI API key

## Installation

1. Clone the repository

2. Install dependencies
`pip install -r requirements.txt`

3. Create a `.env.local` file with your credentials:
```
LIVEKIT_API_KEY=your_api_key
LIVEKIT_API_SECRET=your_api_secret
OPENAI_API_KEY=your_openai_key
```

## Usage
1. Start the AI assistant:
`python agent.py dev`

2. Create a [sandbox](https://docs.livekit.io/home/cloud/sandbox/) to connect to your agent

3. Interact with the assistant by asking about movies. For example:
   - "What movies are playing in Toronto?"
   - "Show me showtimes in Montreal"

The assistant will ask for any missing information (like province/state) and return a formatted table of movies and showtimes.

## Response Format

The assistant returns movie information in markdown tables to make it easier for the LLM to parse the data:

### Example Theatre
| Movie | Genre | Rating | Runtime | Showtimes |
|-------|--------|---------|----------|-----------|
| Example Movie | Action | PG-13 | 120 mins | 1:30 PM (45 seats), 4:15 PM (Sold Out) |

## Project Structure

- `agent.py`: Main application file containing the LiveKit agent implementation
- `movie_api.py`: Handles communication with the Cineplex API
- `theatres.json`: Database of theater locations and IDs, to limit the number of API calls / latency from the bot (since the theaters don't change very often)

## Logging

The app logs detailed information about:
- Theater searches
- Movie fetching progress
- API responses
- Errors and exceptions

Logs are formatted in an easy-to-read table format for better debugging.

## Error Handling

The assistant handles various error cases:
- Invalid city/province combinations
- API communication issues
- Missing theater data
- Invalid response formats

## 