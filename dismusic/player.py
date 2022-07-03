import asyncio
import os

import async_timeout
import discord
from discord.ext import commands
from wavelink import Player

from ._classes import Loop
from .errors import InvalidLoopMode, NotEnoughSong, NothingIsPlaying


class DisPlayer(Player):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.queue = asyncio.Queue()
        self.loop = Loop.NONE  # CURRENT, PLAYLIST
        self.bound_channel = None
        self.track_provider = "yt"

    async def destroy(self) -> None:
        self.queue = None

        await super().stop()
        await super().disconnect()

    async def do_next(self) -> None:
        if self.is_playing():
            return

        timeout = int(os.getenv("DISMUSIC_TIMEOUT", 300))

        try:
            with async_timeout.timeout(timeout):
                track = await self.queue.get()
        except asyncio.TimeoutError:
            if not self.is_playing():
                await self.destroy()

            return

        self._source = track
        await self.play(track)
        self.client.dispatch("dismusic_track_start", self, track)
        await self.invoke_player()

    async def set_loop(self, loop_type: str) -> None:
        if not self.is_playing():
            raise NothingIsPlaying("<:auroraCross:979611376819503125> | Not playing any track. Can't loop")

        if not loop_type:
            if Loop.TYPES.index(self.loop) >= 2:
                loop_type = "NONE"
            else:
                loop_type = Loop.TYPES[Loop.TYPES.index(self.loop) + 1]

            if loop_type == "PLAYLIST" and len(self.queue._queue) < 1:
                loop_type = "NONE"

        if loop_type.upper() == "PLAYLIST" and len(self.queue._queue) < 1:
            raise NotEnoughSong(
                "<:auroraCross:979611376819503125> | There must be 2 songs in the queue in order to use the PLAYLIST loop"
            )

        if loop_type.upper() not in Loop.TYPES:
            raise InvalidLoopMode("<:auroraCross:979611376819503125> | Loop type must be `NONE`, `CURRENT` or `PLAYLIST`.")

        self.loop = loop_type.upper()

        return self.loop

    async def invoke_player(self, ctx: commands.Context = None) -> None:
        track = self.source

        if not track:
            raise NothingIsPlaying("<:auroraCross:979611376819503125>| Player is not playing anything.")

        embed = discord.Embed(
            title=track.title, url=track.uri, color=discord.Color(0x2F3136)
        )
        embed.set_author(
            name=track.author,
            url=track.uri,
            icon_url=self.client.user.display_avatar.url,
        )
        try:
            embed.set_thumbnail(url=track.thumb)
        except AttributeError:
            embed.set_thumbnail(
                url="https://images-ext-2.discordapp.net/external/gz6QANWZhvLUE7X55OZn_q_oRpe6ydyID7tj6gtVFSA/%3Fsize%3D1024/https/cdn.discordapp.com/avatars/983608716102352969/1dc824eb958462f06f17cc4f97dcc409.png"            )
        embed.add_field(
            name="Duration",
            value=f"{int(track.length // 60)}:{int(track.length % 60)}",
        )
        embed.add_field(name="Loop", value=self.loop)
        embed.add_field(name="Volume", value=self.volume)

        next_song = ""

        if self.loop == "CURRENT":
            next_song = self.source.title
        else:
            if len(self.queue._queue) > 0:
                next_song = self.queue._queue[0].title

        if next_song:
            embed.add_field(name="Next Song", value=next_song, inline=False)

        if not ctx:
            return await self.bound_channel.send(embed=embed)

        await ctx.send(embed=embed)
