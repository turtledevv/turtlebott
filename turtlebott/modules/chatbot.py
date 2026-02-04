"""
AI Chatbot Module for Turtlebott
"""
import discord
from discord.ext import commands, tasks

from turtlebott.utils.logger import setup_logger
from turtlebott.config import settings

from dotenv import load_dotenv
import os
import asyncio
import aiohttp
import time
from dataclasses import dataclass, field

from google import genai
from google.genai import types

logger = setup_logger("chatbot")

load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
AI_SETTINGS = settings.config["experiments_config"]["chatbot"]

model_name = AI_SETTINGS["model"]
system_instructions = AI_SETTINGS["systemInstructions"]
temperature = AI_SETTINGS["temperature"]

# Conversation tuning
MAX_TURNS = AI_SETTINGS.get("maxTurns", 20)          # user+bot pairs
CONVO_TIMEOUT = AI_SETTINGS.get("timeoutSeconds", 900)  # 15 minutes default

client = genai.Client(api_key=GOOGLE_API_KEY)


async def fetch_bytes(url: str) -> bytes:
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            resp.raise_for_status()
            return await resp.read()


def is_image_attachment(att: discord.Attachment) -> bool:
    if not att:
        return False
    if not att.content_type:
        return False
    return att.content_type.startswith("image/")


async def attachment_to_part(att: discord.Attachment) -> types.Part:
    image_bytes = await fetch_bytes(att.url)
    return types.Part.from_bytes(
        data=image_bytes,
        mime_type=att.content_type
    )


@dataclass
class Conversation:
    root_bot_message_id: int
    latest_bot_message_id: int
    channel_id: int
    history: list = field(default_factory=list)  # list[str | types.Part]
    last_activity: float = field(default_factory=lambda: time.time())


