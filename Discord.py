import discord
from discord import app_commands, Interaction
from discord.ext import commands, tasks
import json
import os
import random
import asyncio
from typing import Optional, List, Dict
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

# ---------------- CONFIG ----------------
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID", "1443109274904563817"))
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID", "1443188048467853383"))
DATA_FILE = "nations_data.json"
# ---------------------------------------

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

# ---------------- UNIT DEFINITIONS ----------------
UNIT_TYPES = {
    "Infantry": {"cost": 10, "power": 5, "upkeep": 1, "manpower": 1},
    "Light Tank": {"cost": 50, "power": 30, "upkeep": 5, "manpower": 3},
    "MBT": {"cost": 120, "power": 80, "upkeep": 12, "manpower": 5},
    "Artillery": {"cost": 70, "power": 40, "upkeep": 6, "manpower": 4},
    "Fighter": {"cost": 200, "power": 150, "upkeep": 20, "manpower": 2},
    "Helicopter": {"cost": 150, "power": 90, "upkeep": 12, "manpower": 3},
    "Submarine": {"cost": 180, "power": 110, "upkeep": 15, "manpower": 8},
    "Destroyer": {"cost": 250, "power": 160, "upkeep": 25, "manpower": 12},
    "Elite Forces": {"cost": 500, "power": 300, "upkeep": 40, "manpower": 10},
    "Nuclear Missile": {"cost": 5000, "power": 10000, "upkeep": 200, "manpower": 50},
}

# ---------------- TECHNOLOGY TREE ----------------
TECHNOLOGIES = {
    "Advanced Farming": {
        "cost_research": 100,
        "cost_political": 20,
        "effect": "population_growth_multiplier",
        "value": 1.5,
        "description": "+50% population growth"
    },
    "Industrial Revolution": {
        "cost_research": 200,
        "cost_political": 40,
        "effect": "resource_multiplier",
        "value": 1.5,
        "description": "+50% resource generation",
        "requires": ["Advanced Farming"]
    },
    "Military Tactics": {
        "cost_research": 150,
        "cost_political": 30,
        "effect": "unit_power_bonus",
        "value": 1.2,
        "description": "+20% unit power"
    },
    "Mass Conscription": {
        "cost_research": 120,
        "cost_political": 25,
        "effect": "manpower_multiplier",
        "value": 2.0,
        "description": "+100% manpower generation"
    },
    "Advanced Logistics": {
        "cost_research": 180,
        "cost_political": 35,
        "effect": "upkeep_reduction",
        "value": 0.8,
        "description": "-20% unit upkeep",
        "requires": ["Military Tactics"]
    },
    "Nuclear Program": {
        "cost_research": 1000,
        "cost_political": 200,
        "effect": "unlock_nukes",
        "value": 1,
        "description": "Unlock nuclear missiles",
        "requires": ["Industrial Revolution", "Advanced Logistics"]
    },
    "Espionage Network": {
        "cost_research": 250,
        "cost_political": 50,
        "effect": "spy_success_bonus",
        "value": 1.3,
        "description": "+30% spy mission success rate"
    },
}

# ---------------- BUILDINGS ----------------
BUILDINGS = {
    "Farm": {
        "cost": 50,
        "effect": "population_growth",
        "value": 10,
        "description": "+10 population per tick"
    },
    "Factory": {
        "cost": 100,
        "effect": "resource_production",
        "value": 20,
        "description": "+20 resources per tick"
    },
    "Barracks": {
        "cost": 80,
        "effect": "manpower_production",
        "value": 15,
        "description": "+15 manpower per tick"
    },
    "Research Lab": {
        "cost": 150,
        "effect": "research_production",
        "value": 5,
        "description": "+5 research points per tick"
    },
    "Government Complex": {
        "cost": 200,
        "effect": "political_production",
        "value": 3,
        "description": "+3 political points per tick"
    },
}

# ---------------- RANDOM EVENTS ----------------
RANDOM_EVENTS = [
    {"name": "Golden Age", "effect": "resources", "value": 100, "chance": 0.05},
    {"name": "Population Boom", "effect": "population", "value": 500, "chance": 0.05},
    {"name": "Earthquake", "effect": "resources", "value": -50, "chance": 0.03},
    {"name": "Plague", "effect": "population", "value": -200, "chance": 0.02},
    {"name": "Military Parade", "effect": "political_points", "value": 10, "chance": 0.04},
    {"name": "Scientific Breakthrough", "effect": "research_points", "value": 20, "chance": 0.04},
]


