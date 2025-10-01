import sqlite3
from flask import Flask, request, jsonify

app = Flask(__name__)
DB_NAME = "produkte.db"

# Datenbank initialisieren (nur einmal nötig)
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        price REAL NOT NULL
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

# GET: Alle Produkte
@app.route("/api/products", methods=["GET"])
def get_products():
    conn = get_db_connection()
    products = conn.execute("SELECT * FROM products").fetchall()
    conn.close()
    return jsonify([dict(row) for row in products])

# GET: Einzelnes Produkt
@app.route("/api/products/<int:product_id>", methods=["GET"])
def get_product(product_id):
    conn = get_db_connection()
    product = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    conn.close()
    if product:
        return jsonify(dict(product))
    return jsonify({"error": "Produkt nicht gefunden"}), 404

# POST: Neues Produkt hinzufügen
@app.route("/api/products/", methods=["POST"])
def add_product():
    data = request.get_json()
    name = data.get("name")
    price = data.get("price")

    if not name or not price:
        return jsonify({"error": "Name und Preis erforderlich"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO products (name, price) VALUES (?, ?)", (name, price))
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()
    return jsonify({"id": new_id, "name": name, "price": price}), 201

# PUT: Produkt ändern
@app.route("/api/products/<int:product_id>", methods=["PUT"])
def update_product(product_id):
    data = request.get_json()
    name = data.get("name")
    price = data.get("price")

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


if __name__ == "__main__":
    init_db()   # Datenbank & Tabelle beim Start sicherstellen
    app.run(debug=True)
