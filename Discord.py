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

# ---------------- GROUND UNIT DEFINITIONS ----------------
GROUND_UNITS = {
    "Infantry": {"cost": 10, "power": 5, "upkeep": 1, "manpower": 1, "type": "ground"},
    "Light Tank": {"cost": 50, "power": 30, "upkeep": 5, "manpower": 3, "type": "ground"},
    "MBT": {"cost": 120, "power": 80, "upkeep": 12, "manpower": 5, "type": "ground"},
    "Artillery": {"cost": 70, "power": 40, "upkeep": 6, "manpower": 4, "type": "ground"},
    "Elite Forces": {"cost": 500, "power": 300, "upkeep": 40, "manpower": 10, "type": "ground"},
}

# ---------------- NAVAL UNITS ----------------
NAVAL_UNITS = {
    "Patrol Boat": {"cost": 80, "power": 40, "upkeep": 4, "manpower": 5, "type": "naval"},
    "Destroyer": {"cost": 250, "power": 160, "upkeep": 25, "manpower": 12, "type": "naval"},
    "Cruiser": {"cost": 400, "power": 280, "upkeep": 35, "manpower": 20, "type": "naval"},
    "Battleship": {"cost": 800, "power": 600, "upkeep": 70, "manpower": 40, "type": "naval"},
    "Aircraft Carrier": {"cost": 1200, "power": 500, "upkeep": 100, "manpower": 60, "type": "naval"},
    "Submarine": {"cost": 180, "power": 110, "upkeep": 15, "manpower": 8, "type": "naval"},
}

# ---------------- AIR UNITS ----------------
AIR_UNITS = {
    "Fighter": {"cost": 200, "power": 150, "upkeep": 20, "manpower": 2, "type": "air"},
    "Bomber": {"cost": 350, "power": 200, "upkeep": 30, "manpower": 4, "type": "air"},
    "Stealth Bomber": {"cost": 800, "power": 450, "upkeep": 60, "manpower": 6, "type": "air"},
    "Transport Plane": {"cost": 150, "power": 0, "upkeep": 12, "manpower": 3, "type": "air"},
    "Helicopter": {"cost": 150, "power": 90, "upkeep": 12, "manpower": 3, "type": "air"},
}

# Combine all units
ALL_UNITS = {**GROUND_UNITS, **NAVAL_UNITS, **AIR_UNITS}

# Add Nuclear Missile
ALL_UNITS["Nuclear Missile"] = {"cost": 5000, "power": 10000, "upkeep": 200, "manpower": 50, "type": "strategic"}

# ---------------- WORLD MAP ----------------
MAP_WIDTH = 50
MAP_HEIGHT = 30

TERRAIN_OCEAN = "🌊"
TERRAIN_LAND = "🟩"
TERRAIN_MOUNTAIN = "🏔️"
TERRAIN_DESERT = "🏜️"

WORLD_REGIONS = {
    "Northern Highlands": {
        "terrain": "mountain",
        "bonus": "defense",
        "bonus_value": 1.2,
        "description": "+20% defensive power",
        "coordinates": (10, 5),
        "size": 3
    },
    "Eastern Plains": {
        "terrain": "farmland",
        "bonus": "population",
        "bonus_value": 1.5,
        "description": "+50% population growth",
        "coordinates": (35, 10),
        "size": 4
    },
    "Western Industrial Zone": {
        "terrain": "industrial",
        "bonus": "resources",
        "bonus_value": 1.5,
        "description": "+50% resource production",
        "coordinates": (8, 15),
        "size": 3
    },
    "Central Oilfields": {
        "terrain": "desert",
        "bonus": "oil",
        "bonus_value": 100,
        "description": "+100 resources/min",
        "coordinates": (25, 20),
        "size": 2
    },
    "Southern Coastal Bay": {
        "terrain": "coastal",
        "bonus": "naval",
        "bonus_value": 1.3,
        "description": "+30% naval power, can build fleets",
        "coordinates": (20, 25),
        "size": 3
    },
    "Frozen Tundra": {
        "terrain": "mountain",
        "bonus": "defense",
        "bonus_value": 1.4,
        "description": "+40% defense",
        "coordinates": (40, 3),
        "size": 2
    },
    "Tropical Islands": {
        "terrain": "coastal",
        "bonus": "naval_base",
        "bonus_value": 1.5,
        "description": "Strategic naval base",
        "coordinates": (45, 22),
        "size": 1
    },
    "Great Forest": {
        "terrain": "forest",
        "bonus": "guerrilla",
        "bonus_value": 1.3,
        "description": "+30% defense, guerrilla warfare",
        "coordinates": (15, 12),
        "size": 4
    },
    "Silicon Valley": {
        "terrain": "industrial",
        "bonus": "research",
        "bonus_value": 2.0,
        "description": "+100% research points",
        "coordinates": (30, 8),
        "size": 2
    },
    "Trade Hub Port": {
        "terrain": "coastal",
        "bonus": "trade",
        "bonus_value": 1.4,
        "description": "+40% trading efficiency",
        "coordinates": (5, 20),
        "size": 2
    },
}

