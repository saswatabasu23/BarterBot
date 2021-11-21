import base64

import discord
from discord.ext import commands
from fuzzywuzzy import process
from table2ascii import table2ascii as t2a, PresetStyle
import time
import pymongo as mongo
from random import randint

intents = discord.Intents.all()

bot = commands.Bot(command_prefix='!', intents=intents)

platforms = {'discord', 'epic', 'steam', 'psn', 'xbox'}

mongoClient = mongo.MongoClient(
    "mongodb+srv://barterBois:muli123@cluster0.ng91g.mongodb.net/BarterBotDB?retryWrites=true&w=majority")
db = mongoClient['BarterBotDB']
tokenTable = db['TokenTable']
channelTable = db['ChannelTable']
channelKeys = ['item-list', 'reports', 'posts']


@bot.command()
async def report(ctx, *args):
    """
        !report <platform> <username> : Platform can be (discord, epic, steam, xbox, psn)
    """
    channels = await getChannels(ctx)
    if len(args) != 2:
        await ctx.reply('Invalid input length! Check !help for syntax')
        return
    if args[0].lower() not in platforms:
        await ctx.reply('Invalid platform! Check !help for syntax')
        return
    if args[0].lower() == 'discord':
        username = args[1].split('#')
        member = discord.utils.get(ctx.guild.members, name=username[0], discriminator=username[1])
        if member is None:
            await ctx.reply(f'Error! Discord user {args[1]} is not a member of this server')
            return

    report_channel = bot.get_channel(channels['reports'])
    messages = await report_channel.history().flatten()
    reportExists = False
    for msg in messages:
        if msg.content.startswith(args[1] + ' ' + args[0].lower()):  # startswith "<id> <platform>"
            old = msg.content.split(' ')
            old[2] = str(int(old[2]) + 1)  # add 1 to bad report count
            new = ' '.join(old)
            await msg.edit(content=new)
            reportExists = True
    if not reportExists:
        await report_channel.send(args[1] + ' ' + args[0] + ' 1 0')
    await ctx.reply(f'Player {args[1]} has been reported.')


@bot.command()
async def post(ctx, *args):
    """
        !post [H] item1, item2 ... [W] item1, item2...   : [H] Have Items and [W] want items]
    """
    channels = await getChannels(ctx)
    msg = ctx.message.content.lower()
    if len(args) < 2:
        await ctx.reply('Too few parameters! Check !help for syntax')
        return
    if msg.find('[h]') == -1 or msg.find('[w]') == -1:  # if either have or want do not exist
        await ctx.reply('Invalid Syntax! Check !help for syntax')
        return
    msg = msg.replace('!post', '')
    msg = msg.replace('[h]', '')
    items = msg.split('[w]')
    haves = items[0].split(',')
    haves = [x.strip().rstrip().split() for x in haves]
    wants = items[1].split(',')
    wants = [x.strip().rstrip().split() for x in wants]

    allItems = await getItemList(channels)

    if await checkInItemList(ctx, haves + wants, allItems):
        token = str(time.time_ns()) + str(randint(10000000, 99999999))
        token = base64.b64encode(token.encode('ascii')).decode('ascii')  # encode into base64 string

        # insert into db
        entry = {'_id': token, 'message': f'{ctx.guild.id}/{ctx.channel.id}/{ctx.message.id}'}
        result = tokenTable.insert_one(entry)
        if result.acknowledged:
            embed = discord.Embed()
            embed.description = f"For your [post]({ctx.message.jump_url})\nThe Token is {token}"
            await ctx.author.send(embed=embed)
            # await ctx.author.send(f"For your post {ctx.message.jump_url}, the Token is {token}")
            await ctx.reply(f"Trade posted! the Verification Token has been sent in your DMs")
        else:
            await ctx.reply(f"Unable to post trade: Internal Server Error")


@bot.command()
async def test(ctx):
    print(ctx.message.author.display_name)
    print(ctx.message.author.discriminator)
    print(' [link](https://discord.com/channels/907109404535562260/911995393955495947/912018896561795102)       camo       @Thunderlined#2622')
    await ctx.reply('[link](https://discord.com/channels/907109404535562260/911995393955495947/912018896561795102)')

