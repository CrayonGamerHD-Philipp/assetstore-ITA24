import sqlite3
import os
from flask import Flask, request, jsonify, send_from_directory

app = Flask(__name__)
DB_NAME = "produkte.db"

# Ordner für Bilder
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# Datenbank initialisieren (nur einmal nötig)
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_name TEXT NOT NULL,
        price DOUBLE NOT NULL,
        description TEXT,
        sale INTEGER
    )
    """)

    # Bilder-Tabelle
    cursor.execute("""
       CREATE TABLE IF NOT EXISTS images (
           id INTEGER PRIMARY KEY AUTOINCREMENT,
           product_id INTEGER NOT NULL,
           filename TEXT NOT NULL,
           FOREIGN KEY (product_id) REFERENCES products (id)
       )
       """)
    conn.commit()
    conn.close()

# Hilfsfunktion: Verbindung zur DB
def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row  # für dict-artige Ergebnisse
    return conn

# --- ROUTES ---

# GET: Alle Produkte + Bilder abrufen
@app.route("/api/products", methods=["GET"])
def get_products():
    conn = get_db_connection()
    products = conn.execute("SELECT * FROM products").fetchall()

    result = []
    for p in products:
        images = conn.execute("SELECT filename FROM images WHERE product_id = ?", (p["id"],)).fetchall()
        result.append({
            "id": p["id"],
            "name": p["name"],
            "price": p["price"],
            "images": [f"/uploads/{p['id']}/{img['filename']}" for img in images]
        })

    conn.close()
    return jsonify(result)

# Produkt hinzufügen (noch ohne Bilder)
@app.route("/api/products", methods=["POST"])
def add_product():
    name = request.form.get("name")
    price = request.form.get("price")

    if not name or not price:
        return jsonify({"error": "Name und Preis erforderlich"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO products (name, price) VALUES (?, ?)", (name, price))
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()

    # Produkt-Ordner anlegen
    os.makedirs(os.path.join(app.config["UPLOAD_FOLDER"], str(new_id)), exist_ok=True)

    return jsonify({"id": new_id, "name": name, "price": price, "images": []}), 201

# GET: Einzelnes Produkt
@app.route("/api/products/<int:product_id>", methods=["GET"])
def get_product(product_id):
    conn = get_db_connection()
    product = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()

    if not product:
        conn.close()
        return jsonify({"error": "Produkt nicht gefunden"}), 404

    images = conn.execute("SELECT filename FROM images WHERE product_id = ?", (product_id,)).fetchall()
    conn.close()

    return jsonify({
        "id": product["id"],
        "name": product["name"],
        "price": product["price"],
        "images": [f"/uploads/{product_id}/{img['filename']}" for img in images]
    })

# Bilder zu Produkt hochladen
@app.route("/api/products/<int:product_id>/upload", methods=["POST"])
def upload_image(product_id):
    if "file" not in request.files:
        return jsonify({"error": "Kein Bild hochgeladen"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "Keine Datei ausgewählt"}), 400

    # Zielordner pro Produkt
    product_folder = os.path.join(app.config["UPLOAD_FOLDER"], str(product_id))
    os.makedirs(product_folder, exist_ok=True)

    filepath = os.path.join(product_folder, file.filename)
    file.save(filepath)

    # In DB eintragen
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO images (product_id, filename) VALUES (?, ?)", (product_id, file.filename))
    conn.commit()
    conn.close()

    return jsonify({"message": "Upload erfolgreich", "file": f"/uploads/{product_id}/{file.filename}"}), 201

# Produkt ändern (Name/Preis)
@app.route("/api/products/<int:product_id>", methods=["PUT"])
def update_product(product_id):
    data = request.get_json()
    name = data.get("name")
    price = data.get("price")

    if not name or not price:
        return jsonify({"error": "Name und Preis erforderlich"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE products SET name = ?, price = ? WHERE id = ?", (name, price, product_id))
    conn.commit()
    updated = cursor.rowcount
    conn.close()

    if updated == 0:
        return jsonify({"error": "Produkt nicht gefunden"}), 404

    return jsonify({"id": product_id, "name": name, "price": price})

# DELETE: Produkt löschen
@app.route("/api/products/<int:product_id>", methods=["DELETE"])
def delete_product(product_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM products WHERE id = ?", (product_id,))
    conn.commit()
    deleted = cursor.rowcount
    conn.close()

    if deleted == 0:
        return jsonify({"error": "Produkt nicht gefunden"}), 404
    return jsonify({"message": "Produkt gelöscht"})

# Route: Bilder ausliefern
@app.route("/uploads/<int:product_id>/<filename>")
def get_image(product_id, filename):
    return send_from_directory(os.path.join(app.config["UPLOAD_FOLDER"], str(product_id)), filename)

# Einzelnes Bild löschen
@app.route("/api/products/<int:product_id>/images/<int:image_id>", methods=["DELETE"])
def delete_image(product_id, image_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    # Bild aus DB holen
    cursor.execute("SELECT filename FROM images WHERE id = ? AND product_id = ?", (image_id, product_id))
    image = cursor.fetchone()

    if not image:
        conn.close()
        return jsonify({"error": "Bild nicht gefunden"}), 404

    filename = image["filename"]
    file_path = os.path.join(app.config["UPLOAD_FOLDER"], str(product_id), filename)

    # Datei löschen
    if os.path.exists(file_path):
        os.remove(file_path)

    # DB-Eintrag löschen
    cursor.execute("DELETE FROM images WHERE id = ? AND product_id = ?", (image_id, product_id))
    conn.commit()
    conn.close()

    return jsonify({"message": f"Bild {filename} gelöscht"})


# Einzelnes Bild ersetzen (z. B. neues hochladen an Stelle des alten)
@app.route("/api/products/<int:product_id>/images/<int:image_id>", methods=["PUT"])
def update_image(product_id, image_id):
    if "file" not in request.files:
        return jsonify({"error": "Kein Bild hochgeladen"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "Keine Datei ausgewählt"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    # Altes Bild aus DB holen
    cursor.execute("SELECT filename FROM images WHERE id = ? AND product_id = ?", (image_id, product_id))
    old_image = cursor.fetchone()

    if not old_image:
        conn.close()
        return jsonify({"error": "Bild nicht gefunden"}), 404

    old_filename = old_image["filename"]
    old_path = os.path.join(app.config["UPLOAD_FOLDER"], str(product_id), old_filename)

    # Altes Bild löschen (falls vorhanden)
    if os.path.exists(old_path):
        os.remove(old_path)

    # Neues Bild speichern
    product_folder = os.path.join(app.config["UPLOAD_FOLDER"], str(product_id))
    os.makedirs(product_folder, exist_ok=True)
    new_path = os.path.join(product_folder, file.filename)
    file.save(new_path)

    # DB aktualisieren
    cursor.execute("UPDATE images SET filename = ? WHERE id = ? AND product_id = ?", (file.filename, image_id, product_id))
    conn.commit()
    conn.close()

    return jsonify({"message": "Bild ersetzt", "new_file": f"/uploads/{product_id}/{file.filename}"})


if __name__ == "__main__":
    init_db()   # Datenbank & Tabelle beim Start sicherstellen
    app.run(debug=True)