INFRASTRUCTURE = {
    "Naval Base": {
        "cost": 500,
        "requirement": "coastal_region",
        "effect": "unlock_naval_units",
        "description": "Build and deploy naval units"
    },
    "Airbase": {
        "cost": 400,
        "requirement": "any_region",
        "effect": "unlock_air_units",
        "description": "Build and deploy aircraft"
    },
    "Strategic Missile Silo": {
        "cost": 2000,
        "requirement": "nuclear_program",
        "effect": "nuclear_launch",
        "description": "Launch nuclear strikes"
    },
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
        "description": "+30% spy mission success"
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
        print(f"Bot Online as {self.user}")
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
                print(f"Loaded {len(self.nations)} nations")
            except Exception as e:
                print(f"Failed loading data: {e}")
                self.nations = {}
                self.alliances = {}
        else:
            self.nations = {}
            self.alliances = {}

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
            print(f"Failed saving: {e}")

    def calculate_passive_income(self, nation: dict) -> dict:
        base_resources = 1
        base_manpower = 0.5
        base_research = 0.1
        base_political = 0.05
        base_population = 0.2

        territory_mult = 1 + (nation.get("territory", 1) * 0.1)

        # Territory bonuses
        territory_bonus_resources = 0
        territory_bonus_research = 0
        for region_name in nation.get("territories", []):
            if region_name in WORLD_REGIONS:
                region = WORLD_REGIONS[region_name]
                if region["bonus"] == "resources":
                    territory_bonus_resources += 0.5
                elif region["bonus"] == "research":
                    territory_bonus_research += 0.3
                elif region["bonus"] == "oil":
                    territory_bonus_resources += 1.5

        tech_list = nation.get("technologies", [])
        resource_mult = 1.5 if "Industrial Revolution" in tech_list else 1.0
        pop_mult = 1.5 if "Advanced Farming" in tech_list else 1.0
        manpower_mult = 2.0 if "Mass Conscription" in tech_list else 1.0

        buildings = nation.get("buildings", {})
        building_resources = buildings.get("Factory", 0) * 0.3
        building_manpower = buildings.get("Barracks", 0) * 0.2
        building_research = buildings.get("Research Lab", 0) * 0.08
        building_political = buildings.get("Government Complex", 0) * 0.05
        building_population = buildings.get("Farm", 0) * 0.15

        return {
            "resources": (
                                     base_resources * territory_mult * resource_mult) + building_resources + territory_bonus_resources,
            "manpower": (base_manpower * territory_mult * manpower_mult) + building_manpower,
            "research_points": (base_research * territory_mult) + building_research + territory_bonus_research,
            "political_points": (base_political * territory_mult) + building_political,
            "population": (base_population * territory_mult * pop_mult) + building_population
        }

    @tasks.loop(seconds=1)
    async def real_time_growth_loop(self) -> None:
        for user_id, nation in self.nations.items():
            income = self.calculate_passive_income(nation)

            nation["resources"] = min(nation.get("resources", 0) + income["resources"], 999999)
            nation["manpower"] = min(nation.get("manpower", 0) + income["manpower"], 999999)
            nation["research_points"] = min(nation.get("research_points", 0) + income["research_points"], 99999)
            nation["political_points"] = min(nation.get("political_points", 0) + income["political_points"], 99999)
            nation["population"] = min(nation.get("population", 0) + income["population"], 9999999)

        if not hasattr(self, '_save_counter'):
            self._save_counter = 0
        self._save_counter += 1
        if self._save_counter >= 30:
            self.save_data()
            self._save_counter = 0

    @tasks.loop(minutes=5)
    async def passive_growth_loop(self) -> None:
        log_channel = self.get_channel(LOG_CHANNEL_ID)
        for user_id, nation in self.nations.items():
            total_upkeep = sum(
                ALL_UNITS.get(unit, {}).get("upkeep", 0) * qty
                for unit, qty in nation.get("units", {}).items()
            )

            if "Advanced Logistics" in nation.get("technologies", []):
                total_upkeep = int(total_upkeep * 0.8)

            if total_upkeep > 0:
                if nation["resources"] >= total_upkeep:
                    nation["resources"] -= total_upkeep
                else:
                    shortfall = total_upkeep - nation["resources"]
                    nation["resources"] = 0
                    fraction_unpaid = shortfall / total_upkeep
                    for unit_name in list(nation.get("units", {}).keys()):
                        qty = nation["units"][unit_name]
                        to_remove = max(1, int(qty * fraction_unpaid * 0.5))
                        if to_remove > 0:
                            nation["units"][unit_name] = max(0, qty - to_remove)
                            if unit_name in ALL_UNITS:
                                nation["military_power"] = max(0, nation["military_power"] - ALL_UNITS[unit_name][
                                    "power"] * to_remove)
        self.save_data()

    @tasks.loop(minutes=10)
    async def random_events_loop(self) -> None:
        log_channel = self.get_channel(LOG_CHANNEL_ID)
        for user_id, nation in self.nations.items():
            for event in RANDOM_EVENTS:
                if random.random() < event["chance"]:
                    effect = event["effect"]
                    value = event["value"]
                    if effect in nation:
                        nation[effect] = max(0, nation[effect] + value)
                        symbol = "🎉" if value > 0 else "⚠️"
                        message = f"{symbol} **{nation['name']}** - **{event['name']}**!"
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
            await interaction.response.send_message("❌ No nation. Use `/create_nation`", ephemeral=True)
            return False
        return True

    return app_commands.check(predicate)


def append_history(user_id: str, text: str, major: bool = False) -> None:
    bot.nations[user_id]["history"].append(text)
    if major:
        log_channel = bot.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            try:
                bot.loop.create_task(log_channel.send(text))
            except:
                pass


def calculate_military_by_type(nation: dict) -> dict:
    ground, naval, air = 0, 0, 0
    for unit_name, qty in nation.get("units", {}).items():
        if unit_name in ALL_UNITS:
            unit = ALL_UNITS[unit_name]
            power = unit["power"] * qty
            utype = unit.get("type", "ground")
            if utype == "naval":
                naval += power
            elif utype == "air":
                air += power
            else:
                ground += power
    return {"ground": ground, "naval": naval, "air": air, "total": ground + naval + air}


def generate_world_map():
    map_grid = [[TERRAIN_OCEAN for _ in range(MAP_WIDTH)] for _ in range(MAP_HEIGHT)]

    # Continents
    for y in range(3, 12):
        for x in range(5, 20):
            if random.random() > 0.15:
                map_grid[y][x] = TERRAIN_LAND
    for y in range(2, 14):
        for x in range(30, 48):
            if random.random() > 0.15:
                map_grid[y][x] = TERRAIN_LAND
    for y in range(15, 28):
        for x in range(3, 18):
            if random.random() > 0.15:
                map_grid[y][x] = TERRAIN_LAND
    for y in range(18, 28):
        for x in range(35, 48):
            if random.random() > 0.15:
                map_grid[y][x] = TERRAIN_LAND

    # Mountains
    for mx, my in [(10, 5), (40, 3)]:
        for dy in range(-1, 2):
            for dx in range(-2, 3):
                ny, nx = my + dy, mx + dx
                if 0 <= ny < MAP_HEIGHT and 0 <= nx < MAP_WIDTH and map_grid[ny][nx] == TERRAIN_LAND:
                    map_grid[ny][nx] = TERRAIN_MOUNTAIN

    # Deserts
    for dx, dy in [(25, 20)]:
        for dy_off in range(-1, 2):
            for dx_off in range(-1, 2):
                ny, nx = dy + dy_off, dx + dx_off
                if 0 <= ny < MAP_HEIGHT and 0 <= nx < MAP_WIDTH and map_grid[ny][nx] == TERRAIN_LAND:
                    map_grid[ny][nx] = TERRAIN_DESERT

    return map_grid


def render_map_with_nations(map_grid, nations_data):
    nation_symbols = "🔴🔵🟢🟡🟣🟠🟤⚫⚪"
    nation_to_symbol = {}
    idx = 0
    for uid, nation in nations_data.items():
        if nation.get("territories"):
            nation_to_symbol[uid] = nation_symbols[idx % len(nation_symbols)]
            idx += 1

    display_map = [row[:] for row in map_grid]
    for uid, nation in nations_data.items():
        if uid in nation_to_symbol:
            symbol = nation_to_symbol[uid]
            for region_name in nation.get("territories", []):
                if region_name in WORLD_REGIONS:
                    region = WORLD_REGIONS[region_name]
                    x, y = region["coordinates"]
                    size = region["size"]
                    for dy in range(-size, size + 1):
                        for dx in range(-size, size + 1):
                            ny, nx = y + dy, x + dx
                            if 0 <= ny < MAP_HEIGHT and 0 <= nx < MAP_WIDTH and display_map[ny][nx] != TERRAIN_OCEAN:
                                display_map[ny][nx] = symbol

    map_str = "```\n" + "═" * (MAP_WIDTH + 2) + "\n"
    for row in display_map:
        map_str += "║" + "".join(row) + "║\n"
    map_str += "═" * (MAP_WIDTH + 2) + "\n```"
    return map_str, nation_to_symbol


# PASTE THIS AFTER THE HELPERS IN YOUR MAIN FILE

# ---------------- NATION MANAGEMENT ----------------
@bot.tree.command(name="create_nation", description="Create your nation")
@app_commands.describe(nation_name="Name for your nation")
async def create_nation(interaction: Interaction, nation_name: str):
    uid = str(interaction.user.id)
    if uid in bot.nations:
        await interaction.response.send_message("❌ Already have a nation", ephemeral=True)
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
        "territories": [],
        "infrastructure": {},
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
    await interaction.response.send_message(embed=embed)

    log_ch = bot.get_channel(LOG_CHANNEL_ID)
    if log_ch:
        try:
            await log_ch.send(f"🗺️ New nation: **{nation_name}**")
        except:
            pass


@bot.tree.command(name="nation_status", description="View your nation")
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
    embed.add_field(name="⚔️ Military", value=f"{nation['military_power']:,}", inline=True)
    embed.add_field(name="🗺️ Territories", value=f"{len(nation.get('territories', []))}", inline=True)

    await interaction.response.send_message(embed=embed)


# ---------------- GROUND MILITARY ----------------
@bot.tree.command(name="train_units", description="Train ground units")
@app_commands.describe(unit_type="Type of unit", quantity="Number to train")
@has_nation()
async def train_units(interaction: Interaction, unit_type: str, quantity: int):
    uid = str(interaction.user.id)
    nation = bot.nations[uid]

    if unit_type not in GROUND_UNITS:
        await interaction.response.send_message("❌ Invalid unit. Use `/list_units`", ephemeral=True)
        return

    unit_info = GROUND_UNITS[unit_type]
    total_cost = unit_info["cost"] * quantity
    total_manpower = unit_info["manpower"] * quantity

    if nation["resources"] < total_cost or nation["manpower"] < total_manpower:
        await interaction.response.send_message("❌ Not enough resources/manpower", ephemeral=True)
        return

    nation["resources"] -= total_cost
    nation["manpower"] -= total_manpower
    nation["units"][unit_type] = nation["units"].get(unit_type, 0) + quantity

    power_gain = unit_info["power"] * quantity
    if "Military Tactics" in nation.get("technologies", []):
        power_gain = int(power_gain * 1.2)
    nation["military_power"] += power_gain

    append_history(uid, f"⚔️ Trained {quantity}x {unit_type}")
    bot.save_data()

    await interaction.response.send_message(f"✅ Trained {quantity}x **{unit_type}**! (+{power_gain:,} power)")


@bot.tree.command(name="list_units", description="View all ground units")
async def list_units(interaction: Interaction):
    embed = discord.Embed(title="🪖 Ground Units", color=discord.Color.green())
    for unit_name, stats in GROUND_UNITS.items():
        embed.add_field(
            name=unit_name,
            value=f"💰 {stats['cost']} | ⚔️ {stats['power']} | 🛡️ {stats['upkeep']}/tick",
            inline=True
        )
    await interaction.response.send_message(embed=embed)


# ---------------- NAVAL MILITARY ----------------
@bot.tree.command(name="train_naval_units", description="Train naval units (requires Naval Base)")
@app_commands.describe(unit_type="Naval unit", quantity="Number", region="Region with naval base")
@has_nation()
async def train_naval_units(interaction: Interaction, unit_type: str, quantity: int, region: str):
    uid = str(interaction.user.id)
    nation = bot.nations[uid]

    if unit_type not in NAVAL_UNITS:
        await interaction.response.send_message("❌ Invalid naval unit", ephemeral=True)
        return

    if region not in nation.get("infrastructure", {}) or "Naval Base" not in nation["infrastructure"][region]:
        await interaction.response.send_message(f"❌ No Naval Base in {region}", ephemeral=True)
        return

    unit_info = NAVAL_UNITS[unit_type]
    total_cost = unit_info["cost"] * quantity
    total_manpower = unit_info["manpower"] * quantity

    if nation["resources"] < total_cost or nation["manpower"] < total_manpower:
        await interaction.response.send_message("❌ Not enough resources/manpower", ephemeral=True)
        return

    nation["resources"] -= total_cost
    nation["manpower"] -= total_manpower
    nation["units"][unit_type] = nation["units"].get(unit_type, 0) + quantity
    nation["military_power"] += unit_info["power"] * quantity

    append_history(uid, f"🚢 Deployed {quantity}x {unit_type}")
    bot.save_data()

    await interaction.response.send_message(f"✅ Deployed {quantity}x **{unit_type}**!")


@bot.tree.command(name="list_naval_units", description="View naval units")
async def list_naval_units(interaction: Interaction):
    embed = discord.Embed(title="🚢 Naval Units", color=discord.Color.blue())
    for unit_name, stats in NAVAL_UNITS.items():
        embed.add_field(name=unit_name, value=f"💰 {stats['cost']} | ⚓ {stats['power']}", inline=True)
    await interaction.response.send_message(embed=embed)


# ---------------- AIR MILITARY ----------------
@bot.tree.command(name="train_air_units", description="Train aircraft (requires Airbase)")
@app_commands.describe(unit_type="Aircraft type", quantity="Number", region="Region with airbase")
@has_nation()
async def train_air_units(interaction: Interaction, unit_type: str, quantity: int, region: str):
    uid = str(interaction.user.id)
    nation = bot.nations[uid]

    if unit_type not in AIR_UNITS:
        await interaction.response.send_message("❌ Invalid air unit", ephemeral=True)
        return

    if region not in nation.get("infrastructure", {}) or "Airbase" not in nation["infrastructure"][region]:
        await interaction.response.send_message(f"❌ No Airbase in {region}", ephemeral=True)
        return

    unit_info = AIR_UNITS[unit_type]
    total_cost = unit_info["cost"] * quantity
    total_manpower = unit_info["manpower"] * quantity

    if nation["resources"] < total_cost or nation["manpower"] < total_manpower:
        await interaction.response.send_message("❌ Not enough resources/manpower", ephemeral=True)
        return

    nation["resources"] -= total_cost
    nation["manpower"] -= total_manpower
    nation["units"][unit_type] = nation["units"].get(unit_type, 0) + quantity
    nation["military_power"] += unit_info["power"] * quantity

    append_history(uid, f"✈️ Deployed {quantity}x {unit_type}")
    bot.save_data()

    await interaction.response.send_message(f"✅ Deployed {quantity}x **{unit_type}**!")


@bot.tree.command(name="list_air_units", description="View aircraft")
async def list_air_units(interaction: Interaction):
    embed = discord.Embed(title="✈️ Air Units", color=discord.Color.blue())
    for unit_name, stats in AIR_UNITS.items():
        embed.add_field(name=unit_name, value=f"💰 {stats['cost']} | ✈️ {stats['power']}", inline=True)
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="military_overview", description="View your military by domain")
@has_nation()
async def military_overview(interaction: Interaction):
    uid = str(interaction.user.id)
    nation = bot.nations[uid]
    forces = calculate_military_by_type(nation)

    embed = discord.Embed(title=f"🎖️ {nation['name']} Military", color=discord.Color.blue())
    embed.add_field(name="🪖 Ground", value=f"{forces['ground']:,}", inline=True)
    embed.add_field(name="🚢 Naval", value=f"{forces['naval']:,}", inline=True)
    embed.add_field(name="✈️ Air", value=f"{forces['air']:,}", inline=True)
    embed.add_field(name="⚔️ Total", value=f"{forces['total']:,}", inline=False)

    await interaction.response.send_message(embed=embed)