@bot.command()
async def check(ctx, *args):
    """
    !check <platform> <player> : Platform can be (discord, epic, steam, xbox, psn)
    """
    channels = await getChannels(ctx)
    if len(args) != 2:
        await ctx.reply('Invalid input length! Check !help for syntax')
        return
    if args[0].lower() not in platforms:
        await ctx.reply('Invalid platform! Check !help for syntax')
        return
    if args[0].lower() == 'discord':
        username = args[1].split('#')
        member = discord.utils.get(ctx.guild.members, name=username[0], discriminator=username[1])
        if member is None:
            await ctx.reply(f'Error! Discord user {args[1]} is not a member of this server')
            return

    report_channel = bot.get_channel(channels['reports'])
    messages = await report_channel.history().flatten()
    for msg in messages:
        if msg.content.startswith(args[1] + ' ' + args[0]):  # startswitth"<id> <platform>"
            old = msg.content.split(' ');
            print(old)
            await ctx.reply(f'Player {args[1]} has {old[2]} reports.')
            return


# channels = {'item-list': 910202152608206848, 'reported': 907243738064121866}


@bot.command()
@commands.has_any_role("Admin")
async def channel(ctx, *args):
    """
        !channel <type>                 : sets current channel to <type>
        !channel <type> #channel-name   : sets #channel-name to <type>
    """
    if len(args) < 1:
        await ctx.reply('Too few parameters! Check !help for syntax')
        return
    elif len(args) > 2:
        await ctx.reply('Too many parameters! Check !help for syntax')
        return
    if not args[0] in channelKeys:
        await ctx.reply(f'Invalid type! Channel types can only be : {channelKeys}')
        return

    channels = await getChannels(ctx)
    if len(args) == 1:
        channels[args[0]] = ctx.message.channel.id
        result = await updateChannels(ctx, channels)
        if result:
            await ctx.reply(f'{args[0]} channel set to <#{ctx.message.channel.id} successfully>')
        else:
            await ctx.reply('An error occurred while trying to set the channel')
    elif len(args) == 2:
        if args[1].startswith('<') and args[1].endswith('>') and args[1][1] == '#':
            print(args[1][2:-1])
        else:
            ctx.reply("Mentioned channel does not exist on the server!")
            return
        guildChannels = ctx.guild.channels
        guildChannels = [c for c in guildChannels if type(c) == discord.TextChannel]
        guildChannel = discord.utils.get(guildChannels, id=int(args[1][2:-1]))
        if guildChannel is not None:  # Checking if mentioned channel exists on the discord server
            channels[args[0]] = int(args[1][2:-1])
            result = await updateChannels(ctx, channels)
            if result:
                await ctx.reply(f'{args[0]} channel set to <#{args[1][2:-1]}> successfully')
            else:
                await ctx.reply('An error occurred while trying to set the channel')
        else:
            await ctx.reply('Mentioned channel does not exist on the server!')


async def checkInItemList(ctx, userItems, itemList):
    valid = True
    notFound = []
    print(userItems)
    for uItem in userItems:
        query = ''
        if type(uItem) == list:
            for word in uItem:
                if not word.isnumeric():
                    query += word
        elif type(uItem) == str:
            query = uItem

        print(query)
        result = process.extractOne(query, itemList)
        print('Result:\t')
        print(result)
        if result[1] > 93:
            valid = True
        elif result[1] > 60:
            valid = False
            notFound.append([query, result[0] + f' ({result[1]})'])
        else:
            valid = False
    if valid:
        return True
    elif len(notFound) > 0:
        msg = t2a(header=["Input Item", "Best Match"],
                  body=notFound,
                  style=PresetStyle.thin_compact_rounded)
        print(msg)
        await ctx.reply(f"Item(s) were not found! Check your DMs for more details.")
        embed = discord.Embed()
        embed.description = f"Item(s) were not found in our list of tradeable items!\n```{msg}```"
        embed.title = "Item(s) not found!"
        await ctx.author.send(embed=embed)
        # await ctx.author.send(f"These items were not found in our list of items!\n```{msg}```")
        return False
    else:
        await ctx.reply('Item(s) were not found!')
        return False