# ---------------- BOT CLASS ----------------
class PaxHistoriaBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        self.nations: Dict[str, dict] = {}
        self.alliances: Dict[str, dict] = {}
        self.wars: List[dict] = []
        self.trade_offers: List[dict] = []

    async def setup_hook(self) -> None:
        self.load_data()
        guild = discord.Object(id=GUILD_ID)
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)
        print(f"Bot Online as {self.user} (commands synced in guild {GUILD_ID})")
        self.real_time_growth_loop.start()
        self.passive_growth_loop.start()
        self.random_events_loop.start()

    def load_data(self) -> None:
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.nations = data.get("nations", {})
                    self.alliances = data.get("alliances", {})
                    self.wars = data.get("wars", [])
                    self.trade_offers = data.get("trade_offers", [])
                print(f"Loaded {len(self.nations)} nations, {len(self.alliances)} alliances")
            except Exception as e:
                print(f"Failed loading data: {e}")
                self.nations = {}
                self.alliances = {}
                self.wars = []
                self.trade_offers = []
        else:
            self.nations = {}
            self.alliances = {}
            self.wars = []
            self.trade_offers = []

    def save_data(self) -> None:
        try:
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump({
                    "nations": self.nations,
                    "alliances": self.alliances,
                    "wars": self.wars,
                    "trade_offers": self.trade_offers
                }, f, indent=4)
        except Exception as e:
            print(f"Failed saving data: {e}")

    def calculate_passive_income(self, nation: dict) -> dict:
        """Calculate passive income based on territory, buildings, and tech"""
        base_resources = 1  # Per second
        base_manpower = 0.5
        base_research = 0.1
        base_political = 0.05
        base_population = 0.2

        # Territory multiplier
        territory_mult = 1 + (nation.get("territory", 1) * 0.1)

        # Tech multipliers
        tech_list = nation.get("technologies", [])
        resource_mult = 1.5 if "Industrial Revolution" in tech_list else 1.0
        pop_mult = 1.5 if "Advanced Farming" in tech_list else 1.0
        manpower_mult = 2.0 if "Mass Conscription" in tech_list else 1.0

        # Building bonuses
        buildings = nation.get("buildings", {})
        building_resources = buildings.get("Factory", 0) * 0.3  # Per second
        building_manpower = buildings.get("Barracks", 0) * 0.2
        building_research = buildings.get("Research Lab", 0) * 0.08
        building_political = buildings.get("Government Complex", 0) * 0.05
        building_population = buildings.get("Farm", 0) * 0.15

        return {
            "resources": (base_resources * territory_mult * resource_mult) + building_resources,
            "manpower": (base_manpower * territory_mult * manpower_mult) + building_manpower,
            "research_points": (base_research * territory_mult) + building_research,
            "political_points": (base_political * territory_mult) + building_political,
            "population": (base_population * territory_mult * pop_mult) + building_population
        }

    @tasks.loop(seconds=1)
    async def real_time_growth_loop(self) -> None:
        """Update nations every second for real-time resource generation"""
        for user_id, nation in self.nations.items():
            income = self.calculate_passive_income(nation)

            nation["resources"] = nation.get("resources", 0) + income["resources"]
            nation["manpower"] = nation.get("manpower", 0) + income["manpower"]
            nation["research_points"] = nation.get("research_points", 0) + income["research_points"]
            nation["political_points"] = nation.get("political_points", 0) + income["political_points"]
            nation["population"] = nation.get("population", 0) + income["population"]

            # Cap resources to prevent overflow
            nation["resources"] = min(nation["resources"], 999999)
            nation["manpower"] = min(nation["manpower"], 999999)
            nation["research_points"] = min(nation["research_points"], 99999)
            nation["political_points"] = min(nation["political_points"], 99999)
            nation["population"] = min(nation["population"], 9999999)

        # Auto-save every 30 seconds
        if hasattr(self, '_save_counter'):
            self._save_counter += 1
        else:
            self._save_counter = 1

        if self._save_counter >= 30:
            self.save_data()
            self._save_counter = 0

    @tasks.loop(minutes=5)
    async def passive_growth_loop(self) -> None:
        """Handle upkeep and larger events every 5 minutes"""
        log_channel: Optional[discord.TextChannel] = self.get_channel(LOG_CHANNEL_ID)

        for user_id, nation in self.nations.items():
            # Calculate total upkeep
            total_upkeep = sum(
                UNIT_TYPES[unit]["upkeep"] * qty
                for unit, qty in nation.get("units", {}).items()
                if unit in UNIT_TYPES
            )

            # Apply tech reductions
            if "Advanced Logistics" in nation.get("technologies", []):
                total_upkeep *= 0.8

            total_upkeep = int(total_upkeep)

            # Handle upkeep
            if total_upkeep > 0:
                if nation["resources"] >= total_upkeep:
                    nation["resources"] -= total_upkeep
                    status = f"✅ Paid {total_upkeep} upkeep"
                else:
                    paid = int(nation["resources"])
                    nation["resources"] = 0
                    shortfall = total_upkeep - paid
                    fraction_unpaid = shortfall / total_upkeep

                    status = f"⚠️ Could only pay {paid}/{total_upkeep} upkeep - losing units!"

                    for unit_name, qty in list(nation.get("units", {}).items()):
                        to_remove = max(1, int(qty * fraction_unpaid * 0.5))
                        if to_remove > 0 and qty > 0:
                            nation["units"][unit_name] = max(0, qty - to_remove)
                            power_lost = UNIT_TYPES[unit_name]["power"] * to_remove
                            nation["military_power"] = max(0, nation["military_power"] - power_lost)

                if log_channel:
                    try:
                        await log_channel.send(f"**{nation['name']}**: {status}")
                    except:
                        pass

        self.save_data()

    @tasks.loop(minutes=10)
    async def random_events_loop(self) -> None:
        """Trigger random events for nations"""
        log_channel: Optional[discord.TextChannel] = self.get_channel(LOG_CHANNEL_ID)

        for user_id, nation in self.nations.items():
            for event in RANDOM_EVENTS:
                if random.random() < event["chance"]:
                    effect = event["effect"]
                    value = event["value"]

                    if effect in nation:
                        nation[effect] = max(0, nation[effect] + value)

                        symbol = "🎉" if value > 0 else "⚠️"
                        sign = "+" if value > 0 else ""

                        message = f"{symbol} **{nation['name']}** experienced **{event['name']}**! {sign}{value} {effect.replace('_', ' ')}"
                        nation["history"].append(message)

                        if log_channel:
                            try:
                                await log_channel.send(message)
                            except:
                                pass
                    break

        self.save_data()

    @real_time_growth_loop.before_loop
    @passive_growth_loop.before_loop
    @random_events_loop.before_loop
    async def before_loops(self) -> None:
        await self.wait_until_ready()