# ---------------- WORLD MAP ----------------
@bot.tree.command(name="view_map", description="View the world map")
async def view_map(interaction: Interaction):
    await interaction.response.defer()

    world_map = generate_world_map()
    map_display, nation_symbols = render_map_with_nations(world_map, bot.nations)

    embed = discord.Embed(title="🌍 World Map", color=discord.Color.blue())
    embed.description = map_display

    legend = "**Legend:**\n"
    legend += f"{TERRAIN_OCEAN} Ocean | {TERRAIN_LAND} Land | {TERRAIN_MOUNTAIN} Mountain | {TERRAIN_DESERT} Desert\n\n"
    if nation_symbols:
        legend += "**Nations:**\n"
        for uid, symbol in list(nation_symbols.items())[:10]:
            legend += f"{symbol} {bot.nations[uid]['name']}\n"

    embed.add_field(name="Legend", value=legend, inline=False)
    await interaction.followup.send(embed=embed)


@bot.tree.command(name="list_regions", description="View all regions")
async def list_regions(interaction: Interaction):
    embed = discord.Embed(title="🗺️ World Regions", color=discord.Color.green())

    for region_name, region_data in list(WORLD_REGIONS.items())[:10]:
        owner = "Unclaimed"
        for uid, nation in bot.nations.items():
            if region_name in nation.get("territories", []):
                owner = nation["name"]
                break

        embed.add_field(
            name=region_name,
            value=f"**{owner}**\n{region_data['description']}",
            inline=False
        )

    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="invade_region", description="Capture a region")
