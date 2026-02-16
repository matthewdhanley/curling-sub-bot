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

    league = request.get("league_type", "")
    embed.add_field(name="League", value=league if league else "—", inline=True)
    embed.add_field(name="Date", value=request["date"], inline=True)
    embed.add_field(name="Time", value=request["time"], inline=True)
    embed.add_field(name="Team", value=request["team"], inline=False)

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
    league_type = discord.ui.TextInput(
        label="League Type",
        placeholder="Recreational or Competitive",
        max_length=50,
        required=True,
    )
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

        request_data = {
            "requester_name": interaction.user.display_name,
            "league_type": self.league_type.value,
            "date": self.date.value,
            "time": self.time.value,
            "team": self.team.value,
            "note": self.note.value or None,
            "status": "OPEN",
            "closed_by_name": None,
        }
        embed = build_embed(request_data, [])

        subs_role = discord.utils.get(interaction.guild.roles, name="subs")
        mention = subs_role.mention if subs_role else ""
        msg = await interaction.channel.send(content=mention, embed=embed, view=view)

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
            league_type=self.league_type.value,
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

    @app_commands.command(
        name="join-sub-list", description="Join the subs list to be notified of substitute requests"
    )
    async def join_sub_list(self, interaction: discord.Interaction):
        role = discord.utils.get(interaction.guild.roles, name="subs")
        if role is None:
            await interaction.response.send_message(
                'No role named "subs" exists on this server. Ask an admin to create it.',
                ephemeral=True,
            )
            return

        if role in interaction.user.roles:
            await interaction.response.send_message(
                "You're already on the subs list!", ephemeral=True
            )
            return

        await interaction.user.add_roles(role, reason="Joined subs list via /join-sub-list")
        await interaction.response.send_message(
            "You've been added to the subs list and will be notified of substitute requests.",
            ephemeral=True,
        )

    @app_commands.command(
        name="leave-sub-list", description="Remove yourself from the subs list"
    )
    async def leave_sub_list(self, interaction: discord.Interaction):
        role = discord.utils.get(interaction.guild.roles, name="subs")
        if role is None:
            await interaction.response.send_message(
                'No role named "subs" exists on this server.',
                ephemeral=True,
            )
            return

        if role not in interaction.user.roles:
            await interaction.response.send_message(
                "You're not on the subs list.", ephemeral=True
            )
            return

        await interaction.user.remove_roles(role, reason="Left subs list via /leave-sub-list")
        await interaction.response.send_message(
            "You've been removed from the subs list.", ephemeral=True
        )

    @app_commands.command(
        name="open-subs", description="See all open substitute requests"
    )
    async def open_subs(self, interaction: discord.Interaction):
        requests = await db.get_open_requests(self.db_path, str(interaction.guild_id))

        if not requests:
            await interaction.response.send_message(
                "There are no open sub requests right now.", ephemeral=True
            )
            return

        embed = discord.Embed(
            title=f"Open Sub Requests ({len(requests)})",
            color=discord.Color.blue(),
        )

        for r in requests:
            league = f" · {r['league_type']}" if r.get("league_type") else ""
            note = f"\n> {r['note']}" if r.get("note") else ""
            jump_url = f"https://discord.com/channels/{r['guild_id']}/{r['channel_id']}/{r['message_id']}"
            embed.add_field(
                name=f"{r['date']} at {r['time']} · {r['team']}{league}",
                value=f"Requested by {r['requester_name']}{note}\n[Jump to post]({jump_url})",
                inline=False,
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="post-guide", description="Post the how-to guide for this channel (admin only)"
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def post_guide(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="How to Use This Channel",
            color=discord.Color.blue(),
        )

        embed.add_field(
            name="📋 Requesting a Sub",
            value=(
                "Use `/request-sub` to post a substitute request.\n"
                "You'll be asked for the league type, date, time, team name, and any extra details.\n"
                "Once submitted, a post will appear here and the @subs list will be notified."
            ),
            inline=False,
        )

        embed.add_field(
            name="🧹 Volunteering as a Sub",
            value=(
                "Click the **Volunteer** button on any open request to offer yourself as a sub.\n"
                "Click it again to un-volunteer if your availability changes."
            ),
            inline=False,
        )

        embed.add_field(
            name="✅ Closing a Request",
            value=(
                "Once a sub has been found, click **Close Request** on the post.\n"
                "The request will be marked as **FILLED** and the buttons will be disabled."
            ),
            inline=False,
        )

        embed.add_field(
            name="🔔 Joining / Leaving the Subs List",
            value=(
                "Use `/join-sub-list` to sign up to be notified when a sub is needed.\n"
                "Use `/leave-sub-list` to stop receiving notifications."
            ),
            inline=False,
        )

        topic = (
            "Need a sub? Use /request-sub to post a request. "
            "Want to be notified when subs are needed? Use /join-sub-list."
        )

        await interaction.response.defer(ephemeral=True)

        try:
            await interaction.channel.edit(topic=topic)
        except discord.Forbidden:
            pass  # No Manage Channels permission — skip topic

        msg = await interaction.channel.send(embed=embed)

        try:
            await msg.pin()
        except discord.Forbidden:
            pass  # No Manage Messages permission — post without pinning

        await interaction.followup.send("Guide posted!", ephemeral=True)

    @post_guide.error
    async def post_guide_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "You need the **Manage Server** permission to use this command.",
                ephemeral=True,
            )


async def setup(bot: commands.Bot):
    cog = SubRequestCog(bot, DB_PATH)
    await bot.add_cog(cog)
    # Register the persistent view so button interactions survive restarts
    bot.add_view(SubRequestView(db_path=DB_PATH))
