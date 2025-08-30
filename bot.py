import discord
from discord.ext import commands
import json
import aiohttp
import asyncio
from flask import Flask, jsonify
from dotenv import load_dotenv
import os
import threading

# --- CONFIG BOT ---
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")  # Charge le token depuis Railway ou .env local

if not TOKEN:
    raise ValueError("❌ Aucun token Discord trouvé ! Vérifie la variable DISCORD_TOKEN sur Railway.")

bot = commands.Bot(command_prefix="!", intents=intents)
PRIVATE_CHANNEL_ID = 1393953102088114197  # salon commandes
MARKET_CHANNEL_ID = 1393933918364893339   # salon marché noir
bot.market_message = None  # On garde le message pour le mettre à jour

# --- CONFIG API FLASK ---
app = Flask(__name__)
PRODUITS_FILE = "produits.json"

@app.route("/api/produits")
def api_produits():
    try:
        with open(PRODUITS_FILE, "r") as f:
            produits = json.load(f)
    except FileNotFoundError:
        produits = {}
    return jsonify(produits)

# --- Charger les produits depuis l'API web ---
API_URL = os.getenv("API_URL", "http://127.0.0.1:5000/api/produits")

async def charger_produits():
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(API_URL) as response:
                if response.status == 200:
                    produits = await response.json()
                    print("✅ Produits chargés depuis l'API")
                    return produits
                else:
                    print(f"❌ Erreur API: {response.status}")
                    return {}
    except Exception as e:
        print(f"❌ Erreur connexion API: {e}")
        return {}

# --- Créer l'embed du marché noir ---
def creer_embed(produits):
    embed = discord.Embed(
        title="💀 𝗗𝗔𝗥𝗞 𝗠𝗔𝗥𝗞𝗘𝗧 💀",
        description=(
            "Bienvenue dans l'ombre...\n"
            "**Sélectionne tes marchandises et passe commande discrètement.**\n\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "〄 **Cosa Nostra Approved** 〄"
        ),
        color=discord.Color.dark_red()
    )
    for cat, items in produits.items():
        if not items:
            continue
        liste = "\n".join([f"🔪 **{nom}** 〙 `{prix}k`" for nom, prix in items])
        embed.add_field(name=f"📦 {cat.upper()}", value=liste, inline=False)
    embed.set_footer(text="Tout achat est définitif. Pas de remboursement dans l'ombre.")
    return embed

# --- Actualisation continue ---
async def actualiser_produits():
    await bot.wait_until_ready()
    while not bot.is_closed():
        bot.produits = await charger_produits()
        if bot.market_message:
            embed = creer_embed(bot.produits)
            await bot.market_message.edit(embed=embed, view=AchatView(bot.produits))
        await asyncio.sleep(60)

# --- (tes classes LivraisonView, AchatModal, Selects, etc. restent identiques) ---

# --- Commande admin ---
@bot.command()
@commands.has_permissions(administrator=True)
async def actualiser(ctx):
    bot.produits = await charger_produits()
    if bot.market_message:
        embed = creer_embed(bot.produits)
        await bot.market_message.edit(embed=embed, view=AchatView(bot.produits))
    await ctx.send("✅ Produits actualisés depuis l'API!")

# --- Bot prêt ---
@bot.event
async def on_ready():
    print(f"{bot.user} est prêt ✅")
    bot.produits = await charger_produits()
    bot.loop.create_task(actualiser_produits())

    market_channel = bot.get_channel(MARKET_CHANNEL_ID)
    if market_channel:
        await market_channel.purge(limit=10)
        embed = creer_embed(bot.produits)
        bot.market_message = await market_channel.send(embed=embed, view=AchatView(bot.produits))

# --- Lancer Flask en parallèle ---
def run_flask():
    port = int(os.environ.get("PORT", 5000))  # Railway fournit le port
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

threading.Thread(target=run_flask, daemon=True).start()

# --- Lancer le bot ---
bot.run(TOKEN)