@app_commands.describe(region_name="Region to invade")
@has_nation()
async def invade_region(interaction: Interaction, region_name: str):
    uid = str(interaction.user.id)
    nation = bot.nations[uid]

    if region_name not in WORLD_REGIONS:
        await interaction.response.send_message("❌ Invalid region", ephemeral=True)
        return

    if nation["military_power"] < 100:
        await interaction.response.send_message("❌ Need 100+ military power", ephemeral=True)
        return

    current_owner = None
    for owner_uid, owner_nation in bot.nations.items():
        if region_name in owner_nation.get("territories", []):
            current_owner = owner_uid
            break

    if current_owner is None:
        cost = 500
        if nation["resources"] < cost:
            await interaction.response.send_message(f"❌ Need {cost} resources", ephemeral=True)
            return

        nation["resources"] -= cost
        if "territories" not in nation:
            nation["territories"] = []
        nation["territories"].append(region_name)

        append_history(uid, f"🗺️ Claimed {region_name}!", major=True)
        bot.save_data()

        await interaction.response.send_message(f"✅ Claimed **{region_name}**!")
        return

    if current_owner == uid:
        await interaction.response.send_message("❌ Already own this", ephemeral=True)
        return

    defender = bot.nations[current_owner]
    region_data = WORLD_REGIONS[region_name]

    att_power = nation["military_power"]
    def_power = int(defender["military_power"] * region_data.get("bonus_value", 1.0))

    total = att_power + def_power
    attacker_wins = random.random() < (att_power / total if total > 0 else 0.5)

    if attacker_wins:
        defender["territories"].remove(region_name)
        nation["territories"].append(region_name)

        att_losses = int(att_power * 0.15)
        def_losses = int(def_power * 0.30)
        nation["military_power"] = max(0, nation["military_power"] - att_losses)
        defender["military_power"] = max(0, defender["military_power"] - def_losses)

        append_history(uid, f"⚔️ Conquered {region_name}!", major=True)
        append_history(current_owner, f"💔 Lost {region_name}", major=True)

        await interaction.response.send_message(f"🎖️ **VICTORY!** Conquered **{region_name}**!")
    else:
        att_losses = int(att_power * 0.35)
        def_losses = int(def_power * 0.15)
        nation["military_power"] = max(0, nation["military_power"] - att_losses)
        defender["military_power"] = max(0, defender["military_power"] - def_losses)

        append_history(uid, f"💔 Failed to take {region_name}", major=True)

        await interaction.response.send_message(f"💔 **DEFEAT!** Failed to capture {region_name}")

    bot.save_data()