async def getChannels(ctx):
    guildID = ctx.guild.id
    channels = channelTable.find_one({'_id': guildID},
                                     {'_id': 0})  # find channels of guild and don't include the id in the result
    if channels is None:
        channels = {key: None for key in channelKeys}
    return channels


async def updateChannels(ctx, channels):
    if channelTable.find_one_and_update({'_id': ctx.guild.id}, {'$set': channels}) is None:
        channels['_id'] = ctx.guild.id
        result = channelTable.insert_one(channels)
        if not result.acknowledged:
            print(f"ERROR: Couldn't set channels: {channels} for {ctx.guild.id}")
        return result.acknowledged
    return True


async def getItemList(channels):
    itemChannel = bot.get_channel(channels['item-list'])
    itemsList = await itemChannel.history().flatten()
    allItems = []
    for items in itemsList:
        items1 = items.content.split(',')
        allItems += items1
    print('All Items:')
    print(allItems)
    return allItems


@bot.command()
async def price(ctx, *args):
    itemName = ''
    for arg in args:
        itemName += arg

    channels = await getChannels(ctx)
    allItems = await getItemList(channels)
    if not await checkInItemList(ctx, [itemName], allItems):
        return

    postChannel = bot.get_channel(channels['posts'])
    messages = await postChannel.history(limit=500).flatten()
    messages = [x for x in messages if (not x.author.bot) and x.content.startswith('!post')]
    results = []
    count = 0
    for msg in messages:
        text = msg.content.lower()
        text = text.replace('!post', '')
        text = text.replace('[h]', '')
        items = text.split('[w]')
        haves = items[0].split(',')
        haves = [x.strip().rstrip().split() for x in haves]
        wants = items[1].split(',')
        wants = [x.strip().rstrip().split() for x in wants]
        result = process.extractOne(itemName, haves + wants)
        if result[1] > 93:
            i1 = haves.index(result[0]) if result[0] in haves else None
            i2 = wants.index(result[0]) if result[0] in wants else None
            if i1 is None:
                results.append([haves[i2], msg])
            else:
                results.append([wants[i1], msg])
            count += 1
            if count > 4:
                break
    if count != 0:
        body = [[ f'[link]', ' '.join(x[0]), f'@{x[1].author.name}#{x[1].author.discriminator}'] for x in results]
        print(body)
        table = t2a(header=["Post Link", "Barter Item", "Discord User"],
                    body=body,
                    style=PresetStyle.thin_compact_rounded)
        i = 0
        temp = ''
        for line in table.splitlines():
            if '[link]' in line:
                line = line.replace('[link]', f'`[link]({results[i][1].jump_url})`')
                i += 1
            line = '`' + line + '`\n'
            temp += line
        table = temp
        print(table)
        embed = discord.Embed()
        embed.description = f'{table}'
        embed.title = f'The last {len(results)} posts for {itemName}'
        await ctx.reply(embed=embed)
        print(f'The last {len(results)} posts for {itemName}\n{table}')
    else:
        await ctx.reply(f'No posts found for {itemName}')

@bot.command()
async def verify(ctx, *args):
    """
    !verify <token>: token is a string
    """
    channels = await getChannels(ctx)
    if len(args) != 2:
        await ctx.reply('Invalid input length! Check !help for syntax')
        return

    token = args[0]
    entry = {'_id': token,
             'message': f'{ctx.guild.id}/{ctx.channel.id}/{ctx.message.id}'}

    report_channel = bot.get_channel(channels['reports'])
    messages = await report_channel.history().flatten()
    for msg in messages:
        # startswitth"<id> <platform>"
        if msg.content.startswith(args[1] + ' ' + args[0]):
            old = msg.content.split(' ')
            print(old)
            await ctx.reply(f'Player {args[1]} has {old[2]} reports.')
            return




bot.run('OTA3MTA5OTM0OTU5ODI5MDQ0.YYiZ9Q.AlQj1fjgXbBkt6eChf1Kr_tDRaU')
