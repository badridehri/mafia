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
TOKEN = os.getenv("DISCORD_TOKEN")  # Charge le token depuis .env

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
async def charger_produits():
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("http://127.0.0.1:5000/api/produits") as response:
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

# --- Suivi livraison ---
class LivraisonView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Marquer comme livrée", style=discord.ButtonStyle.green)
    async def livrer(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Tu n'as pas la permission pour livrer.", ephemeral=True)
            return

        embed = interaction.message.embeds[0]
        embed.color = discord.Color.green()
        embed.set_footer(text="✅ Commande livrée")
        await interaction.message.edit(embed=embed, view=None)
        await interaction.response.send_message("Commande marquée comme livrée ✅", ephemeral=True)

# --- Modal commande ---
class AchatModal(discord.ui.Modal, title="🛒 Passer une commande"):
    def __init__(self, produit_nom: str, prix: int):
        super().__init__()
        self.produit_nom = produit_nom
        self.prix = prix
        self.quantite = discord.ui.TextInput(label="Quantité", placeholder="Ex: 2", required=True)
        self.groupe = discord.ui.TextInput(label="Nom de votre groupe", placeholder="Ex: Les Sans-Nom", required=True)
        self.add_item(self.quantite)
        self.add_item(self.groupe)

    async def on_submit(self, interaction: discord.Interaction):
        private_channel = bot.get_channel(PRIVATE_CHANNEL_ID)
        if private_channel is None:
            await interaction.response.send_message("⚠️ Salon privé introuvable.", ephemeral=True)
            return

        try:
            qte = int(self.quantite.value)
        except ValueError:
            await interaction.response.send_message("⚠️ Quantité invalide.", ephemeral=True)
            return

        total = qte * self.prix
        nom_groupe = self.groupe.value

        embed = discord.Embed(title="🛒 Nouvelle commande", color=discord.Color.red())
        embed.add_field(name="👤 Acheteur", value=interaction.user.mention, inline=False)
        embed.add_field(name="🏷️ Groupe", value=nom_groupe, inline=False)
        embed.add_field(name="📦 Produit", value=self.produit_nom, inline=True)
        embed.add_field(name="🔢 Quantité", value=str(qte), inline=True)
        embed.add_field(name="💵 Prix unitaire", value=f"{self.prix}k", inline=True)
        embed.add_field(name="💰 Total", value=f"{total}k", inline=False)
        embed.set_footer(text="❌ Pas encore livrée")

        await private_channel.send(embed=embed, view=LivraisonView())
        await interaction.response.send_message(
            f"✅ Ta commande pour **{qte}x {self.produit_nom}** ({total}k) a été envoyée.",
            ephemeral=True
        )

# --- Sélecteur catégories et produits ---
class ProduitSelect(discord.ui.Select):
    def __init__(self, categorie, produits):
        self.categorie = categorie
        self.produits = produits
        items = produits.get(categorie, [])

        options = []
        if not items:
            options.append(discord.SelectOption(label="Aucun produit", value="none", default=True))
        else:
            seen = set()
            for nom, prix in items:
                if nom not in seen:
                    options.append(discord.SelectOption(label=nom, value=f"{categorie}-{nom}", description=f"{prix}k"))
                    seen.add(nom)

        super().__init__(placeholder=f"Choisis ton {categorie}...", options=options)

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "none":
            await interaction.response.send_message("Cette catégorie est vide ❌", ephemeral=True)
            return
        nom = self.values[0].split("-", 1)[1]
        prix = next((p for n, p in self.produits[self.categorie] if n == nom), None)
        if prix is None:
            await interaction.response.send_message("Produit introuvable ❌", ephemeral=True)
            return
        await interaction.response.send_modal(AchatModal(nom, prix))

class ProduitSelectView(discord.ui.View):
    def __init__(self, categorie, produits):
        super().__init__()
        self.add_item(ProduitSelect(categorie, produits))

class CategorieSelect(discord.ui.Select):
    def __init__(self, produits):
        options = [discord.SelectOption(label=cat, description=f"{len(items)} produits") for cat, items in produits.items() if items]
        super().__init__(placeholder="Choisis une catégorie...", options=options)
        self.produits = produits

    async def callback(self, interaction: discord.Interaction):
        cat = self.values[0]
        await interaction.response.edit_message(content=f"Produits dans **{cat}** :", view=ProduitSelectView(cat, self.produits))

class CategorieSelectView(discord.ui.View):
    def __init__(self, produits):
        super().__init__()
        self.add_item(CategorieSelect(produits))

class AchatView(discord.ui.View):
    def __init__(self, produits):
        super().__init__(timeout=None)
        self.produits = produits

    @discord.ui.button(label="🛒 Acheter", style=discord.ButtonStyle.green)
    async def acheter(self, interaction: discord.Interaction, button: discord.ui.Button):
        categories_valide = {cat: items for cat, items in self.produits.items() if items}
        if not categories_valide:
            await interaction.response.send_message("❌ Aucun produit disponible.", ephemeral=True)
            return
        await interaction.response.send_message("Choisis une catégorie :", view=CategorieSelectView(categories_valide), ephemeral=True)

# --- Commande admin ---
@bot.command()
@commands.has_permissions(administrator=True)
async def actualiser(ctx):
    bot.produits = await charger_produits()
    if bot.market_message:
        embed = creer_embed(bot.produits)
        await bot.market_message.edit(embed=embed, view=AchatView(bot.produits))
    await ctx.send("✅ Produits actualisés depuis le site web!")

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
    port = int(os.environ.get("PORT", 5000))  # Railway fournit $PORT
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)


threading.Thread(target=run_flask, daemon=True).start()

bot.run(TOKEN)