@bot.tree.command(name="my_territories", description="View your territories")
@has_nation()
async def my_territories(interaction: Interaction):
    uid = str(interaction.user.id)
    nation = bot.nations[uid]
    territories = nation.get("territories", [])

    if not territories:
        await interaction.response.send_message("📍 No territories yet", ephemeral=True)
        return

    embed = discord.Embed(title=f"🗺️ {nation['name']}'s Territories", color=discord.Color.gold())
    for territory in territories[:15]:
        region_data = WORLD_REGIONS[territory]
        embed.add_field(name=territory, value=region_data['description'], inline=False)

    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="build_infrastructure", description="Build naval bases or airbases")
@app_commands.describe(infra_type="Infrastructure type", region_name="Region to build in")
@has_nation()
async def build_infrastructure(interaction: Interaction, infra_type: str, region_name: str):
    uid = str(interaction.user.id)
    nation = bot.nations[uid]

    if infra_type not in INFRASTRUCTURE:
        await interaction.response.send_message("❌ Invalid type", ephemeral=True)
        return

    if region_name not in nation.get("territories", []):
        await interaction.response.send_message("❌ Don't control this region", ephemeral=True)
        return

    infra = INFRASTRUCTURE[infra_type]

    if infra["requirement"] == "coastal_region":
        region_data = WORLD_REGIONS[region_name]
        if region_data["terrain"] != "coastal":
            await interaction.response.send_message("❌ Must be coastal region", ephemeral=True)
            return

    if nation["resources"] < infra["cost"]:
        await interaction.response.send_message(f"❌ Need {infra['cost']:,} resources", ephemeral=True)
        return

    nation["resources"] -= infra["cost"]
    if "infrastructure" not in nation:
        nation["infrastructure"] = {}
    if region_name not in nation["infrastructure"]:
        nation["infrastructure"][region_name] = []
    nation["infrastructure"][region_name].append(infra_type)

    append_history(uid, f"🏗️ Built {infra_type} in {region_name}!", major=True)
    bot.save_data()

    await interaction.response.send_message(f"✅ Built **{infra_type}** in **{region_name}**!")