bot = PaxHistoriaBot()


# ---------------- HELPERS ----------------
def has_nation():
    async def predicate(interaction: Interaction) -> bool:
        uid = str(interaction.user.id)
        if uid not in bot.nations:
            await interaction.response.send_message("❌ You don't have a nation yet. Use `/create_nation` first.",
                                                    ephemeral=True)
            return False
        return True

    return app_commands.check(predicate)


def append_history(user_id: str, text: str, major: bool = False) -> None:
    bot.nations[user_id]["history"].append(text)
    if major:
        log_channel: Optional[discord.TextChannel] = bot.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            try:
                bot.loop.create_task(log_channel.send(text))
            except:
                pass


# ---------------- NATION MANAGEMENT ----------------
@bot.tree.command(name="create_nation", description="Create your nation")
@app_commands.describe(nation_name="Name for your nation")
async def create_nation(interaction: Interaction, nation_name: str):
    uid = str(interaction.user.id)
    if uid in bot.nations:
        await interaction.response.send_message("❌ You already have a nation.", ephemeral=True)
        return

    bot.nations[uid] = {
        "name": nation_name,
        "population": 1000,
        "resources": 100,
        "manpower": 50,
        "research_points": 0,
        "political_points": 0,
        "military_power": 50,
        "territory": 1,
        "units": {},
        "technologies": [],
        "buildings": {},
        "alliance": None,
        "history": [f"Nation created: {nation_name}"]
    }
    bot.save_data()

    embed = discord.Embed(title=f"🏛️ {nation_name} Founded!", color=discord.Color.green())
    embed.add_field(name="👥 Population", value="1,000", inline=True)
    embed.add_field(name="💰 Resources", value="100", inline=True)
    embed.add_field(name="🪖 Manpower", value="50", inline=True)
    embed.add_field(name="🗺️ Territory", value="1", inline=True)
    embed.set_footer(text="Your nation will now generate resources in real-time!")

    await interaction.response.send_message(embed=embed, ephemeral=True)

    log_ch: Optional[discord.TextChannel] = bot.get_channel(LOG_CHANNEL_ID)
    if log_ch:
        try:
            await log_ch.send(f"🗺️ New nation founded: **{nation_name}** (Leader: {interaction.user.display_name})")
        except:
            pass


@bot.tree.command(name="nation_status", description="View your nation's current status")
@has_nation()
async def nation_status(interaction: Interaction):
    uid = str(interaction.user.id)
    nation = bot.nations[uid]

    income = bot.calculate_passive_income(nation)

    embed = discord.Embed(title=f"🏛️ {nation['name']}", color=discord.Color.blue())
    embed.add_field(name="👥 Population", value=f"{int(nation['population']):,} (+{income['population']:.1f}/s)",
                    inline=True)
    embed.add_field(name="💰 Resources", value=f"{int(nation['resources']):,} (+{income['resources']:.1f}/s)",
                    inline=True)
    embed.add_field(name="🪖 Manpower", value=f"{int(nation['manpower']):,} (+{income['manpower']:.1f}/s)", inline=True)
    embed.add_field(name="🔬 Research", value=f"{int(nation['research_points']):,} (+{income['research_points']:.1f}/s)",
                    inline=True)
    embed.add_field(name="🏛️ Political",
                    value=f"{int(nation['political_points']):,} (+{income['political_points']:.1f}/s)", inline=True)
    embed.add_field(name="⚔️ Military Power", value=f"{nation['military_power']:,}", inline=True)
    embed.add_field(name="🗺️ Territory", value=f"{nation['territory']}", inline=True)

    if nation.get("alliance"):
        embed.add_field(name="🤝 Alliance", value=nation["alliance"], inline=True)

    await interaction.response.send_message(embed=embed)

# Continuing in next part due to length...

# ADD THESE COMMANDS TO THE MAIN BOT FILE (after nation_status)

# ---------------- MILITARY COMMANDS ----------------
@bot.tree.command(name="train_units", description="Train military units")
@app_commands.describe(unit_type="Type of unit", quantity="Number of units")
@has_nation()
async def train_units(interaction: Interaction, unit_type: str, quantity: int):
    uid = str(interaction.user.id)
    nation = bot.nations[uid]

    if unit_type not in UNIT_TYPES:
        await interaction.response.send_message(f"❌ Invalid unit. Use `/list_units`", ephemeral=True)
        return

    if quantity <= 0:
        await interaction.response.send_message("❌ Quantity must be positive.", ephemeral=True)
        return

    # Check for nuclear unlock
    if unit_type == "Nuclear Missile" and "Nuclear Program" not in nation.get("technologies", []):
        await interaction.response.send_message("❌ You need to research **Nuclear Program** first!", ephemeral=True)
        return

    unit_info = UNIT_TYPES[unit_type]
    total_cost = unit_info["cost"] * quantity
    total_manpower = unit_info["manpower"] * quantity

    if nation["resources"] < total_cost:
        await interaction.response.send_message(f"❌ Need {total_cost:,} resources (have {int(nation['resources']):,})",
                                                ephemeral=True)
        return

    if nation["manpower"] < total_manpower:
        await interaction.response.send_message(
            f"❌ Need {total_manpower:,} manpower (have {int(nation['manpower']):,})", ephemeral=True)
        return

    nation["resources"] -= total_cost
    nation["manpower"] -= total_manpower
    nation["units"][unit_type] = nation["units"].get(unit_type, 0) + quantity

    power_gain = unit_info["power"] * quantity
    if "Military Tactics" in nation.get("technologies", []):
        power_gain = int(power_gain * 1.2)

    nation["military_power"] += power_gain

    log_text = f"⚔️ {nation['name']} trained {quantity}x {unit_type} (+{power_gain} power)"
    append_history(uid, log_text, major=True)
    bot.save_data()

    await interaction.response.send_message(
        f"✅ Trained {quantity}x **{unit_type}**!\n"
        f"💰 Cost: {total_cost:,} resources\n"
        f"🪖 Manpower: {total_manpower:,}\n"
        f"⚔️ Power: +{power_gain:,}\n"
        f"🛡️ Upkeep: {unit_info['upkeep'] * quantity}/tick"
    )


