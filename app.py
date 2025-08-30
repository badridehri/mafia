from flask import Flask, render_template, request, redirect, jsonify, session, url_for
import json
import os

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "une_clef_secrete_super_longue_et_difficile")  
# 👉 Utilise une vraie clé dans Render/Railway : ajoute une variable d’env. SECRET_KEY

USERS_FILE = "users.json"
PRODUITS_FILE = "produits.json"

# --- Login ---
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
            session["logged_in"] = True  # L'utilisateur est connecté
            return redirect("/admin")
        else:
            message = "Nom d'utilisateur ou mot de passe incorrect ❌"

    return render_template("login.html", message=message)


# --- Admin page ---
@app.route("/admin", methods=["GET", "POST"])
def admin():
    if not session.get("logged_in"):  # Protection de la page admin
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

        # Sauvegarder les changements
        with open(PRODUITS_FILE, "w", encoding="utf-8") as f:
            json.dump(produits, f, indent=4, ensure_ascii=False)

    return render_template("admin.html", produits=produits, message=message)


# --- Déconnexion ---
@app.route("/logout")
def logout():
    session.clear()  # Supprime toutes les données de session
    return redirect(url_for("login"))


# --- API produits pour le bot ---
@app.route("/api/produits", methods=["GET"])
def api_produits():
    try:
        with open(PRODUITS_FILE, "r", encoding="utf-8") as f:
            produits = json.load(f)
    except FileNotFoundError:
        produits = {}
    print("API /api/produits appelée : ", produits)  # DEBUG
    return jsonify(produits)


# --- Lancement ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # Render/Railway/Heroku donnent PORT
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