# PASTE THIS AFTER PART 2 IN YOUR MAIN FILE

# ---------------- FULL-SCALE WARFARE ----------------
@bot.tree.command(name="full_scale_war", description="Launch combined arms assault")
@app_commands.describe(target_user="Nation to attack")
@has_nation()
async def full_scale_war(interaction: Interaction, target_user: discord.User):
    uid = str(interaction.user.id)
    target_uid = str(target_user.id)

    if uid == target_uid or target_uid not in bot.nations:
        await interaction.response.send_message("❌ Invalid target", ephemeral=True)
        return

    attacker = bot.nations[uid]
    defender = bot.nations[target_uid]

    att_forces = calculate_military_by_type(attacker)
    def_forces = calculate_military_by_type(defender)

    if att_forces["total"] <= 0:
        await interaction.response.send_message("❌ No military!", ephemeral=True)
        return

    await interaction.response.defer()

    embed = discord.Embed(title="⚔️ FULL-SCALE WAR!", color=discord.Color.red())
    embed.description = f"**{attacker['name']}** vs **{defender['name']}**"

    battle_log = []
    total_att_losses = 0
    total_def_losses = 0

    # PHASE 1: AIR BATTLE
    air_winner = None
    if att_forces["air"] > 0 or def_forces["air"] > 0:
        air_total = att_forces["air"] + def_forces["air"]
        if air_total > 0:
            att_air_chance = att_forces["air"] / air_total
            if random.random() < att_air_chance:
                air_winner = "attacker"
                att_losses = int(att_forces["air"] * 0.10)
                def_losses = int(def_forces["air"] * 0.40)
                battle_log.append(f"✈️ **AIR SUPERIORITY**: {attacker['name']}!")
            else:
                air_winner = "defender"
                att_losses = int(att_forces["air"] * 0.40)
                def_losses = int(def_forces["air"] * 0.10)
                battle_log.append(f"✈️ **AIR SUPERIORITY**: {defender['name']}!")

            total_att_losses += att_losses
            total_def_losses += def_losses
            battle_log.append(f"   Losses: {att_losses:,} vs {def_losses:,}")

    # PHASE 2: NAVAL BATTLE
    naval_winner = None
    if att_forces["naval"] > 0 or def_forces["naval"] > 0:
        naval_total = att_forces["naval"] + def_forces["naval"]
        if naval_total > 0:
            att_naval_chance = att_forces["naval"] / naval_total
            if random.random() < att_naval_chance:
                naval_winner = "attacker"
                att_losses = int(att_forces["naval"] * 0.15)
                def_losses = int(def_forces["naval"] * 0.35)
                battle_log.append(f"\n🚢 **NAVAL DOMINANCE**: {attacker['name']}!")
            else:
                naval_winner = "defender"
                att_losses = int(att_forces["naval"] * 0.35)
                def_losses = int(def_forces["naval"] * 0.15)
                battle_log.append(f"\n🚢 **NAVAL DOMINANCE**: {defender['name']}!")

            total_att_losses += att_losses
            total_def_losses += def_losses
            battle_log.append(f"   Losses: {att_losses:,} vs {def_losses:,}")

    # PHASE 3: GROUND BATTLE
    ground_att = att_forces["ground"]
    ground_def = def_forces["ground"]

    if air_winner == "attacker":
        ground_att = int(ground_att * 1.25)
        battle_log.append(f"\n🎯 Air superiority: +25% attacker power!")
    elif air_winner == "defender":
        ground_def = int(ground_def * 1.25)
        battle_log.append(f"\n🎯 Air superiority: +25% defender power!")

    if naval_winner == "attacker":
        ground_att = int(ground_att * 1.15)
        battle_log.append(f"🌊 Naval support: +15% attacker power!")
    elif naval_winner == "defender":
        ground_def = int(ground_def * 1.15)
        battle_log.append(f"🌊 Coastal defense: +15% defender power!")

    ground_total = ground_att + ground_def
    ground_winner = None

    if ground_total > 0:
        if random.random() < (ground_att / ground_total):
            ground_winner = "attacker"
            att_losses = int(att_forces["ground"] * 0.20)
            def_losses = int(def_forces["ground"] * 0.45)
            battle_log.append(f"\n🪖 **GROUND VICTORY**: {attacker['name']}!")
        else:
            ground_winner = "defender"
            att_losses = int(att_forces["ground"] * 0.45)
            def_losses = int(def_forces["ground"] * 0.20)
            battle_log.append(f"\n🪖 **GROUND DEFENSE**: {defender['name']} holds!")

        total_att_losses += att_losses
        total_def_losses += def_losses
        battle_log.append(f"   Losses: {att_losses:,} vs {def_losses:,}")

    attacker["military_power"] = max(0, attacker["military_power"] - total_att_losses)
    defender["military_power"] = max(0, defender["military_power"] - total_def_losses)

    phases_won = sum([
        1 if air_winner == "attacker" else 0,
        1 if naval_winner == "attacker" else 0,
        1 if ground_winner == "attacker" else 0
    ])

    if phases_won >= 2:
        resources_plunder = min(int(defender["resources"]), int(defender["resources"] * 0.30) + 200)
        pop_captured = min(int(defender["population"]), int(defender["population"] * 0.10))

        attacker["resources"] += resources_plunder
        attacker["population"] += pop_captured
        defender["resources"] = max(0, defender["resources"] - resources_plunder)
        defender["population"] = max(100, defender["population"] - pop_captured)

        embed.color = discord.Color.green()
        embed.title = "🎖️ DECISIVE VICTORY!"
        embed.add_field(name="Plunder", value=f"💰 {resources_plunder:,}\n👥 {pop_captured:,}", inline=False)
    else:
        embed.color = discord.Color.red()
        embed.title = "💔 DEFEAT!"

    embed.add_field(name="Battle Report", value="\n".join(battle_log), inline=False)
    embed.add_field(name="Total Casualties", value=f"Attacker: {total_att_losses:,}\nDefender: {total_def_losses:,}",
                    inline=False)

    bot.save_data()
    await interaction.followup.send(embed=embed)


