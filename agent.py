from __future__ import annotations
from typing import Annotated
from pydantic import Field

import logging
from dotenv import load_dotenv
from movie_api import MovieAPI

from livekit.agents import (
    JobContext,
    WorkerOptions,
    cli,
)
from livekit.agents.llm import function_tool
from livekit.agents.voice import Agent, AgentSession
from livekit.plugins import deepgram, openai, silero

from datetime import datetime


class MovieAssistant(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions="You are an assistant who helps users find movies showing in Canada. "
            f"Today's date is {datetime.now().strftime('%Y-%m-%d')}. "
            "You can help users find movies for specific dates - if they use relative terms like 'tomorrow' or "
            "'next Friday', convert those to YYYY-MM-DD format based on today's date. Don't check anything "
            "unless the user asks. Only give the minimum information needed to answer the question the user asks.",
        )

    async def on_enter(self) -> None:
        self._movie_api = self.session.userdata["movie_api"]
        await self.session.generate_reply(
            instructions="Greet the user. Then, ask them which movie they'd like to see and which city and province they're in."
        )

    @function_tool()
    async def get_movies(
        self,
        location: Annotated[
            str, Field(description="The city to get movie showtimes for")
        ],
        province: Annotated[
            str,
            Field(
                description="The province/state code (e.g. 'qc' for Quebec, 'on' for Ontario)"
            ),
        ],
        show_date: Annotated[
            str,
            Field(
                description="The date to get showtimes for in YYYY-MM-DD format. If not provided, defaults to today."
            ),
        ] = None,
    ):
        """Called when the user asks about movies showing in theaters. Returns the movies showing in the specified location for the given date."""
        logger.info(
            f"get_movies called with location='{location}', province='{province}', date='{show_date}'"
        )
        try:
            target_date = (
                datetime.strptime(show_date, "%Y-%m-%d")
                if show_date
                else datetime.now()
            )
            theatre_movies = await self._movie_api.get_movies(
                location, province, target_date
            )
            num_theatres = len(theatre_movies.theatres)
            logger.info(
                f"Returning movies for {num_theatres} theatres in '{location}', '{province}'."
            )

            if num_theatres == 0:
                return f"No movies found for {location}, {province}."

            output = []
            for theatre in theatre_movies.theatres:
                output.append(f"\n{theatre['theatre_name']}")
                output.append("-------------------")

                for movie in theatre["movies"]:
                    showtimes = ", ".join(
                        [
                            f"{showtime.start_time.strftime('%I:%M %p').lstrip('0')}"
                            + (
                                " (Sold Out)"
                                if showtime.is_sold_out
                                else f" ({showtime.seats_remaining} seats)"
                            )
                            for showtime in movie.showtimes
                        ]
                    )

                    output.append(f"• {movie.title}")
                    output.append(f"  Genre: {movie.genre}")
                    output.append(f"  Rating: {movie.rating}")
                    output.append(f"  Runtime: {movie.runtime} mins")
                    output.append(f"  Showtimes: {showtimes}")
                    output.append("")

                output.append("-------------------\n")

            return "\n".join(output)
        except Exception as e:
            logger.error(f"Error in get_movies: {e}")
            return f"Sorry, I couldn't get the movie listings for {location}. Please check the city and province/state names and try again."


load_dotenv()
logger = logging.getLogger("movie-finder")
logger.setLevel(logging.INFO)


async def entrypoint(ctx: JobContext):
    await ctx.connect()
    logger.info(f"connecting to room {ctx.room.name}")
    userdata = {"movie_api": MovieAPI()}
    session = AgentSession(
        userdata=userdata,
        stt=deepgram.STT(),
        llm=openai.LLM(),
        tts=deepgram.TTS(),
        vad=silero.VAD.load(),
    )

    await session.start(agent=MovieAssistant(), room=ctx.room)

    logger.info("agent started")


if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
        )
    )
