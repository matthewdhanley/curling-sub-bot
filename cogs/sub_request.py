import os

import discord
from discord import app_commands
from discord.ext import commands

import db

SUBS_CHANNEL_ID = os.environ.get("SUBS_CHANNEL_ID", "")
DB_PATH = os.environ.get("DB_PATH", "./data/subbot.db")


def build_embed(request: dict, volunteers: list[dict]) -> discord.Embed:
    is_open = request["status"] == "OPEN"

    color = discord.Color.blue() if is_open else discord.Color(0x808080)
    title = "Sub Request" if is_open else "~~Sub Request~~ FILLED"

    embed = discord.Embed(title=title, color=color)
    embed.add_field(name="Requested by", value=request["requester_name"], inline=True)
    embed.add_field(name="Status", value="OPEN" if is_open else "FILLED", inline=True)
    embed.add_field(name="\u200b", value="\u200b", inline=True)  # spacer
    embed.add_field(name="Date", value=request["date"], inline=True)
    embed.add_field(name="Time", value=request["time"], inline=True)
    embed.add_field(name="Team", value=request["team"], inline=True)

    if request.get("note"):
        embed.add_field(name="Note", value=request["note"], inline=False)

    if volunteers:
        vol_names = "\n".join(f"- {v['user_name']}" for v in volunteers)
        embed.add_field(
            name=f"Volunteers ({len(volunteers)})", value=vol_names, inline=False
        )
    else:
        embed.add_field(name="Volunteers", value="_No volunteers yet_", inline=False)

    if not is_open and request.get("closed_by_name"):
        embed.set_footer(text=f"Closed by {request['closed_by_name']}")

    return embed


class SubRequestView(discord.ui.View):
    def __init__(self, db_path: str):
        super().__init__(timeout=None)
        self.db_path = db_path

    @discord.ui.button(
        label="Volunteer",
        style=discord.ButtonStyle.green,
        custom_id="subbot:volunteer",
        emoji="\U0001f9f9",  # broom emoji (curling)
    )
    async def volunteer_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.defer(ephemeral=True)

        request = await db.get_request_by_message_id(
            self.db_path, str(interaction.message.id)
        )
        if request is None:
            await interaction.followup.send(
                "Could not find this request in the database.", ephemeral=True
            )
            return

        if request["status"] == "FILLED":
            await interaction.followup.send(
                "This request has already been filled.", ephemeral=True
            )
            return

        volunteered = await db.toggle_volunteer(
            self.db_path,
            request["id"],
            str(interaction.user.id),
            interaction.user.display_name,
        )

        volunteers = await db.get_volunteers(self.db_path, request["id"])
        embed = build_embed(request, volunteers)

        try:
            await interaction.message.edit(embed=embed)
        except discord.NotFound:
            await interaction.followup.send(
                "The request message was not found.", ephemeral=True
            )
            return

        msg = "You have volunteered!" if volunteered else "You have un-volunteered."
        await interaction.followup.send(msg, ephemeral=True)

    @discord.ui.button(
        label="Close Request",
        style=discord.ButtonStyle.red,
        custom_id="subbot:close",
    )
    async def close_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.defer(ephemeral=True)

        success = await db.close_request(
            self.db_path,
            str(interaction.message.id),
            str(interaction.user.id),
            interaction.user.display_name,
        )
        if not success:
            await interaction.followup.send(
                "This request is already closed.", ephemeral=True
            )
            return

        request = await db.get_request_by_message_id(
            self.db_path, str(interaction.message.id)
        )
        volunteers = await db.get_volunteers(self.db_path, request["id"])
        embed = build_embed(request, volunteers)

        # Build a fresh view with disabled buttons — never mutate the persistent view
        disabled_view = discord.ui.View()
        disabled_view.add_item(
            discord.ui.Button(
                label="Volunteer",
                style=discord.ButtonStyle.green,
                custom_id="subbot:volunteer",
                emoji="\U0001f9f9",
                disabled=True,
            )
        )
        disabled_view.add_item(
            discord.ui.Button(
                label="Close Request",
                style=discord.ButtonStyle.red,
                custom_id="subbot:close",
                disabled=True,
            )
        )

        try:
            await interaction.message.edit(embed=embed, view=disabled_view)
        except discord.NotFound:
            await interaction.followup.send(
                "The request message was not found.", ephemeral=True
            )
            return

        await interaction.followup.send("Request closed.", ephemeral=True)


class SubRequestModal(discord.ui.Modal, title="Request a Substitute"):
    date = discord.ui.TextInput(
        label="Date",
        placeholder="e.g. Feb 22",
        max_length=50,
        required=True,
    )
    time = discord.ui.TextInput(
        label="Time",
        placeholder="e.g. 7:30 PM",
        max_length=50,
        required=True,
    )
    team = discord.ui.TextInput(
        label="Team Name",
        placeholder="e.g. The Stones",
        max_length=100,
        required=True,
    )
    note = discord.ui.TextInput(
        label="Additional Info (optional)",
        placeholder="e.g. Skip position needed",
        style=discord.TextStyle.paragraph,
        max_length=500,
        required=False,
    )

    def __init__(self, db_path: str):
        super().__init__()
        self.db_path = db_path

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        view = SubRequestView(db_path=self.db_path)

        # Build the initial embed from form data before we have a message_id
        request_data = {
            "requester_name": interaction.user.display_name,
            "date": self.date.value,
            "time": self.time.value,
            "team": self.team.value,
            "note": self.note.value or None,
            "status": "OPEN",
            "closed_by_name": None,
        }
        embed = build_embed(request_data, [])

        # Send to channel first to get the message_id from Discord
        msg = await interaction.channel.send(embed=embed, view=view)

        # Now persist with the real message_id
        await db.create_request(
            db_path=self.db_path,
            message_id=str(msg.id),
            channel_id=str(interaction.channel_id),
            guild_id=str(interaction.guild_id),
            requester_id=str(interaction.user.id),
            requester_name=interaction.user.display_name,
            date=self.date.value,
            time=self.time.value,
            team=self.team.value,
            note=self.note.value or None,
        )

        await interaction.followup.send("Your request has been posted!", ephemeral=True)


class SubRequestCog(commands.Cog):
    def __init__(self, bot: commands.Bot, db_path: str):
        self.bot = bot
        self.db_path = db_path

    @app_commands.command(
        name="request-sub", description="Post a substitute request for curling"
    )
    async def request_sub(self, interaction: discord.Interaction):
        if SUBS_CHANNEL_ID and str(interaction.channel_id) != SUBS_CHANNEL_ID:
            await interaction.response.send_message(
                f"Please use this command in <#{SUBS_CHANNEL_ID}>.",
                ephemeral=True,
            )
            return

        await interaction.response.send_modal(SubRequestModal(db_path=self.db_path))


async def setup(bot: commands.Bot):
    cog = SubRequestCog(bot, DB_PATH)
    await bot.add_cog(cog)
    # Register the persistent view so button interactions survive restarts
    bot.add_view(SubRequestView(db_path=DB_PATH))
