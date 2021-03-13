import discord
import datetime
from asyncio import TimeoutError
from discord.ext import commands
from core.globs import Git, Mgr
from typing import Optional, Tuple, Union

DISCORD_MD_LANGS: tuple = (
    "java",
    "js",
    "py",
    "css",
    "cs",
    "c",
    "cpp",
    "html",
    "php",
    "json",
    "xml",
    "yml",
    "nim",
    "md",
    "go",
    "kt",
)


class Gist(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot: commands.Bot = bot
        self.emoji: str = "<:github:772040411954937876>"
        self.e: str = "<:ge:767823523573923890>"
        self.square: str = ":white_small_square:"

    @commands.command(
        name="gist", aliases=["-gist", "--gist", "gists", "-gists", "--gists"]
    )
    @commands.cooldown(10, 30, commands.BucketType.user)
    async def gist_command(
        self, ctx: commands.Context, user: str, ind: Optional[Union[int, str]] = None
    ) -> None:
        data: dict = await Git.get_user_gists(user)
        if not data:
            await ctx.send(f"{self.e}  This user **doesn't exist!**")
            return
        if (gists := len(data["gists"]["nodes"])) < 2:
            if gists == 0:
                await ctx.send(
                    f"{self.e}  This user doesn't have any **public gists!**"
                )
            else:
                await ctx.send(
                    embed=await self.build_gist_embed(
                        data,
                        1,
                        footer="You didn't see the gist list because this user has only one gist.",
                    )
                )
            return

        def gist_url(gist: dict) -> str:
            if not gist["description"]:
                return gist["url"]
            desc = (
                gist["description"]
                if len(gist["description"]) < 70
                else gist["description"][:67] + "..."
            )
            return f'[{desc}]({gist["url"]})'

        gist_strings: list = [
            f"{self.square}**{ind + 1} |** {gist_url(gist)}"
            for ind, gist in enumerate(data["gists"]["nodes"])
        ]

        embed: discord.Embed = discord.Embed(
            color=0xEFEFEF,
            title=f"{user}'s gists",
            description="\n".join(gist_strings),
            url=data["url"],
        )

        embed.set_footer(
            text=f"Ten latest gists from {user}.\nTo inspect a specific gist, simply send its number in this channel."
        )

        base_msg: discord.Message = await ctx.send(embed=embed)

        def validate_index(index: Union[int, str]) -> Tuple[bool, Optional[str]]:
            if not str(index).isnumeric():
                return (
                    False,
                    f"{self.emoji}  Please pick a number **between 1 and {len(gist_strings)}**",
                )
            elif int(index) > 10:
                return (
                    False,
                    f"{self.emoji} Please pass in a number **smaller than 10!**",
                )
            elif int(index) > len(gist_strings):
                return False, f"{self.emoji} This user doesn't have that many gists!"
            else:
                return True, None

        if ind:
            if (i := validate_index(ind))[0]:
                await base_msg.delete()
                await ctx.send(
                    embed=await self.build_gist_embed(
                        data,
                        int(ind),
                        "The content is a preview of the first file of the gist",
                    )
                )
                return
            else:
                await ctx.send(i[1], delete_after=7)

        while True:
            try:
                msg: discord.Message = await self.bot.wait_for(
                    "message",
                    check=lambda m: (
                        m.channel.id == ctx.channel.id and m.author.id == ctx.author.id
                    ),
                    timeout=30,
                )
                success, err_msg = validate_index(msg.content)
                if not success:
                    await ctx.send(err_msg, delete_after=7)
                    continue
                break
            except TimeoutError:
                timeout_embed = discord.Embed(color=0xFFD500, title=f"Timed Out")
                timeout_embed.set_footer(
                    text="To pick an option, simply send a number next time!"
                )
                await base_msg.edit(embed=timeout_embed)
                return
        await ctx.send(
            embed=await self.build_gist_embed(
                data,
                int(msg.clean_content),
                "The content is a preview of the first file of the gist",
            )
        )

    async def build_gist_embed(
        self, data: dict, index: int, footer: Optional[str] = None
    ) -> discord.Embed:
        gist: dict = data["gists"]["nodes"][index - 1 if index != 0 else 1]
        embed = discord.Embed(
            color=await self.get_color_from_files(gist["files"]),
            title=gist["description"],
            description=None,
            url=gist["url"],
        )
        first_file: dict = gist["files"][0]

        created_at: str = f"Created by [{data['login']}]({data['url']}) on {datetime.datetime.strptime(gist['createdAt'], '%Y-%m-%dT%H:%M:%SZ').strftime('%e, %b %Y')}\n"
        updated_at: str = f"Last updated at {datetime.datetime.strptime(gist['updatedAt'], '%Y-%m-%dT%H:%M:%SZ').strftime('%e, %b %Y')}\n"
        stargazers = (
            f"Has [{gist['stargazerCount']} stargazers]({gist['url']}/stargazers)"
            if gist["stargazerCount"] != 1
            else f"Has [one stargazer]({gist['url']}/stargazers)"
        )
        if gist["stargazerCount"] == 0:
            stargazers = "Has no stargazers"
        comment_count = gist["comments"]["totalCount"]
        comments = (
            f"and [{comment_count} comments]({gist['url']})"
            if comment_count != 1
            else f"and [one comment]({gist['url']})"
        )
        if gist["stargazerCount"] == 0:
            comments = "and no comments"

        stargazers_and_comments = f"{stargazers} and {comments}"
        info: str = f"{created_at}{updated_at}{stargazers_and_comments}"
        embed.add_field(
            name=":notepad_spiral: Contents:",
            value=f"```{self.extension(first_file['extension'])}\n{first_file['text'][:449]}```",
        )
        embed.add_field(name=":mag_right: Info:", value=info, inline=False)

        if footer:
            embed.set_footer(text=footer)

        return embed

    async def get_color_from_files(self, files: list) -> int:
        extensions: list = [f["extension"] for f in files]
        most_common: Optional[str] = await Mgr.get_most_common(extensions)
        if most_common in [".md", ""]:
            return 0xEFEFEF
        for file in files:
            if all(
                [
                    file["extension"] == most_common,
                    file["language"],
                    file["language"]["color"],
                ]
            ):
                return int(file["language"]["color"][1:], 16)
        return 0xEFEFEF

    def extension(self, ext: str) -> str:
        ext: str = ext[1:]
        if ext == "ts":
            return "js"
        return ext if ext in DISCORD_MD_LANGS else ""


def setup(bot: commands.Bot) -> None:
    bot.add_cog(Gist(bot))
