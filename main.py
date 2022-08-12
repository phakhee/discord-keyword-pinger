import os
from threading import Thread
from dotenv import load_dotenv
from classes.StreamHandler import stream_handler
from interactions.ext.paginator import Page, Paginator
from interactions import Client, Intents, Message, Option, OptionType, CommandContext, Embed, Channel

load_dotenv()

discord_token = os.getenv("DISCORD_CLIENT_TOKEN")
guild_id = int(os.getenv("GUILD_ID"))

webhook_color = int(os.getenv("WEBHOOK_COLOR"))
webhook_icon = os.getenv("WEBHOOK_ICON")
webhook_name = os.getenv("WEBHOOK_NAME")

client = Client(
    token=discord_token,
    default_scope=guild_id,
    intents=Intents.DEFAULT | Intents.GUILD_MESSAGE_CONTENT
)


@client.event
async def on_ready():
    print(f"{webhook_name} is online")


@client.event(name="on_message_create")
async def on_message(message: Message):
    try:
        channel_id = str(message.channel_id)
        keywords_for_channel = [
            keyword for keyword in stream_handler.keywords
            if keyword[list(keyword.keys())[0]]["channel"]["id"] == channel_id
        ]

        # Check if message consists of embeds.
        if message.embeds:
            for embed in message.embeds:
                embed_text = ""

                # Filter out keyword CRUD and detection embeds.
                if embed.title:
                    embed_text += f"{embed.title}\n"

                if "Keyword(s) detected!" not in embed_text and "Added new keyword!" not in embed_text \
                        and "Deleted keyword(s)" not in embed_text and "All keyword(s)" not in embed_text:

                    if embed.author:
                        embed_text += f"{embed.author.name}\n"

                    if embed.description:
                        embed_text += f"{embed.description}\n"

                    if embed.fields:
                        for field in embed.fields:
                            embed_text += f"{field.name}\n"
                            embed_text += f"{field.value}\n"

                    # Loop through every saved keywords for channel of message.
                    for keywords_entry in keywords_for_channel:
                        keywords_id = list(keywords_entry.keys())[0]
                        keywords = keywords_entry[keywords_id]["keywords"]
                        delay = keywords_entry[keywords_id]["delay"]
                        contains_keywords = True

                        # Check if every keyword is in the embed text.
                        for keyword in keywords:
                            contains_keywords = keyword.lower() in embed_text.lower()

                        if contains_keywords:
                            past_delay = stream_handler.check_existing_ping(keywords_id, delay)

                            if past_delay:
                                embed = Embed(
                                    title="Keyword(s) detected!",
                                    color=webhook_color
                                )
                                embed.add_field(
                                    name="Keyword(s)",
                                    value=", ".join(keywords)
                                )
                                embed.set_footer(icon_url=webhook_icon, text=webhook_name)

                                channel: Channel = await message.get_channel()
                                await channel.send(embeds=[embed])
                                stream_handler.add_ping(keywords_id)

    except Exception as e:
        print(f"Error reason: {e}")


def divide_chunks(l, n):
    for i in range(0, len(l), n):
        yield l[i:i + n]


@client.command(name="allkeywords", description="Gets all saved keywords.", scope=guild_id)
async def all_keywords(ctx: CommandContext):
    keywords_entries = stream_handler.all_keywords()
    embed_string = ""
    embeds = []

    if len(keywords_entries) > 0:
        partitioned_keywords_entries = list(divide_chunks(keywords_entries, 10))

        for entries_partition in partitioned_keywords_entries:
            for keywords_entry in entries_partition:
                keywords_id = list(keywords_entry.keys())[0]

                embed_string += f"ID: {keywords_id}\n"
                embed_string += f"Channel: #{keywords_entry[keywords_id]['channel']['name']}\n"
                embed_string += f"Keyword(s): {', '.join(keywords_entry[keywords_id]['keywords'])}\n\n"

            embed_string = f"```{embed_string}```"
            embed = Embed(
                title="All keyword(s)",
                color=webhook_color,
                description=embed_string
            )
            embed.set_footer(icon_url=webhook_icon, text=webhook_name)
            embeds.append(embed)
            embed_string = ""

    else:
        embed_string = "No keyword(s) found."
        embed = Embed(
            title="All keyword(s)",
            color=webhook_color,
            description=embed_string
        )
        embed.set_footer(icon_url=webhook_icon, text=webhook_name)
        embeds.append(embed)

    if len(embeds) == 1:
        await ctx.send(embeds=embeds)
    else:
        embeds = [Page(embeds=[embed]) for embed in embeds]
        await Paginator(
            client=client,
            ctx=ctx,
            pages=embeds,
        ).run()


# Bot command where you can add a keyword.
@client.command(
    name="addkeyword",
    description="Makes it possible for user to add keyword that requires pinging if found.",
    scope=guild_id,
    options=[
        Option(
            name="keywords",
            description="The keyword you would like to add.",
            type=OptionType.STRING,
            required=True
        ),
        Option(
            name="channel",
            description="Which channel the keyword needs to be monitored.",
            type=OptionType.CHANNEL,
            required=True
        ),
        Option(
            name="delay",
            description="The amount of seconds the interval needs to be between pings when keyword is found.",
            type=OptionType.INTEGER,
            required=True
        )
    ]
)
async def add_keyword(ctx: CommandContext, keywords: str, channel: Channel, delay: int):
    data = {
        "keywords": keywords.split(" "),
        "channel": {
            "id": str(channel.id),
            "name": str(channel.name)
        },
        "delay": delay
    }

    entry_id = stream_handler.add_keywords(data)
    embed = Embed(
        title="Added new keyword!",
        color=webhook_color
    )
    embed.add_field(name="Keyword(s)", value=keywords)
    embed.add_field(name="Channel", value=str(channel.name))
    embed.add_field(name="Delay", value=str(delay))
    embed.add_field(name="ID", value=entry_id)
    embed.set_footer(icon_url=webhook_icon, text=webhook_name)

    await ctx.send(embeds=[embed])


@client.command(
    name="removekeyword",
    description="Command for deleting keywords in certain channels",
    scope=guild_id,
    options=[
        Option(
            name="keywords",
            description="The keyword you would like to add.",
            type=OptionType.STRING,
            required=True
        ),
        Option(
            name="channel",
            description="Which channel the keyword needs to be monitored.",
            type=OptionType.CHANNEL,
            required=True
        )
    ]
)
async def remove_keyword(ctx: CommandContext, keywords: str, channel: Channel):
    deleted_ids = stream_handler.remove_keywords(keywords, channel.id)
    embed_string = ""

    if len(deleted_ids) > 0:
        for deleted_id in deleted_ids:
            embed_string += f"{deleted_id}\n"

        embed_string = f"```{embed_string}```"
    else:
        embed_string = f"No keywords saved with **{keywords}**"

    embed = Embed(
        title="Deleted keyword(s)",
        color=webhook_color
    )
    embed.add_field("ID", value=embed_string)
    embed.set_footer(icon_url=webhook_icon, text=webhook_name)

    await ctx.send(embeds=[embed])


# Separate thread to stream realtime database.
thread = Thread(target=stream_handler.start)
thread.start()

client.start()
