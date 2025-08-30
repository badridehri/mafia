from flask import Flask, render_template, request, redirect, jsonify, session, url_for
import json
import os
import threading
import discord
from discord.ext import commands
import aiohttp
from dotenv import load_dotenv

# ================== FLASK (ton app.py inchangé) ==================
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "une_clef_secrete_super_longue_et_difficile")

USERS_FILE = "users.json"
PRODUITS_FILE = "produits.json"

@app.route("/", methods=["GET", "POST"])
def login():
    message = ""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if not username or not password:
            message = "Veuillez remplir tous les champs ❌"
            return render_template("login.html", message=message)

        try:
            with open(USERS_FILE, "r", encoding="utf-8") as f:
                users = json.load(f)
        except FileNotFoundError:
            message = "Fichier utilisateurs introuvable ❌"
            return render_template("login.html", message=message)

        user = next((u for u in users if u["username"] == username and u["password"] == password), None)
        if user:
            session["logged_in"] = True
            return redirect("/admin")
        else:
            message = "Nom d'utilisateur ou mot de passe incorrect ❌"

    return render_template("login.html", message=message)

@app.route("/admin", methods=["GET", "POST"])
def admin():
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    try:
        with open(PRODUITS_FILE, "r", encoding="utf-8") as f:
            produits = json.load(f)
    except FileNotFoundError:
        produits = {}

    message = ""
    if request.method == "POST":
        action = request.form.get("action")
        cat = request.form.get("categorie", "").strip()
        nom = request.form.get("nom", "").strip()
        prix = request.form.get("prix", "").strip()

        if not cat or not nom:
            message = "Catégorie et nom du produit sont obligatoires ❌"
            return render_template("admin.html", produits=produits, message=message)

        if action == "ajouter":
            try:
                prix = int(prix)
            except ValueError:
                message = "Le prix doit être un nombre ❌"
                return render_template("admin.html", produits=produits, message=message)

            if cat not in produits:
                produits[cat] = []
            produits[cat].append([nom, prix])
            message = f"Produit {nom} ajouté à {cat} ✅"

        elif action == "supprimer":
            if cat in produits:
                produits[cat] = [p for p in produits[cat] if p[0] != nom]
                message = f"Produit {nom} supprimé de {cat} ✅"
            else:
                message = f"Catégorie {cat} inexistante ❌"

        with open(PRODUITS_FILE, "w", encoding="utf-8") as f:
            json.dump(produits, f, indent=4, ensure_ascii=False)

    return render_template("admin.html", produits=produits, message=message)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/api/produits", methods=["GET"])
def api_produits():
    try:
        with open(PRODUITS_FILE, "r", encoding="utf-8") as f:
            produits = json.load(f)
    except FileNotFoundError:
        produits = {}
    print("API /api/produits appelée : ", produits)
    return jsonify(produits)

# ================== DISCORD BOT (ton bot.py ajouté) ==================
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"✅ Connecté en tant que {bot.user}")

@bot.command()
async def produits(ctx):
    """Affiche les produits depuis l'API Flask"""
    async with aiohttp.ClientSession() as session:
        async with session.get("http://localhost:5000/api/produits") as resp:
            if resp.status == 200:
                data = await resp.json()
                if not data:
                    await ctx.send("⚠️ Aucun produit disponible.")
                    return

                message = "**🛒 Produits disponibles :**\n"
                for cat, items in data.items():
                    message += f"\n**{cat}**\n"
                    for nom, prix in items:
                        message += f"- {nom} : {prix}€\n"
                await ctx.send(message)
            else:
                await ctx.send("❌ Erreur API produits.")

# ================== LANCEMENT FLASK + BOT ==================
def run_discord_bot():
    bot.run(TOKEN)

if __name__ == "__main__":
    # Lance le bot dans un thread séparé
    t = threading.Thread(target=run_discord_bot)
    t.start()

    # Lance Flask
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
