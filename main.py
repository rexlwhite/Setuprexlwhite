import os
import discord, typing
from discord import app_commands as app
from discord.ext import commands
from keep_alive import keep_alive

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

class RoleButton(discord.ui.Button):
    def __init__(self, label, style, rid):
        super().__init__(label=label, style=style, custom_id=f"p_{rid}")
        self.rid = rid

    async def callback(self, it: discord.Interaction):
        r = it.guild.get_role(self.rid)
        if not r or it.guild.me.top_role <= r:
            return await it.response.send_message("ไม่พบยศหรือบอทไม่มีสิทธิ์แจกยศนี้", ephemeral=True)

        log = discord.utils.get(it.guild.text_channels, name="บันทึกข้อมูลผู้ใช้")

        if r in it.user.roles:
            await it.user.remove_roles(r)
            await it.response.send_message(f"ถอดยศ {r.name} ออกจากคุณแล้ว", ephemeral=True)

            # ส่งบันทึกข้อมูลการถอนยศแบบ Embed สีแดง
            if log:
                embed_log = discord.Embed(title="บันทึกข้อมูลการถอดยศ", color=discord.Color.red())
                embed_log.set_thumbnail(url=it.user.display_avatar.url)
                embed_log.add_field(name="ผู้ใช้งาน", value=f"{it.user.name} ({it.user.mention})", inline=True)
                embed_log.add_field(name="ยศที่ถูกถอด", value=r.name, inline=True)
                embed_log.set_footer(text=f"ไอดีผู้ใช้: {it.user.id}")
                embed_log.timestamp = discord.utils.utcnow()
                await log.send(embed=embed_log)
        else:
            await it.user.add_roles(r)
            await it.response.send_message(f"มอบยศ {r.name} ให้คุณเรียบร้อยแล้ว", ephemeral=True)

            # ส่งบันทึกข้อมูลการรับยศแบบ Embed สีเขียว
            if log:
                embed_log = discord.Embed(title="บันทึกข้อมูลการรับยศ", color=discord.Color.green())
                embed_log.set_thumbnail(url=it.user.display_avatar.url)
                embed_log.add_field(name="ผู้ใช้งาน", value=f"{it.user.name} ({it.user.mention})", inline=True)
                embed_log.add_field(name="ยศที่ได้รับ", value=r.name, inline=True)
                embed_log.set_footer(text=f"ไอดีผู้ใช้: {it.user.id}")
                embed_log.timestamp = discord.utils.utcnow()
                await log.send(embed=embed_log)

class RoleView(discord.ui.View):
    def __init__(self, label="รับยศ", col="เทา", rid=None):
        super().__init__(timeout=None)
        if rid:
            s = {"แดง": discord.ButtonStyle.danger, "ฟ้า": discord.ButtonStyle.primary, "เขียว": discord.ButtonStyle.success}.get(col, discord.ButtonStyle.secondary)
            self.add_item(RoleButton(label, s, rid))

class TextModal(discord.ui.Modal, title="ตั้งค่าข้อความ"):
    t_in = discord.ui.TextInput(label="หัวข้อหลัก")
    d_in = discord.ui.TextInput(label="รายละเอียดเนื้อหา", style=discord.TextStyle.long)
    a_in = discord.ui.TextInput(label="ชื่อผู้เขียนด้านบนสุด", required=False)
    f_in = discord.ui.TextInput(label="ข้อความท้ายแถบ", required=False)

    def __init__(self, cp):
        super().__init__()
        self.cp = cp
        self.t_in.default, self.d_in.default, self.a_in.default, self.f_in.default = cp.t, cp.d, cp.auth_name, cp.f

    async def on_submit(self, it: discord.Interaction):
        self.cp.t, self.cp.d, self.cp.auth_name, self.cp.f = self.t_in.value, self.d_in.value, self.a_in.value, self.f_in.value
        await self.cp.up(it)

class MediaModal(discord.ui.Modal, title="ตั้งค่ารูปภาพและลิงก์ไอคอน"):
    i_in = discord.ui.TextInput(label="ลิงก์รูปใหญ่ด้านล่าง (Image URL)", required=False)
    m_in = discord.ui.TextInput(label="ลิงก์รูปมุมขวาบน (Thumbnail URL)", required=False)
    ai_in = discord.ui.TextInput(label="ลิงก์ไอคอนรูปผู้เขียนด้านบนสุด", required=False)

    def __init__(self, cp):
        super().__init__()
        self.cp = cp
        self.i_in.default, self.m_in.default, self.ai_in.default = cp.img or "", cp.thmb or "", cp.auth_icon or ""

    async def on_submit(self, it: discord.Interaction):
        self.cp.img = self.i_in.value if self.i_in.value.strip() else None
        self.cp.thmb = self.m_in.value if self.m_in.value.strip() else None
        self.cp.auth_icon = self.ai_in.value if self.ai_in.value.strip() else None
        await self.cp.up(it)

class ControlPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=600)
        self.t, self.d, self.f, self.col, self.b_col, self.img, self.thmb, self.lbl, self.role = "หัวข้อหลัก", "รายละเอียดเนื้อหา", None, "น้ำเงิน", "เทา", None, None, "คลิกรับยศ", None
        self.auth_name, self.auth_icon = None, None

        r_sel = discord.ui.RoleSelect(placeholder="เลือกยศที่ต้องการ", row=0)
        r_sel.callback = self.sel_r
        c_sel = discord.ui.Select(placeholder="เลือกแถบสี", options=[discord.SelectOption(label=f"แถบสี{k}", value=k) for k in ["น้ำเงิน","แดง","เขียว","เหลือง","ดำ"]], row=1)
        c_sel.callback = self.sel_c
        b_sel = discord.ui.Select(placeholder="เลือกสีของปุ่มกด", options=[discord.SelectOption(label=f"ปุ่มสี{k}", value=k) for k in ["เทา","ฟ้า","แดง","เขียว"]], row=2)
        b_sel.callback = self.sel_b

        self.add_item(r_sel); self.add_item(c_sel); self.add_item(b_sel)

    async def sel_r(self, it): 
        if r_sel := it.data.get('values'): self.role = r_sel[0] if isinstance(r_sel, list) else r_sel
        await self.up(it)
    async def sel_c(self, it): 
        if c_sel := it.data.get('values'): self.col = c_sel[0] if isinstance(c_sel, list) else c_sel
        await self.up(it)
    async def sel_b(self, it): 
        if b_sel := it.data.get('values'): self.b_col = b_sel[0] if isinstance(b_sel, list) else b_sel
        await self.up(it)

    def build(self, final=False):
        cls = {"แดง": discord.Color.red(), "เขียว": discord.Color.green(), "เหลือง": discord.Color.gold(), "ดำ": discord.Color.from_rgb(0,0,0)}
        e = discord.Embed(title=self.t, description=self.d, color=cls.get(self.col, discord.Color.blue()))
        if self.auth_name:
            e.set_author(name=self.auth_name, icon_url=self.auth_icon if self.auth_icon else None)
        if self.img: e.set_image(url=self.img)
        if self.thmb: e.set_thumbnail(url=self.thmb)
        if self.f: e.set_footer(text=self.f)

        if final:
            e.timestamp = discord.utils.utcnow()
        else:
            r_m = f"<@&{self.role}>" if self.role else "ยังไม่ได้เลือก"
            e.add_field(name="สถานะระบบแจกยศ", value=f"**ยศที่จะแจก:** {r_m}\n**ข้อความบนปุ่ม:** {self.lbl}\n**สีปุ่ม:** {self.b_col}", inline=False)
        return e

    async def up(self, it): await it.response.edit_message(embed=self.build(), view=self)

    @discord.ui.button(label="แก้ไขข้อความ", style=discord.ButtonStyle.primary, row=3)
    async def edit_t(self, it, b): await it.response.send_modal(TextModal(self))

    @discord.ui.button(label="ตั้งค่ารูปภาพ", style=discord.ButtonStyle.primary, row=3)
    async def edit_m(self, it, b): await it.response.send_modal(MediaModal(self))

    @discord.ui.button(label="แก้ไขชื่อปุ่ม", style=discord.ButtonStyle.primary, row=3)
    async def edit_b(self, it, b):
        m = discord.ui.Modal(title="ชื่อปุ่ม")
        inp = discord.ui.TextInput(label="ข้อความบนปุ่ม", default=self.lbl)
        m.add_item(inp)
        async def submit(i): self.lbl = inp.value; await self.up(i)
        m.on_submit = submit
        await it.response.send_modal(m)

    @discord.ui.button(label="ส่งใช้งานจริง", style=discord.ButtonStyle.success, row=4)
    async def send(self, it, b):
        if not self.role: return await it.response.send_message("กรุณาเลือกยศก่อนส่งจริง", ephemeral=True)
        await it.channel.send(embed=self.build(final=True), view=RoleView(self.lbl, self.b_col, int(self.role)))
        await it.response.edit_message(content="สร้างเสร็จสิ้นแล้ว", embed=None, view=None)

    @discord.ui.button(label="ยกเลิก", style=discord.ButtonStyle.danger, row=4)
    async def cancel(self, it, b): await it.response.edit_message(content="ยกเลิกแล้ว", embed=None, view=None)

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self): 
        keep_alive()
        self.add_view(RoleView())
        try:
            print("กำลังซิงค์คำสั่ง Slash Command...")
            synced = await self.tree.sync()
            print(f"ซิงค์คำสั่งสำเร็จทันที จำนวน {len(synced)} คำสั่ง")
        except Exception as e:
            print(f"เกิดข้อผิดพลาดในการซิงค์คำสั่ง: {e}")

bot = MyBot()

@bot.tree.command(name="setuprexlwhite", description="เปิดแผงตั้งค่ากล่องรับยศผ่าน UI")
@app.checks.has_permissions(manage_roles=True)
async def setup(it):
    p = ControlPanel()
    await it.response.send_message(content="แผงควบคุมระบบสร้างกล่องรับยศ", embed=p.build(), view=p, ephemeral=True)

@bot.event
async def on_ready():
    print(f"บอทพร้อมทำงานเต็มระบบในชื่อ: {bot.user}")
    for guild in bot.guilds:
        existing_channel = discord.utils.get(guild.text_channels, name="บันทึกข้อมูลผู้ใช้")
        if not existing_channel:
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(view_channel=False),
                guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True)
            }
            await guild.create_text_channel("บันทึกข้อมูลผู้ใช้", overwrites=overwrites)
            print(f"สร้างห้องบันทึกข้อมูลอัตโนมัติในเซิร์ฟเวอร์ {guild.name} สำเร็จ")

keep_alive()

bot.run(os.getenv("TOKEN"))