@bot.tree.command(name="disband_units", description="Disband units")
@app_commands.describe(unit_type="Type of unit", quantity="Number to disband")
@has_nation()
async def disband_units(interaction: Interaction, unit_type: str, quantity: int):
    uid = str(interaction.user.id)
    nation = bot.nations[uid]

    if unit_type not in nation.get("units", {}) or nation["units"][unit_type] < quantity:
        await interaction.response.send_message(f"❌ You don't have {quantity}x {unit_type}", ephemeral=True)
        return

    unit_info = UNIT_TYPES[unit_type]
    nation["units"][unit_type] -= quantity
    power_loss = unit_info["power"] * quantity
    nation["military_power"] = max(0, nation["military_power"] - power_loss)

    # Refund some manpower
    manpower_refund = unit_info["manpower"] * quantity // 2
    nation["manpower"] += manpower_refund

    append_history(uid, f"🔻 Disbanded {quantity}x {unit_type}")
    bot.save_data()

    await interaction.response.send_message(
        f"✅ Disbanded {quantity}x **{unit_type}** (-{power_loss:,} power, +{manpower_refund} manpower)")


# ---------------- TECHNOLOGY ----------------
@bot.tree.command(name="research", description="Research a technology")
@app_commands.describe(tech_name="Technology to research")
@has_nation()
async def research(interaction: Interaction, tech_name: str):
    uid = str(interaction.user.id)
    nation = bot.nations[uid]

    if tech_name not in TECHNOLOGIES:
        await interaction.response.send_message(f"❌ Invalid tech. Use `/view_tech`", ephemeral=True)
        return

    if tech_name in nation.get("technologies", []):
        await interaction.response.send_message(f"❌ Already researched **{tech_name}**", ephemeral=True)
        return

    tech = TECHNOLOGIES[tech_name]

    # Check prerequisites
    if "requires" in tech:
        missing = [req for req in tech["requires"] if req not in nation.get("technologies", [])]
        if missing:
            await interaction.response.send_message(f"❌ Requires: {', '.join(missing)}", ephemeral=True)
            return

    if nation["research_points"] < tech["cost_research"]:
        await interaction.response.send_message(
            f"❌ Need {tech['cost_research']} research (have {int(nation['research_points'])})", ephemeral=True)
        return

    if nation["political_points"] < tech["cost_political"]:
        await interaction.response.send_message(
            f"❌ Need {tech['cost_political']} political (have {int(nation['political_points'])})", ephemeral=True)
        return

    nation["research_points"] -= tech["cost_research"]
    nation["political_points"] -= tech["cost_political"]
    nation["technologies"].append(tech_name)

    log_text = f"🔬 {nation['name']} researched **{tech_name}**!"
    append_history(uid, log_text, major=True)
    bot.save_data()

    embed = discord.Embed(title=f"🔬 Research Complete!", color=discord.Color.gold())
    embed.add_field(name="Technology", value=tech_name, inline=False)
    embed.add_field(name="Effect", value=tech["description"], inline=False)
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="view_tech", description="View available technologies")
@has_nation()
async def view_tech(interaction: Interaction):
    uid = str(interaction.user.id)
    nation = bot.nations[uid]

    embed = discord.Embed(title="🔬 Technology Tree", color=discord.Color.purple())

    for tech_name, tech in TECHNOLOGIES.items():
        status = "✅" if tech_name in nation.get("technologies", []) else "🔒"

        requirements = ""
        if "requires" in tech:
            requirements = f"\nRequires: {', '.join(tech['requires'])}"

        embed.add_field(
            name=f"{status} {tech_name}",
            value=f"{tech['description']}\n🔬 {tech['cost_research']} Research | 🏛️ {tech['cost_political']} Political{requirements}",
            inline=False
        )

    await interaction.response.send_message(embed=embed)


# ---------------- BUILDINGS ----------------
@bot.tree.command(name="construct_building", description="Construct a building")
@app_commands.describe(building_type="Type of building", quantity="Number to build")
@has_nation()
async def construct_building(interaction: Interaction, building_type: str, quantity: int):
    uid = str(interaction.user.id)
    nation = bot.nations[uid]

    if building_type not in BUILDINGS:
        await interaction.response.send_message(f"❌ Invalid building. Use `/list_buildings`", ephemeral=True)
        return

    if quantity <= 0:
        await interaction.response.send_message("❌ Quantity must be positive", ephemeral=True)
        return

    building = BUILDINGS[building_type]
    total_cost = building["cost"] * quantity

    if nation["resources"] < total_cost:
        await interaction.response.send_message(f"❌ Need {total_cost:,} resources", ephemeral=True)
        return

    nation["resources"] -= total_cost
    nation["buildings"][building_type] = nation["buildings"].get(building_type, 0) + quantity

    append_history(uid, f"🏗️ Built {quantity}x {building_type}")
    bot.save_data()

    await interaction.response.send_message(
        f"✅ Constructed {quantity}x **{building_type}**!\n"
        f"💰 Cost: {total_cost:,}\n"
        f"📈 Effect: {building['description']}"
    )


