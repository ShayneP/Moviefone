from __future__ import annotations
from typing import Annotated, List

import logging
from dotenv import load_dotenv
import json
from movie_api import MovieAPI

from livekit import rtc
from livekit.agents import (
    AutoSubscribe,
    JobContext,
    WorkerOptions,
    cli,
    llm,
)
from livekit.agents.multimodal import MultimodalAgent
from livekit.plugins import openai
import asyncio
import aiohttp

load_dotenv(dotenv_path=".env.local")
logger = logging.getLogger("my-worker")
logger.setLevel(logging.INFO)


async def entrypoint(ctx: JobContext):
    fnc_ctx = llm.FunctionContext()
    movie_api = MovieAPI()

    @fnc_ctx.ai_callable()
    async def get_movies(
        location: Annotated[
            str, llm.TypeInfo(description="The city to get movie showtimes for")
        ],
        province: Annotated[
            str, llm.TypeInfo(description="The province/state code (e.g. 'qc' for Quebec, 'ny' for New York)")
        ],
    ):
        """Called when the user asks about movies showing in theaters. Returns the current movies showing in the specified location."""
        logger.info(f"get_movies called with location='{location}', province='{province}'")
        try:
            theatre_movies = await movie_api.get_movies(location, province)
            num_theatres = len(theatre_movies.theatres)
            logger.info(f"Returning movies for {num_theatres} theatres in '{location}', '{province}'.")

            if num_theatres == 0:
                return f"No movies found for {location}, {province}."

            # Create markdown table
            markdown = []
            for theatre in theatre_movies.theatres:
                markdown.append(f"\n### {theatre['theatre_name']}\n")
                markdown.append("| Movie | Genre | Rating | Runtime | Showtimes |")
                markdown.append("|-------|--------|---------|----------|-----------|")
                
                for movie in theatre["movies"]:
                    showtimes = ", ".join([
                        f"{showtime.start_time.strftime('%I:%M %p').lstrip('0')}" + 
                        (" (Sold Out)" if showtime.is_sold_out else f" ({showtime.seats_remaining} seats)")
                        for showtime in movie.showtimes
                    ])
                    
                    markdown.append(
                        f"| {movie.title} | {movie.genre} | {movie.rating} | {movie.runtime} mins | {showtimes} |"
                    )
                markdown.append("\n")

            return "\n".join(markdown)
        except Exception as e:
            logger.error(f"Error in get_movies: {e}")
            return f"Sorry, I couldn't get the movie listings for {location}. Please check the city and province/state names and try again."

    logger.info(f"connecting to room {ctx.room.name}")
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)
    
    participant = await ctx.wait_for_participant()

    run_multimodal_agent(ctx, participant, fnc_ctx)

    logger.info("agent started")


def run_multimodal_agent(ctx: JobContext, participant: rtc.Participant, fnc_ctx: llm.FunctionContext):
    logger.info("starting multimodal agent")

    model = openai.realtime.RealtimeModel(
        instructions=(
            "You are an assistant who helps users find movies showing in  in Canada. "
            "When users ask about movies, make sure to ask for both the city and province. "
            "For Canadian provinces, use codes like 'qc' for Quebec."
        ),
        modalities=["audio", "text"],
    )
    assistant = MultimodalAgent(model=model, fnc_ctx=fnc_ctx)
    assistant.start(ctx.room, participant)

    session = model.sessions[0]
    session.conversation.item.create(
        llm.ChatMessage(
            role="assistant",
            content="Please begin the interaction with the user in a manner consistent with your instructions.",
        )
    )
    session.response.create()


if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
        )
    )
