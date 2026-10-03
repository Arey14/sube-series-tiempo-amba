"""
Script para descargar y actualizar el dataset oficial de transacciones y usuarios diarios SUBE AMBA
Fuente: Portal Nacional de Datos Abiertos de Transporte (datos.transporte.gob.ar)
"""

import os
import urllib.request

DATA_URL = "https://archivos-datos.transporte.gob.ar/upload/Sube/total-usuarios-por-dia-AMBA.csv"
DEST_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "total-usuarios-por-dia-AMBA.csv")


def descargar_datos():
    os.makedirs(os.path.dirname(DEST_PATH), exist_ok=True)
    print(f"Descargando dataset oficial desde: {DATA_URL}...")
    req = urllib.request.Request(DATA_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as resp, open(DEST_PATH, "wb") as f:
        f.write(resp.read())
    size_kb = os.path.getsize(DEST_PATH) / 1024
    print(f"✅ Descarga completada exitosamente: {DEST_PATH} ({size_kb:.1f} KB)")


if __name__ == "__main__":
    descargar_datos()