@bot.tree.command(name="list_buildings", description="View all buildings")
async def list_buildings(interaction: Interaction):
    embed = discord.Embed(title="🏗️ Available Buildings", color=discord.Color.green())

    for building_name, building in BUILDINGS.items():
        embed.add_field(
            name=building_name,
            value=f"Cost: {building['cost']}\n{building['description']}",
            inline=True
        )

    await interaction.response.send_message(embed=embed)


# ---------------- TERRITORY ----------------
@bot.tree.command(name="expand_territory", description="Expand your nation's territory")
@has_nation()
async def expand_territory(interaction: Interaction):
    uid = str(interaction.user.id)
    nation = bot.nations[uid]

    current_territory = nation.get("territory", 1)
    cost = 500 * (current_territory ** 1.5)
    cost = int(cost)

    if nation["resources"] < cost:
        await interaction.response.send_message(f"❌ Need {cost:,} resources to expand", ephemeral=True)
        return

    nation["resources"] -= cost
    nation["territory"] += 1

    log_text = f"🗺️ {nation['name']} expanded to {nation['territory']} territories!"
    append_history(uid, log_text, major=True)
    bot.save_data()

    await interaction.response.send_message(
        f"✅ Territory expanded to **{nation['territory']}**!\n"
        f"💰 Cost: {cost:,}\n"
        f"📈 +10% passive income per territory"
    )


# ---------------- ALLIANCES ----------------
@bot.tree.command(name="create_alliance", description="Create an alliance")
@app_commands.describe(alliance_name="Name of the alliance")
@has_nation()
async def create_alliance(interaction: Interaction, alliance_name: str):
    uid = str(interaction.user.id)
    nation = bot.nations[uid]

    if nation.get("alliance"):
        await interaction.response.send_message("❌ You're already in an alliance", ephemeral=True)
        return

    if alliance_name in bot.alliances:
        await interaction.response.send_message("❌ Alliance name taken", ephemeral=True)
        return

    cost = 1000
    if nation["resources"] < cost:
        await interaction.response.send_message(f"❌ Need {cost:,} resources", ephemeral=True)
        return

    nation["resources"] -= cost
    nation["alliance"] = alliance_name

    bot.alliances[alliance_name] = {
        "leader": uid,
        "members": [uid],
        "invites": []
    }

    append_history(uid, f"🤝 Created alliance: {alliance_name}", major=True)
    bot.save_data()

    await interaction.response.send_message(f"✅ Alliance **{alliance_name}** created!")


@bot.tree.command(name="invite_to_alliance", description="Invite a nation to your alliance")
@app_commands.describe(target_user="User to invite")
@has_nation()
async def invite_alliance(interaction: Interaction, target_user: discord.User):
    uid = str(interaction.user.id)
    target_uid = str(target_user.id)
    nation = bot.nations[uid]

    if not nation.get("alliance"):
        await interaction.response.send_message("❌ You're not in an alliance", ephemeral=True)
        return

    alliance_name = nation["alliance"]
    alliance = bot.alliances[alliance_name]

    if alliance["leader"] != uid:
        await interaction.response.send_message("❌ Only the alliance leader can invite", ephemeral=True)
        return

    if target_uid not in bot.nations:
        await interaction.response.send_message("❌ Target doesn't have a nation", ephemeral=True)
        return

    if bot.nations[target_uid].get("alliance"):
        await interaction.response.send_message("❌ Target is already in an alliance", ephemeral=True)
        return

    if target_uid in alliance["invites"]:
        await interaction.response.send_message("❌ Already invited", ephemeral=True)
        return

    alliance["invites"].append(target_uid)
    bot.save_data()

    await interaction.response.send_message(f"✅ Invited **{bot.nations[target_uid]['name']}** to {alliance_name}")


@bot.tree.command(name="join_alliance", description="Join an alliance you were invited to")
@app_commands.describe(alliance_name="Alliance to join")
@has_nation()
async def join_alliance(interaction: Interaction, alliance_name: str):
    uid = str(interaction.user.id)
    nation = bot.nations[uid]

    if nation.get("alliance"):
        await interaction.response.send_message("❌ Leave your current alliance first", ephemeral=True)
        return

    if alliance_name not in bot.alliances:
        await interaction.response.send_message("❌ Alliance doesn't exist", ephemeral=True)
        return

    alliance = bot.alliances[alliance_name]

    if uid not in alliance["invites"]:
        await interaction.response.send_message("❌ You weren't invited", ephemeral=True)
        return

    alliance["invites"].remove(uid)
    alliance["members"].append(uid)
    nation["alliance"] = alliance_name

    append_history(uid, f"🤝 Joined alliance: {alliance_name}", major=True)
    bot.save_data()

    await interaction.response.send_message(f"✅ Joined **{alliance_name}**!")

# Continue with more commands...

# ADD THESE TO THE MAIN BOT FILE (continuation)

