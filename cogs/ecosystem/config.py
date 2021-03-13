import discord
import os
from discord.ext import commands
from core.globs import Git
from typing import Optional
from asyncio import TimeoutError
from motor.motor_asyncio import AsyncIOMotorClient


class Config(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot: commands.Bot = bot
        self.db_client: AsyncIOMotorClient = AsyncIOMotorClient(
            os.getenv('DB_CONNECTION')).store
        self.user_db: AsyncIOMotorClient = self.db_client.users
        self.guild_db: AsyncIOMotorClient = self.db_client.guilds
        self.square: str = ":white_small_square:"
        self.emoji: str = '<:github:772040411954937876>'
        self.ga: str = '<:ga:768064843176738816>'
        self.e: str = '<:ge:767823523573923890>'

    @commands.group(name='config', aliases=['--config', '-cfg', 'cfg'])
    @commands.cooldown(15, 30, commands.BucketType.user)
    async def config_command_group(self, ctx: commands.Context) -> None:
        if ctx.invoked_subcommand is None:
            lines: list = ["**In this section you can configure various aspects of your experience**",
                           "\n**Quick access**",
                           "These commands allow you to save a user, repo or org to get with a short command.",
                           "`git config --user {username}` " + self.ga +
                           " Access a saved user with `git user`",
                           "`git config --org {org}` " + self.ga +
                           " Access a saved organization with `git org`",
                           "`git config --repo {repo}` " + self.ga +
                           " Access a saved repo with `git repo`",
                           "`git config --feed {repo}` " + self.ga +
                           " Subscribe to new releases of a repository",
                           "\n**You can delete stored data by typing** `git config --delete`"]
            embed = discord.Embed(
                color=0xefefef,
                title=f"{self.emoji}  GitBot Config",
                description='\n'.join(lines)
            )
            embed.set_footer(
                text='To see what you have saved, use git config --show')
            await ctx.send(embed=embed)

    @config_command_group.command(name='--show', aliases=['-S', '-show', 'show'])
    @commands.cooldown(15, 30, commands.BucketType.user)
    async def config_show(self, ctx: commands.Context) -> None:
        query: dict = await self.user_db.find_one({"_id": int(ctx.author.id)})
        if not isinstance(ctx.channel, discord.DMChannel):
            release: Optional[dict] = await self.guild_db.find_one({'_id': ctx.guild.id})
        else:
            release = None
        if query is None and release is None or release and len(release) == 1 and query is None:
            await ctx.send(
                f'{self.e}  **You don\'t have any quick access data configured!** Use `git config` to do it')
            return
        user: str = f"User: `{query['user']}`" if 'user' in query else "User: `Not set`"
        org: str = f"Organization: `{query['org']}`" if 'org' in query else "Organization: `Not set`"
        repo: str = f"Repo: `{query['repo']}`" if 'repo' in query else "Repo: `Not set`"
        feed: str = 'Release Feed:\n' + '\n'.join(
            [f'{self.square} `{r["repo"]}`' for r in release['feed']]) if release and release[
            'feed'] else 'Release Feed: `Not configured`'
        data: list = [user, org, repo, feed]
        embed = discord.Embed(
            color=0xefefef,
            title=f"{self.emoji}  Your {self.bot.user.name} Config",
            description="**Quick access:**\n" + '\n'.join(data)
        )
        await ctx.send(embed=embed)

    @config_command_group.command(name='feed',
                                  aliases=['-feed', '--feed', 'release', '-release', '--release', '-f', '-F'])
    @commands.guild_only()
    @commands.has_guild_permissions(manage_channels=True)
    @commands.bot_has_guild_permissions(manage_webhooks=True, manage_channels=True)
    @commands.cooldown(10, 30, commands.BucketType.guild)
    async def config_release_feed(self, ctx: commands.Context, repo: Optional[str] = None) -> None:
        g: dict = await self.guild_db.find_one({'_id': ctx.guild.id})
        if not g:
            embed: discord.Embed = discord.Embed(
                color=0xff009b,
                title='Release Feed channel configuration',
                description=f'It appears that you don\'t have a Release Feed channel configured yet.\n'
                            f'**Let\'s configure one now, shall we?**\n\n'
                            f'Simply specify the channel you want to receive the updates in below by typing its name '
                            f'or mention, or type `create` for the bot to make the channel for you. '
            )
            embed.set_footer(text='You can type cancel to quit at any point.')
            base_msg: discord.Message = await ctx.send(embed=embed)
            while True:
                try:
                    msg: discord.Message = await self.bot.wait_for('message',
                                                                   check=lambda msg_: (msg_.channel.id == ctx.channel.id
                                                                                       and msg_.author.id == ctx.author.id),
                                                                   timeout=30)
                    if (m := msg.content.lower()) == 'cancel':
                        await base_msg.delete()
                        await ctx.send(f'{self.emoji}  Release Feed channel setup **cancelled.**')
                        return
                    elif m == 'create':
                        channel: Optional[discord.TextChannel] = await ctx.guild.create_text_channel('release-feeds',
                                                                                                     topic=f'Release feeds of configured repos will show up here!')
                    else:
                        try:
                            channel: Optional[discord.TextChannel] = await commands.TextChannelConverter().convert(ctx,
                                                                                                                   msg.content)
                        except commands.BadArgument:
                            await ctx.send(
                                f'{self.e}  **That is not a valid channel!** Try again, or type `cancel` to quit.')
                            continue
                    hook: discord.Webhook = await channel.create_webhook(name=self.bot.user.name,
                                                                         reason=f'Release Feed channel setup by {ctx.author}')
                    feed: list = []
                    r: Optional[dict] = None
                    if repo:
                        r: dict = await Git.get_latest_release(repo)
                        feed = [{'repo': repo.lower(), 'release': r['release']['tagName']}] if r and r[
                            'release'] else []
                    if hook:
                        await self.guild_db.insert_one(
                            {'_id': ctx.guild.id, 'hook': hook.url[33:], 'feed': feed if feed else []})
                        success_embed: discord.Embed = discord.Embed(
                            color=0x33ba7c,
                            title=f'Release Feed channel configured!',
                            description=f'You can now add repos whose new updates should be logged in'
                                        f' {channel.mention} by using `git config feed {{repo}}`.'
                                        f' Each time there is a new release,'
                                        f' an embed will show up with some info and changes.'
                        )
                        if r:
                            success_embed.set_footer(
                                text=f'{repo} has already been added :)')
                        try:
                            await msg.delete()
                        except discord.errors.Forbidden:
                            pass
                        await base_msg.edit(embed=success_embed)
                        return
                    else:
                        await base_msg.delete()
                        await ctx.send(f'{self.e}  **Something went wrong,** please report this in the support server.')
                        return
                except TimeoutError:
                    timeout_embed = discord.Embed(
                        color=0xffd500,
                        title=f'Timed Out'
                    )
                    timeout_embed.set_footer(
                        text='Simply send a channel name/mention next time!')
                    await base_msg.edit(embed=timeout_embed)
                    return
        if g and not repo:
            await ctx.send(f'{self.e} Please pass in a repository which you wish to follow!')
            return
        r: dict = await Git.get_latest_release(repo)
        if not r:
            await ctx.send(f'{self.e}  This repo **doesn\'t exist!**')
        if g:
            for r_ in g['feed']:
                if r_['repo'].lower() == repo.lower():
                    await ctx.send(f'{self.e}  That repo\'s releases are **already being logged!**')
                    return
            if len(g['feed']) < 3:
                await self.guild_db.update_one({'_id': ctx.guild.id},
                                               {'$push': {'feed': {'repo': repo, 'release': r['release']['tagName'] if r['release'] else None}}})
                await ctx.send(f'{self.emoji} **{repo}\'s** releases will now be logged.')
            else:
                embed_limit_reached: discord.Embed = discord.Embed(
                    color=0xda4353,
                    title='Release Feed repo limit reached!',
                    description=f'This guild has reached the **limit of 3 release feed repos.**'
                                f' You can remove a previously added repo by typing `git config -delete feed`'
                )
                embed_limit_reached.set_footer(text=f'You need the Manage Channels to do that.',
                                               icon_url=self.bot.user.avatar_url)
                await ctx.send(embed=embed_limit_reached)

    @config_command_group.command(name='--user', aliases=['-u', '-user', 'user'])
    @commands.cooldown(15, 30, commands.BucketType.user)
    async def config_user(self, ctx: commands.Context, user: str) -> None:
        u = await self.setitem(ctx, 'user', user)
        if u:
            await ctx.send(f"{self.emoji}  Quick access user set to **{user}**")
        else:
            await ctx.send(f'{self.e}  This user **doesn\'t exist!**')

    @config_command_group.command(name='--org', aliases=['--organization', '-O', '-org', 'org'])
    @commands.cooldown(15, 30, commands.BucketType.user)
    async def config_org(self, ctx: commands.Context, org: str) -> None:
        o = await self.setitem(ctx, 'org', org)
        if o:
            await ctx.send(f"{self.emoji}  Quick access organization set to **{org}**")
        else:
            await ctx.send(f'{self.e}  This organization **doesn\'t exist!**')

    @config_command_group.command(name='--repo', aliases=['--repository', '-R', '-repo', 'repo'])
    @commands.cooldown(15, 30, commands.BucketType.user)
    async def config_repo(self, ctx, repo) -> None:
        r = await self.setitem(ctx, 'repo', repo)
        if r:
            await ctx.send(f"{self.emoji}  Quick access repo set to **{repo}**")
        else:
            await ctx.send(f'{self.e}  This repo **doesn\'t exist!**')

    @config_command_group.group(name='-delete', aliases=['-D', '-del', 'delete', '--delete'])
    @commands.cooldown(15, 30, commands.BucketType.user)
    async def delete_field_group(self, ctx: commands.Context) -> None:
        if ctx.invoked_subcommand is None:
            embed = discord.Embed(
                color=0xefefef,
                title=f"{self.emoji}  Delete Quick Access Data",
                description=f"**You can delete stored quick access data by running the following commands:**\n"
                            f"`git config --delete user`" +
                f' {self.ga} ' + 'delete the quick access user\n'
                f"`git config --delete org`" +
                f' {self.ga} ' + 'delete the quick access organization\n'
                f"`git config --delete repo`" +
                f' {self.ga} ' + 'delete the quick access repo\n'
                f"`git config --delete all`" +
                f' {self.ga} ' + 'delete all of your quick access data\n'
                f"`git config --delete feed` {self.ga} view options regarding deleting release feed data"
            )
            await ctx.send(embed=embed)

    @delete_field_group.group(name='feed', aliases=['-feed', '--feed'], invoke_without_command=True)
    @commands.guild_only()
    @commands.has_guild_permissions(manage_guild=True, manage_channels=True)
    @commands.cooldown(15, 30, commands.BucketType.guild)
    async def delete_feed_group(self, ctx: commands.Context, repo: Optional[str]) -> None:
        if ctx.invoked_subcommand is None:
            if not repo:
                embed: discord.Embed = discord.Embed(
                    color=0xefefef,
                    title='Delete Release Feed data',
                    description=f'**You can delete stored release feed data by running the following commands:**\n'
                                f'`git config -delete feed {{repo}}` {self.ga} unsubscribe from a specific repo\n'
                                f'`git config -delete feed all` {self.ga} unsubscribe from all repos\n'
                                f'`git config -delete feed total` {self.ga} unsubscribe from all releases and delete '
                                f'the '
                                f'feed webhook'
                )
                await ctx.send(embed=embed)
            else:
                guild: Optional[dict] = await self.guild_db.find_one({'_id': ctx.guild.id})
                if guild:
                    for r in guild['feed']:
                        if r['repo'].lower() == repo.lower():
                            guild['feed'].remove(r)
                            await self.guild_db.update_one({'_id': ctx.guild.id}, {'$set': {'feed': guild['feed']}})
                            await ctx.send(f'{self.emoji}  `{repo}`\'s releases will **no longer be logged.**')
                            return
                    await ctx.send(f'{self.e}  That repo\'s releases are **not currently logged!**')
                else:
                    await ctx.send(f'{self.e}  You don\'t have a release feed channel configured!')

    @delete_feed_group.command(name='all', aliases=['-all', '--all'])
    @commands.guild_only()
    @commands.cooldown(15, 30, commands.BucketType.guild)
    @commands.has_guild_permissions(manage_guild=True, manage_channels=True)
    async def delete_all_feeds_command(self, ctx: commands.Context) -> None:
        guild: Optional[dict] = await self.guild_db.find_one({'_id': ctx.guild.id})
        if guild is None:
            await ctx.send(f'{self.e}  You don\'t have a release feed configured, so **nothing was deleted.**')
        else:
            if guild['feed']:
                await self.guild_db.update_one(guild, {'$set': {'feed': []}})
            await ctx.send(f'{self.emoji}  All release feeds were **closed successfully.**')

    @delete_feed_group.command(name='total', aliases=['-total', '--total', '-t'])
    @commands.guild_only()
    @commands.cooldown(10, 30, commands.BucketType.guild)
    @commands.has_guild_permissions(manage_guild=True, manage_channels=True)
    @commands.bot_has_guild_permissions()
    async def delete_feed_with_channel_command(self, ctx: commands.Context) -> None:
        guild: Optional[dict] = await self.guild_db.find_one({'_id': ctx.guild.id})
        if guild is None:
            await ctx.send(f'{self.e}  You don\'t have a release feed configured, so **nothing was deleted.**')
        else:
            await self.guild_db.delete_one(guild)
            try:
                webhook: discord.Webhook = discord.Webhook.from_url('https://discord.com/api/webhooks/' + guild['hook'],
                                                                    adapter=discord.AsyncWebhookAdapter(Git.ses))
                await webhook.delete()
            except (discord.NotFound, discord.HTTPException):
                pass
            finally:
                await ctx.send(f'{self.e}  The release feed channel has been **closed successfully.**')

    @delete_field_group.command(name='user', aliases=['-U', '-user', '--user'])
    @commands.cooldown(15, 30, commands.BucketType.user)
    async def delete_user_command(self, ctx: commands.Context) -> None:
        deleted: bool = await self.delete_field(ctx, 'user')
        if deleted:
            await ctx.send(f"{self.emoji}  Saved **user deleted.**")
        else:
            await ctx.send(f"{self.e}  You don't have a user saved!")

    @delete_field_group.command(name='org', aliases=['-O', '-org', 'organization', '-organization'])
    @commands.cooldown(15, 30, commands.BucketType.user)
    async def delete_org_command(self, ctx: commands.Context) -> None:
        deleted: bool = await self.delete_field(ctx, 'org')
        if deleted:
            await ctx.send(f"{self.emoji}  Saved **organization deleted.**")
        else:
            await ctx.send(f"{self.e}  You don't have an organization saved!")

    @delete_field_group.command(name='repo', aliases=['-R', '-repo'])
    @commands.cooldown(15, 30, commands.BucketType.user)
    async def delete_repo_command(self, ctx: commands.Context) -> None:
        deleted: bool = await self.delete_field(ctx, 'repo')
        if deleted:
            await ctx.send(f"{self.emoji}  Saved **repo deleted.**")
        else:
            await ctx.send(f"{self.e}  You don't have a repo saved!")

    @delete_field_group.command(name='all', aliases=['-A', '-all'])
    @commands.cooldown(15, 30, commands.BucketType.user)
    async def delete_entire_record(self, ctx: commands.Context) -> None:
        query: dict = await self.user_db.find_one_and_delete({"_id": int(ctx.author.id)})
        if not query:
            await ctx.send(f"{self.e}  It appears that **you don't have anything stored!**")
            return
        await ctx.send(f"{self.emoji}  All of your stored data was **successfully deleted.**")

    async def delete_field(self, ctx: commands.Context, field: str) -> bool:
        query: dict = await self.user_db.find_one({"_id": ctx.author.id})
        if query is not None and field in query:
            await self.user_db.update_one(query, {"$unset": {field: ""}})
            del query[field]
            if len(query) == 2:
                await self.user_db.find_one_and_delete({"_id": ctx.author.id})
            return True
        return False

    async def getitem(self, ctx: commands.Context, item: str) -> Optional[str]:
        query: dict = await self.user_db.find_one({'_id': ctx.author.id})
        if query and item in query:
            return query[item]
        return None

    async def setitem(self, ctx: commands.Context, item: str, value: str) -> bool:
        exists: bool = await ({'user': Git.get_user, 'repo': Git.get_repo, 'org': Git.get_org}[item])(value) is not None
        if exists:
            query = await self.user_db.find_one({"_id": ctx.author.id})
            if query is not None:
                await self.user_db.update_one(query, {"$set": {item: value}})
            else:
                await self.user_db.insert_one({"_id": ctx.author.id, item: value})
            return True
        return False


def setup(bot: commands.Bot) -> None:
    bot.add_cog(Config(bot))
