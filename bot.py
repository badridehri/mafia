import discord
from discord.ext import commands
import json
import aiohttp
import asyncio
from flask import Flask, jsonify, request, redirect, url_for, render_template_string, session
from dotenv import load_dotenv
import os
import threading

# --- CONFIG BOT ---
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")  # ⚠️ mets ton token dans Railway > Variables d’env

bot = commands.Bot(command_prefix="!", intents=intents)
PRIVATE_CHANNEL_ID = 1393953102088114197  # salon commandes
MARKET_CHANNEL_ID = 1393933918364893339   # salon marché noir
bot.market_message = None

# --- CONFIG API FLASK ---
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "secret")  # session sécurisée
PRODUITS_FILE = "produits.json"
USERS = {"admin": "admin123"}  # login admin

# --- TEMPLATES HTML (inline) ---
login_html = """
<!DOCTYPE html>
<html>
<head><title>Login</title></head>
<body>
  <h2>Connexion Admin</h2>
  <form method="POST">
    <input type="text" name="username" placeholder="Utilisateur" required><br>
    <input type="password" name="password" placeholder="Mot de passe" required><br>
    <button type="submit">Se connecter</button>
  </form>
  {% if error %}<p style="color:red">{{ error }}</p>{% endif %}
</body>
</html>
"""

admin_html = """
<!DOCTYPE html>
<html>
<head><title>Admin</title></head>
<body>
  <h2>📦 Panel Admin</h2>
  <p><a href="{{ url_for('logout') }}">Déconnexion</a></p>

  <h3>Produits actuels</h3>
  <pre>{{ produits|tojson(indent=2) }}</pre>

  <h3>Ajouter un produit</h3>
  <form method="POST">
    <input type="text" name="categorie" placeholder="Catégorie" required><br>
    <input type="text" name="nom" placeholder="Nom produit" required><br>
    <input type="number" name="prix" placeholder="Prix (k)" required><br>
    <button type="submit">Ajouter</button>
  </form>
</body>
</html>
"""

# --- ROUTES FLASK ---
@app.route("/")
def home():
    return "✅ Bot + Site en ligne !"

@app.route("/api/produits")
def api_produits():
    try:
        with open(PRODUITS_FILE, "r") as f:
            produits = json.load(f)
    except FileNotFoundError:
        produits = {}
    return jsonify(produits)

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        user = request.form["username"]
        pwd = request.form["password"]
        if user in USERS and USERS[user] == pwd:
            session["user"] = user
            return redirect(url_for("admin"))
        else:
            error = "Identifiants invalides"
    return render_template_string(login_html, error=error)

@app.route("/admin", methods=["GET", "POST"])
def admin():
    if "user" not in session:
        return redirect(url_for("login"))

    try:
        with open(PRODUITS_FILE, "r") as f:
            produits = json.load(f)
    except FileNotFoundError:
        produits = {}

    if request.method == "POST":
        cat = request.form["categorie"]
        nom = request.form["nom"]
        prix = int(request.form["prix"])
        produits.setdefault(cat, []).append([nom, prix])
        with open(PRODUITS_FILE, "w") as f:
            json.dump(produits, f, indent=2)

    return render_template_string(admin_html, produits=produits)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# --- Charger produits ---
async def charger_produits():
    try:
        with open(PRODUITS_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

# --- Embed marché noir ---
def creer_embed(produits):
    embed = discord.Embed(
        title="💀 𝗗𝗔𝗥𝗞 𝗠𝗔𝗥𝗞𝗘𝗧 💀",
        description="Bienvenue dans l'ombre...\n〄 **Cosa Nostra Approved** 〄",
        color=discord.Color.dark_red()
    )
    for cat, items in produits.items():
        if not items:
            continue
        liste = "\n".join([f"🔪 **{nom}** 〙 `{prix}k`" for nom, prix in items])
        embed.add_field(name=f"📦 {cat.upper()}", value=liste, inline=False)
    return embed

# --- Actualisation auto ---
async def actualiser_produits():
    await bot.wait_until_ready()
    while not bot.is_closed():
        bot.produits = await charger_produits()
        if bot.market_message:
            embed = creer_embed(bot.produits)
            await bot.market_message.edit(embed=embed, view=AchatView(bot.produits))
        await asyncio.sleep(60)

# --- Views / Modals (inchangés, à garder comme tu avais) ---
class LivraisonView(discord.ui.View): ...
class AchatModal(discord.ui.Modal, title="🛒 Passer une commande"): ...
class ProduitSelect(discord.ui.Select): ...
class ProduitSelectView(discord.ui.View): ...
class CategorieSelect(discord.ui.Select): ...
class CategorieSelectView(discord.ui.View): ...
class AchatView(discord.ui.View): ...

# --- Commande admin Discord ---
@bot.command()
@commands.has_permissions(administrator=True)
async def actualiser(ctx):
    bot.produits = await charger_produits()
    if bot.market_message:
        embed = creer_embed(bot.produits)
        await bot.market_message.edit(embed=embed, view=AchatView(bot.produits))
    await ctx.send("✅ Produits actualisés !")

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

# --- Lancer Flask ---
def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

# --- Lancer BOT + SITE ---
if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    bot.run(TOKEN)