# ---------------- COMBAT SYSTEM ----------------
@bot.tree.command(name="declare_war", description="Declare war on another nation")
@app_commands.describe(target_user="Nation to declare war on")
@has_nation()
async def declare_war(interaction: Interaction, target_user: discord.User):
    uid = str(interaction.user.id)
    target_uid = str(target_user.id)

    if uid == target_uid:
        await interaction.response.send_message("❌ Can't declare war on yourself", ephemeral=True)
        return

    if target_uid not in bot.nations:
        await interaction.response.send_message("❌ Target doesn't have a nation", ephemeral=True)
        return

    # Check if already at war
    for war in bot.wars:
        if (war["attacker"] == uid and war["defender"] == target_uid) or \
                (war["attacker"] == target_uid and war["defender"] == uid):
            await interaction.response.send_message("❌ Already at war", ephemeral=True)
            return

    # Can't attack allies
    attacker_alliance = bot.nations[uid].get("alliance")
    defender_alliance = bot.nations[target_uid].get("alliance")
    if attacker_alliance and attacker_alliance == defender_alliance:
        await interaction.response.send_message("❌ Can't attack alliance members", ephemeral=True)
        return

    bot.wars.append({
        "attacker": uid,
        "defender": target_uid,
        "attacker_score": 0,
        "defender_score": 0,
        "battles": []
    })

    attacker_name = bot.nations[uid]["name"]
    defender_name = bot.nations[target_uid]["name"]

    log_text = f"⚔️ **WAR DECLARED!** {attacker_name} vs {defender_name}"
    append_history(uid, log_text, major=True)
    append_history(target_uid, log_text, major=True)
    bot.save_data()

    await interaction.response.send_message(
        f"⚔️ War declared against **{defender_name}**!\nUse `/attack` to launch battles.")


@bot.tree.command(name="attack", description="Launch an attack in an active war")
@app_commands.describe(target_user="Enemy to attack")
@has_nation()
async def attack(interaction: Interaction, target_user: discord.User):
    uid = str(interaction.user.id)
    target_uid = str(target_user.id)

    # Find active war
    war = None
    is_attacker = False
    for w in bot.wars:
        if w["attacker"] == uid and w["defender"] == target_uid:
            war = w
            is_attacker = True
            break
        elif w["attacker"] == target_uid and w["defender"] == uid:
            war = w
            is_attacker = False
            break

    if not war:
        await interaction.response.send_message("❌ Not at war with this nation", ephemeral=True)
        return

    attacker = bot.nations[uid]
    defender = bot.nations[target_uid]

    if attacker["military_power"] <= 0:
        await interaction.response.send_message("❌ No military power", ephemeral=True)
        return

    # Calculate combat
    att_power = attacker["military_power"]
    def_power = defender["military_power"]

    # Defender bonus
    def_power = int(def_power * 1.15)

    # Tech bonuses
    if "Military Tactics" in attacker.get("technologies", []):
        att_power = int(att_power * 1.2)
    if "Military Tactics" in defender.get("technologies", []):
        def_power = int(def_power * 1.2)

    total_power = att_power + def_power
    att_win_chance = att_power / total_power if total_power > 0 else 0.5

    attacker_wins = random.random() < att_win_chance

    if attacker_wins:
        # Attacker wins
        resources_plunder = min(int(defender["resources"]), int(defender["resources"] * 0.3) + 100)
        pop_captured = min(int(defender["population"]), int(defender["population"] * 0.1))

        attacker["resources"] += resources_plunder
        attacker["population"] += pop_captured
        defender["resources"] = max(0, defender["resources"] - resources_plunder)
        defender["population"] = max(100, defender["population"] - pop_captured)

        # Casualties
        att_losses = int(att_power * random.uniform(0.05, 0.15))
        def_losses = int(def_power * random.uniform(0.25, 0.40))

        attacker["military_power"] = max(0, attacker["military_power"] - att_losses)
        defender["military_power"] = max(0, defender["military_power"] - def_losses)

        # War score
        if is_attacker:
            war["attacker_score"] += 1
        else:
            war["defender_score"] += 1

        result_embed = discord.Embed(title="🎖️ VICTORY!", color=discord.Color.green())
        result_embed.add_field(name="Plundered",
                               value=f"💰 {resources_plunder:,} resources\n👥 {pop_captured:,} population", inline=False)
        result_embed.add_field(name="Your Losses", value=f"⚔️ {att_losses:,} power", inline=True)
        result_embed.add_field(name="Enemy Losses", value=f"⚔️ {def_losses:,} power", inline=True)

        log_text = f"⚔️ {attacker['name']} defeated {defender['name']} in battle!"
    else:
        # Defender wins
        att_losses = int(att_power * random.uniform(0.30, 0.45))
        def_losses = int(def_power * random.uniform(0.10, 0.20))

        attacker["military_power"] = max(0, attacker["military_power"] - att_losses)
        defender["military_power"] = max(0, defender["military_power"] - def_losses)

        # War score
        if is_attacker:
            war["defender_score"] += 1
        else:
            war["attacker_score"] += 1

        result_embed = discord.Embed(title="💔 DEFEAT!", color=discord.Color.red())
        result_embed.add_field(name="Your Losses", value=f"⚔️ {att_losses:,} power", inline=True)
        result_embed.add_field(name="Enemy Losses", value=f"⚔️ {def_losses:,} power", inline=True)

        log_text = f"🛡️ {defender['name']} repelled {attacker['name']}'s attack!"

    war["battles"].append({
        "winner": uid if attacker_wins else target_uid,
        "att_losses": att_losses,
        "def_losses": def_losses
    })

    result_embed.add_field(name="War Score", value=f"{war['attacker_score']} - {war['defender_score']}", inline=False)

    append_history(uid, log_text, major=True)
    append_history(target_uid, log_text, major=True)
    bot.save_data()

    await interaction.response.send_message(embed=result_embed)