class Chatbot(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        # root_bot_message_id -> Conversation
        self.conversations: dict[int, Conversation] = {}

        # any_bot_message_id_in_convo -> root_bot_message_id
        # (lets us map replies to the right conversation fast)
        self.message_to_root: dict[int, int] = {}

        self.cleanup_task.start()

    def cog_unload(self):
        self.cleanup_task.cancel()

    def _touch(self, convo: Conversation):
        convo.last_activity = time.time()

    def _trim_history(self, convo: Conversation):
        """
        Keep only the last MAX_TURNS turns.
        A "turn" here is: user prompt + bot response.
        Since we store plain strings/parts in a flat list, we’ll just cap size.
        """
        # Rough cap: each turn adds ~2 items (user + bot).
        max_items = max(4, MAX_TURNS * 2)
        if len(convo.history) > max_items:
            convo.history = convo.history[-max_items:]

    def _register_bot_message(self, convo: Conversation, message_id: int):
        convo.latest_bot_message_id = message_id
        self.message_to_root[message_id] = convo.root_bot_message_id

    async def _generate(self, contents: list):
        return await asyncio.to_thread(
            client.models.generate_content,
            model=model_name,
            config=types.GenerateContentConfig(
                temperature=temperature,
                system_instruction=system_instructions
            ),
            contents=contents
        )

    async def _handle_prompt(
        self,
        ctx_or_message,
        prompt: str,
        image: discord.Attachment | None,
        convo: Conversation | None = None,
        start_new: bool = False
    ):
        """
        Shared logic for both:
        - /ask or t.ask
        - reply-to-continue messages

        ctx_or_message can be:
        - commands.Context (from command)
        - discord.Message (from on_message)
        """

        prompt = (prompt or "").strip()
        if not prompt:
            if isinstance(ctx_or_message, commands.Context):
                return await ctx_or_message.reply("You must specify a prompt!", ephemeral=True)
            return

        # Build base contents
        contents: list = []

        # If continuing a conversation, include history
        if convo is not None:
            self._touch(convo)
            contents.extend(convo.history)


        user_name = ctx_or_message.author.name
        contents.append(f"{user_name}: {prompt}")

        # Add image if present
        if image is not None:
            if not is_image_attachment(image):
                reply_target = ctx_or_message if isinstance(ctx_or_message, commands.Context) else ctx_or_message.channel
                if isinstance(ctx_or_message, commands.Context):
                    return await ctx_or_message.reply("That attachment isn't an image.", ephemeral=True)
                else:
                    return await ctx_or_message.reply("That attachment isn't an image.")

            try:
                image_part = await attachment_to_part(image)
            except Exception:
                logger.exception("Failed to download image attachment.")
                if isinstance(ctx_or_message, commands.Context):
                    return await ctx_or_message.reply("I couldn't download that image attachment.", ephemeral=True)
                else:
                    return await ctx_or_message.reply("I couldn't download that image attachment.")

            contents.append(image_part)

        # Typing / deferring behavior
        if isinstance(ctx_or_message, commands.Context):
            try:
                await ctx_or_message.defer()
            except Exception:
                pass
            typing_cm = ctx_or_message.typing()
        else:
            typing_cm = ctx_or_message.channel.typing()

        async with typing_cm:
            try:
                response = await self._generate(contents)
                text = getattr(response, "text", None) or "(No text returned.)"
            except Exception:
                logger.exception("AI generation failed.")
                if isinstance(ctx_or_message, commands.Context):
                    return await ctx_or_message.reply("An error occurred while generating a response.")
                else:
                    return await ctx_or_message.reply("An error occurred while generating a response.")

        # Send reply
        if isinstance(ctx_or_message, commands.Context):
            sent = await ctx_or_message.reply(text)
        else:
            sent = await ctx_or_message.reply(text)

        # If starting a new conversation, create one now anchored on the bot message
        if start_new:
            new_convo = Conversation(
                root_bot_message_id=sent.id,
                latest_bot_message_id=sent.id,
                channel_id=sent.channel.id,
                history=[]
            )
            # Store the first turn in history
            new_convo.history.append(prompt)
            if image is not None:
                # NOTE: we do NOT store raw attachment objects, only parts
                # We re-create the part again so history is consistent
                try:
                    image_part = await attachment_to_part(image)
                    new_convo.history.append(image_part)
                except Exception:
                    pass
            new_convo.history.append(text)

            self.conversations[new_convo.root_bot_message_id] = new_convo
            self.message_to_root[sent.id] = new_convo.root_bot_message_id
            logger.info(f"Started new conversation root={new_convo.root_bot_message_id}")
            return

        # If continuing a conversation, append to history and update message pointers
        if convo is not None:
            convo.history.append(prompt)
            if image is not None:
                try:
                    image_part = await attachment_to_part(image)
                    convo.history.append(image_part)
                except Exception:
                    pass
            convo.history.append(f"Bot: {text}")


            self._trim_history(convo)
            self._register_bot_message(convo, sent.id)

    @commands.hybrid_command(name="ask")
    async def ask(
        self,
        ctx: commands.Context,
        *,
        prompt: str,
        image: discord.Attachment | None = None
    ):
        """Ask the AI chatbot a question."""
        logger.info(f"User {ctx.author} invoked ask command: {prompt!r}")

        # Prefix users can attach an image instead
        if image is None and getattr(ctx.message, "attachments", None):
            if ctx.message.attachments:
                image = ctx.message.attachments[0]

        await self._handle_prompt(
            ctx_or_message=ctx,
            prompt=prompt,
            image=image,
            convo=None,
            start_new=True
        )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Ignore bots (including ourselves)
        if message.author.bot:
            return

        # Ignore non-replies
        if not message.reference or not message.reference.message_id:
            return

        # Try to resolve the replied-to message
        replied_id = message.reference.message_id

        # Fast path: if it's not a known convo message, ignore
        root_id = self.message_to_root.get(replied_id)
        if not root_id:
            return

        convo = self.conversations.get(root_id)
        if not convo:
            return

        # Strict mode: only allow replying to the LATEST bot message
        if replied_id != convo.latest_bot_message_id:
            return

        # Must be same channel
        if message.channel.id != convo.channel_id:
            return

        # Get prompt text
        prompt = (message.content or "").strip()
        if not prompt:
            return

        # Check for an image attachment on the reply message
        image = None
        if message.attachments:
            image = message.attachments[0]

        await self._handle_prompt(
            ctx_or_message=message,
            prompt=prompt,
            image=image,
            convo=convo,
            start_new=False
        )

    @tasks.loop(minutes=2)
    async def cleanup_task(self):
        now = time.time()
        expired = []

        for root_id, convo in self.conversations.items():
            if now - convo.last_activity > CONVO_TIMEOUT:
                expired.append(root_id)

        for root_id in expired:
            convo = self.conversations.pop(root_id, None)
            if not convo:
                continue

            # Remove all message id mappings pointing to this convo root
            # (slow but safe; number of convos should be small)
            to_remove = [mid for mid, rid in self.message_to_root.items() if rid == root_id]
            for mid in to_remove:
                self.message_to_root.pop(mid, None)

            logger.info(f"Expired conversation root={root_id}")

    @cleanup_task.before_loop
    async def before_cleanup(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(Chatbot(bot))
