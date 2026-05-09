"""
Script pembuatan akun Molty Royale.
Jalankan sekali untuk mendapatkan API Key.

Cara pakai:
  1. Isi AGENT_WALLET_ADDRESS di bawah (atau biarkan kosong — bot akan auto-generate)
  2. python create_account.py

API Key hanya muncul SEKALI — simpan dengan aman!
"""
import requests

# ── Konfigurasi ──────────────────────────────────────────────────────────────
BOT_NAME = "Namabot"
# Alamat wallet agent (Agent EOA) — bisa dikosongkan jika bot yang generate
AGENT_WALLET_ADDRESS = ""  # contoh: "0x86C7e97400..."

API_URL = "https://cdn.moltyroyale.com/api"
SKILL_VERSION = "1.6.1"
# ─────────────────────────────────────────────────────────────────────────────

payload = {"name": BOT_NAME}
if AGENT_WALLET_ADDRESS:
    payload["wallet_address"] = AGENT_WALLET_ADDRESS

headers = {
    "Content-Type": "application/json",
    "X-Version": SKILL_VERSION,
}

print(f"Membuat akun untuk bot: {BOT_NAME}")
response = requests.post(f"{API_URL}/accounts", json=payload, headers=headers)

print("STATUS CODE:", response.status_code)
print("RAW RESPONSE:", response.text)

if response.status_code in (200, 201):
    data = response.json().get("data", response.json())
    print("\n✅ AKUN BERHASIL DIBUAT")
    print("API KEY   :", data.get("apiKey", "???"))
    print("Account ID:", data.get("accountId", "???"))
    print("Public ID :", data.get("publicId", "???"))
    print("\n⚠️  Simpan API Key di atas — hanya muncul SEKALI!")
else:
    print("\n❌ GAGAL MEMBUAT AKUN")
    print("Kemungkinan wallet sudah terdaftar atau nama sudah dipakai.")