@bot.tree.command(name="make_peace", description="End an active war")
@app_commands.describe(target_user="Nation to make peace with")
@has_nation()
async def make_peace(interaction: Interaction, target_user: discord.User):
    uid = str(interaction.user.id)
    target_uid = str(target_user.id)

    # Find and remove war
    war_found = False
    for i, war in enumerate(bot.wars):
        if (war["attacker"] == uid and war["defender"] == target_uid) or \
                (war["attacker"] == target_uid and war["defender"] == uid):
            bot.wars.pop(i)
            war_found = True
            break

    if not war_found:
        await interaction.response.send_message("❌ Not at war", ephemeral=True)
        return

    log_text = f"🕊️ Peace treaty signed between {bot.nations[uid]['name']} and {bot.nations[target_uid]['name']}"
    append_history(uid, log_text, major=True)
    append_history(target_uid, log_text, major=True)
    bot.save_data()

    await interaction.response.send_message(f"✅ Peace treaty signed!")


# ---------------- ESPIONAGE ----------------
@bot.tree.command(name="spy_on", description="Spy on another nation")
@app_commands.describe(target_user="Nation to spy on")
@has_nation()
async def spy_on(interaction: Interaction, target_user: discord.User):
    uid = str(interaction.user.id)
    target_uid = str(target_user.id)

    if target_uid not in bot.nations:
        await interaction.response.send_message("❌ Target doesn't have a nation", ephemeral=True)
        return

    nation = bot.nations[uid]
    target = bot.nations[target_uid]

    cost = 100
    if nation["resources"] < cost:
        await interaction.response.send_message(f"❌ Need {cost} resources", ephemeral=True)
        return

    nation["resources"] -= cost

    # Success chance
    base_chance = 0.65
    if "Espionage Network" in nation.get("technologies", []):
        base_chance = 0.85

    success = random.random() < base_chance

    if success:
        embed = discord.Embed(title=f"🕵️ Intel Report: {target['name']}", color=discord.Color.dark_grey())
        embed.add_field(name="Military Power", value=f"{target['military_power']:,}", inline=True)
        embed.add_field(name="Resources", value=f"~{int(target['resources'] * random.uniform(0.8, 1.2)):,}",
                        inline=True)
        embed.add_field(name="Territory", value=f"{target['territory']}", inline=True)

        # Show some units
        if target.get("units"):
            units_str = "\n".join([f"{unit}: ~{int(qty * random.uniform(0.7, 1.3))}"
                                   for unit, qty in list(target["units"].items())[:3]])
            embed.add_field(name="Military Units (Est.)", value=units_str, inline=False)

        append_history(uid, f"🕵️ Successfully spied on {target['name']}")
        await interaction.response.send_message(embed=embed, ephemeral=True)
    else:
        append_history(uid, f"🕵️ Spy mission failed on {target['name']}")
        append_history(target_uid, f"⚠️ Detected spy attempt from {nation['name']}", major=True)
        await interaction.response.send_message("❌ Spy mission failed! You were detected.", ephemeral=True)

    bot.save_data()


@bot.tree.command(name="sabotage", description="Sabotage an enemy nation")
@app_commands.describe(target_user="Nation to sabotage")
@has_nation()
async def sabotage(interaction: Interaction, target_user: discord.User):
    uid = str(interaction.user.id)
    target_uid = str(target_user.id)

    if target_uid not in bot.nations:
        await interaction.response.send_message("❌ Target doesn't have a nation", ephemeral=True)
        return

    nation = bot.nations[uid]
    target = bot.nations[target_uid]

    cost = 250
    if nation["resources"] < cost:
        await interaction.response.send_message(f"❌ Need {cost} resources", ephemeral=True)
        return

    nation["resources"] -= cost

    # Success chance (harder than spying)
    base_chance = 0.45
    if "Espionage Network" in nation.get("technologies", []):
        base_chance = 0.60

    success = random.random() < base_chance

    if success:
        # Random sabotage effect
        effects = [
            ("resources", int(target["resources"] * 0.15), "resources destroyed"),
            ("military_power", int(target["military_power"] * 0.10), "military power lost"),
            ("population", int(target["population"] * 0.05), "population casualties"),
        ]

        effect_type, damage, description = random.choice(effects)
        target[effect_type] = max(0, target[effect_type] - damage)

        log_text = f"💥 {nation['name']} sabotaged {target['name']}: {damage:,} {description}!"
        append_history(uid, log_text, major=True)
        append_history(target_uid, log_text, major=True)

        await interaction.response.send_message(f"✅ Sabotage successful! Dealt {damage:,} {description}",
                                                ephemeral=True)
    else:
        append_history(uid, f"💥 Sabotage mission failed on {target['name']}")
        append_history(target_uid, f"⚠️ Foiled sabotage attempt from {nation['name']}", major=True)
        await interaction.response.send_message("❌ Sabotage failed! You were caught.", ephemeral=True)

    bot.save_data()


# ---------------- TRADE ----------------
@bot.tree.command(name="send_resources", description="Send resources to another nation")
@app_commands.describe(target_user="Nation to send to", amount="Amount of resources")
@has_nation()
async def send_resources(interaction: Interaction, target_user: discord.User, amount: int):
    uid = str(interaction.user.id)
    target_uid = str(target_user.id)

    if target_uid not in bot.nations:
        await interaction.response.send_message("❌ Target doesn't have a nation", ephemeral=True)
        return

    if amount <= 0:
        await interaction.response.send_message("❌ Amount must be positive", ephemeral=True)
        return

    nation = bot.nations[uid]
    target = bot.nations[target_uid]

    if nation["resources"] < amount:
        await interaction.response.send_message(f"❌ Not enough resources", ephemeral=True)
        return

    nation["resources"] -= amount
    target["resources"] += amount

    log_text = f"💸 {nation['name']} sent {amount:,} resources to {target['name']}"
    append_history(uid, log_text)
    append_history(target_uid, log_text, major=True)
    bot.save_data()

    await interaction.response.send_message(f"✅ Sent {amount:,} resources to **{target['name']}**")