# ---------------- TECHNOLOGY ----------------
@bot.tree.command(name="research", description="Research technology")
@app_commands.describe(tech_name="Technology to research")
@has_nation()
async def research(interaction: Interaction, tech_name: str):
    uid = str(interaction.user.id)
    nation = bot.nations[uid]

    if tech_name not in TECHNOLOGIES:
        await interaction.response.send_message("❌ Invalid tech", ephemeral=True)
        return

    if tech_name in nation.get("technologies", []):
        await interaction.response.send_message("❌ Already researched", ephemeral=True)
        return

    tech = TECHNOLOGIES[tech_name]

    if "requires" in tech:
        missing = [req for req in tech["requires"] if req not in nation.get("technologies", [])]
        if missing:
            await interaction.response.send_message(f"❌ Requires: {', '.join(missing)}", ephemeral=True)
            return

    if nation["research_points"] < tech["cost_research"]:
        await interaction.response.send_message(f"❌ Need {tech['cost_research']} research", ephemeral=True)
        return

    if nation["political_points"] < tech["cost_political"]:
        await interaction.response.send_message(f"❌ Need {tech['cost_political']} political", ephemeral=True)
        return

    nation["research_points"] -= tech["cost_research"]
    nation["political_points"] -= tech["cost_political"]
    nation["technologies"].append(tech_name)

    append_history(uid, f"🔬 Researched {tech_name}!", major=True)
    bot.save_data()

    embed = discord.Embed(title="🔬 Research Complete!", color=discord.Color.gold())
    embed.add_field(name="Technology", value=tech_name, inline=False)
    embed.add_field(name="Effect", value=tech["description"], inline=False)
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="view_tech", description="View technology tree")
@has_nation()
async def view_tech(interaction: Interaction):
    uid = str(interaction.user.id)
    nation = bot.nations[uid]

    embed = discord.Embed(title="🔬 Technology Tree", color=discord.Color.purple())

    for tech_name, tech in list(TECHNOLOGIES.items())[:7]:
        status = "✅" if tech_name in nation.get("technologies", []) else "🔒"
        requirements = ""
        if "requires" in tech:
            requirements = f"\nRequires: {', '.join(tech['requires'])}"

        embed.add_field(
            name=f"{status} {tech_name}",
            value=f"{tech['description']}\n🔬 {tech['cost_research']} | 🏛️ {tech['cost_political']}{requirements}",
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
        await interaction.response.send_message("❌ Invalid building", ephemeral=True)
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

    await interaction.response.send_message(f"✅ Built {quantity}x **{building_type}**!\n📈 {building['description']}")


@bot.tree.command(name="list_buildings", description="View all buildings")
async def list_buildings(interaction: Interaction):
    embed = discord.Embed(title="🏗️ Buildings", color=discord.Color.green())
    for building_name, building in BUILDINGS.items():
        embed.add_field(
            name=building_name,
            value=f"💰 {building['cost']}\n{building['description']}",
            inline=True
        )
    await interaction.response.send_message(embed=embed)


# ---------------- UTILITY ----------------
@bot.tree.command(name="leaderboard", description="View rankings")
@app_commands.describe(category="What to rank by")
async def leaderboard(interaction: Interaction, category: str = "power"):
    if not bot.nations:
        await interaction.response.send_message("📊 No nations yet", ephemeral=True)
        return

    category_map = {
        "power": ("military_power", "⚔️ Military Power"),
        "population": ("population", "👥 Population"),
        "resources": ("resources", "💰 Resources"),
        "territories": ("territories", "🗺️ Territories"),
    }

    if category not in category_map:
        category = "power"

    sort_key, title = category_map[category]

    if sort_key == "territories":
        ranked = sorted(bot.nations.items(), key=lambda x: len(x[1].get("territories", [])), reverse=True)[:10]
    else:
        ranked = sorted(bot.nations.items(), key=lambda x: x[1].get(sort_key, 0), reverse=True)[:10]

    embed = discord.Embed(title=f"🏆 Leaderboard - {title}", color=discord.Color.gold())

    for idx, (uid, nation) in enumerate(ranked, 1):
        try:
            if sort_key == "territories":
                value = len(nation.get("territories", []))
            else:
                value = int(nation.get(sort_key, 0))
            embed.add_field(
                name=f"{idx}. {nation['name']}",
                value=f"{title}: {value:,}",
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


# ---------------- AUTOCOMPLETE ----------------
@train_units.autocomplete('unit_type')
async def ground_unit_autocomplete(interaction: Interaction, current: str):
    return [
        app_commands.Choice(name=unit, value=unit)
        for unit in GROUND_UNITS.keys()
        if current.lower() in unit.lower()
    ][:25]


@train_naval_units.autocomplete('unit_type')
async def naval_unit_autocomplete(interaction: Interaction, current: str):
    return [
        app_commands.Choice(name=unit, value=unit)
        for unit in NAVAL_UNITS.keys()
        if current.lower() in unit.lower()
    ][:25]


@train_air_units.autocomplete('unit_type')
async def air_unit_autocomplete(interaction: Interaction, current: str):
    return [
        app_commands.Choice(name=unit, value=unit)
        for unit in AIR_UNITS.keys()
        if current.lower() in unit.lower()
    ][:25]


@invade_region.autocomplete('region_name')
async def region_autocomplete(interaction: Interaction, current: str):
    return [
        app_commands.Choice(name=region, value=region)
        for region in WORLD_REGIONS.keys()
        if current.lower() in region.lower()
    ][:25]


@train_naval_units.autocomplete('region')
@train_air_units.autocomplete('region')
@build_infrastructure.autocomplete('region_name')
async def owned_region_autocomplete(interaction: Interaction, current: str):
    uid = str(interaction.user.id)
    if uid not in bot.nations:
        return []
    territories = bot.nations[uid].get("territories", [])
    return [
        app_commands.Choice(name=region, value=region)
        for region in territories
        if current.lower() in region.lower()
    ][:25]


@build_infrastructure.autocomplete('infra_type')
async def infrastructure_autocomplete(interaction: Interaction, current: str):
    return [
        app_commands.Choice(name=infra, value=infra)
        for infra in INFRASTRUCTURE.keys()
        if current.lower() in infra.lower()
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


@leaderboard.autocomplete('category')
async def leaderboard_autocomplete(interaction: Interaction, current: str):
    categories = ["power", "population", "resources", "territories"]
    return [
        app_commands.Choice(name=cat.title(), value=cat)
        for cat in categories
        if current.lower() in cat.lower()
    ]


# ---------------- RUN BOT ----------------
if __name__ == "__main__":
    if not TOKEN:
        print("ERROR: DISCORD_TOKEN not found!")
        exit(1)
    bot.run(TOKEN)