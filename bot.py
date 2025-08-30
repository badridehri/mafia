import discord
from discord.ext import commands
from flask import Flask, render_template, request, redirect, session, url_for
import json
import os
from dotenv import load_dotenv
import threading

# --- CONFIG BOT DISCORD ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# --- FLASK APP ---
app = Flask(__name__)
app.secret_key = "super_secret_key"

# Charger utilisateurs
if not os.path.exists("users.json"):
    with open("users.json", "w") as f:
        json.dump([{"username": "admin", "password": "admin"}], f)

with open("users.json", "r") as f:
    users = json.load(f)

# Charger produits
if not os.path.exists("produits.json"):
    with open("produits.json", "w") as f:
        json.dump([], f)

with open("produits.json", "r") as f:
    produits = json.load(f)

# --- ROUTES FLASK ---
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        for user in users:
            if user["username"] == username and user["password"] == password:
                session["user"] = username
                return redirect("/admin")

        return render_template("login.html", message="Identifiants invalides")
    return render_template("login.html", message="")

@app.route("/admin", methods=["GET", "POST"])
def admin():
    if "user" not in session:
        return redirect("/")
    message = ""
    if request.method == "POST":
        action = request.form.get("action")
        if action == "ajouter":
            categorie = request.form["categorie"]
            nom = request.form["nom"]
            prix = request.form["prix"]
            produits.append({"categorie": categorie, "nom": nom, "prix": prix})
            with open("produits.json", "w") as f:
                json.dump(produits, f, indent=4)
            message = f"Produit {nom} ajouté avec succès !"
    return render_template("admin.html", produits=produits, message=message)

@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect("/")

# --- FONCTION POUR LANCER FLASK ---
def run_flask():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

# --- BOT EVENTS ---
@bot.event
async def on_ready():
    print(f"✅ Connecté en tant que {bot.user}")

@bot.command()
async def ping(ctx):
    await ctx.send("Pong!")

# --- START ---
if __name__ == "__main__":
    # Lancer Flask dans un thread
    threading.Thread(target=run_flask).start()
    # Lancer Discord bot
    bot.run(TOKEN)