# ---------------- UTILITY ----------------
@bot.tree.command(name="list_units", description="View all unit types")
async def list_units(interaction: Interaction):
    embed = discord.Embed(title="🪖 Military Units", color=discord.Color.green())

    for unit_name, stats in UNIT_TYPES.items():
        locked = ""
        if unit_name == "Nuclear Missile":
            locked = "\n🔒 Requires: Nuclear Program tech"

        embed.add_field(
            name=unit_name,
            value=f"💰 Cost: {stats['cost']}\n⚔️ Power: {stats['power']}\n🛡️ Upkeep: {stats['upkeep']}\n🪖 Manpower: {stats['manpower']}{locked}",
            inline=True
        )

    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="leaderboard", description="View nation rankings")
@app_commands.describe(category="What to rank by")
async def leaderboard(interaction: Interaction, category: str = "power"):
    if not bot.nations:
        await interaction.response.send_message("📊 No nations yet", ephemeral=True)
        return

    category_map = {
        "power": ("military_power", "⚔️ Military Power"),
        "population": ("population", "👥 Population"),
        "resources": ("resources", "💰 Resources"),
        "territory": ("territory", "🗺️ Territory"),
    }

    if category not in category_map:
        category = "power"

    sort_key, title = category_map[category]

    ranked = sorted(
        bot.nations.items(),
        key=lambda x: x[1].get(sort_key, 0),
        reverse=True
    )[:10]

    embed = discord.Embed(title=f"🏆 Leaderboard - {title}", color=discord.Color.gold())

    for idx, (uid, nation) in enumerate(ranked, 1):
        try:
            user = await bot.fetch_user(int(uid))
            value = int(nation.get(sort_key, 0))
            embed.add_field(
                name=f"{idx}. {nation['name']}",
                value=f"Leader: {user.display_name}\n{title}: {value:,}",
                inline=False
            )
        except:
            pass

    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="history", description="View your nation's history")
@has_nation()
async def history(interaction: Interaction):
    uid = str(interaction.user.id)
    nation = bot.nations[uid]

    hist = nation.get("history", [])
    if not hist:
        await interaction.response.send_message("📜 No history yet", ephemeral=True)
        return

    recent = hist[-15:]
    embed = discord.Embed(
        title=f"📜 History of {nation['name']}",
        description="\n".join(recent),
        color=discord.Color.gold()
    )
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="compare", description="Compare your nation with another")
@app_commands.describe(target_user="Nation to compare with")
@has_nation()
async def compare(interaction: Interaction, target_user: discord.User):
    uid = str(interaction.user.id)
    target_uid = str(target_user.id)

    if target_uid not in bot.nations:
        await interaction.response.send_message("❌ Target doesn't have a nation", ephemeral=True)
        return

    nation1 = bot.nations[uid]
    nation2 = bot.nations[target_uid]

    embed = discord.Embed(title=f"⚖️ {nation1['name']} vs {nation2['name']}", color=discord.Color.blue())

    stats = [
        ("⚔️ Military Power", "military_power"),
        ("👥 Population", "population"),
        ("💰 Resources", "resources"),
        ("🗺️ Territory", "territory"),
    ]

    for label, key in stats:
        v1 = int(nation1.get(key, 0))
        v2 = int(nation2.get(key, 0))
        embed.add_field(name=label, value=f"{v1:,} vs {v2:,}", inline=True)

    await interaction.response.send_message(embed=embed)


# ---------------- AUTOCOMPLETE ----------------
@train_units.autocomplete('unit_type')
@disband_units.autocomplete('unit_type')
async def unit_autocomplete(interaction: Interaction, current: str):
    return [
        app_commands.Choice(name=unit, value=unit)
        for unit in UNIT_TYPES.keys()
        if current.lower() in unit.lower()
    ][:25]


@research.autocomplete('tech_name')
async def tech_autocomplete(interaction: Interaction, current: str):
    return [
        app_commands.Choice(name=tech, value=tech)
        for tech in TECHNOLOGIES.keys()
        if current.lower() in tech.lower()
    ][:25]


@construct_building.autocomplete('building_type')
async def building_autocomplete(interaction: Interaction, current: str):
    return [
        app_commands.Choice(name=building, value=building)
        for building in BUILDINGS.keys()
        if current.lower() in building.lower()
    ][:25]


@join_alliance.autocomplete('alliance_name')
async def alliance_autocomplete(interaction: Interaction, current: str):
    return [
        app_commands.Choice(name=alliance, value=alliance)
        for alliance in bot.alliances.keys()
        if current.lower() in alliance.lower()
    ][:25]


@leaderboard.autocomplete('category')
async def leaderboard_autocomplete(interaction: Interaction, current: str):
    categories = ["power", "population", "resources", "territory"]
    return [
        app_commands.Choice(name=cat.title(), value=cat)
        for cat in categories
        if current.lower() in cat.lower()
    ]


# ADD THIS TO THE END OF YOUR MAIN bot.py FILE
if __name__ == "__main__":
    if not TOKEN:
        print("ERROR: DISCORD_TOKEN not found!")
        exit(1)
    bot.run(TOKEN)