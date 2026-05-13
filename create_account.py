"""
Script pembuatan akun Claw Royale.
Jalankan sekali untuk mendapatkan API Key.

Cara pakai:
  1. Isi AGENT_WALLET_ADDRESS di bawah (atau biarkan kosong — bot akan auto-generate)
  2. python create_account.py

API Key hanya muncul SEKALI — simpan dengan aman!
"""
import time
import requests
import uuid

# ── Konfigurasi ──────────────────────────────────────────────────────────────
# Gunakan nama yang unik — duplikat nama tidak diperbolehkan di v1.6.1
BOT_NAME = f"Namabot-{uuid.uuid4().hex[:4]}" 
# Alamat wallet agent (Agent EOA) — bisa dikosongkan jika bot yang generate
AGENT_WALLET_ADDRESS = ""  

API_URL = "https://cdn.clawroyale.ai/api"
SKILL_VERSION = "1.6.2"
# ─────────────────────────────────────────────────────────────────────────────

payload = {"name": BOT_NAME}
if AGENT_WALLET_ADDRESS:
    payload["wallet_address"] = AGENT_WALLET_ADDRESS

headers = {
    "Content-Type": "application/json",
    "X-Version": SKILL_VERSION,
    # v1.6.1 preferensi Authorization untuk auth
}

print(f"Membuat akun untuk bot: {BOT_NAME}")
print("Menghubungi server Claw Royale...")

try:
    response = requests.post(f"{API_URL}/accounts", json=payload, headers=headers)
    response.raise_for_status()
    data = response.json().get("data", response.json())
    
    print("\n✅ AKUN BERHASIL DIBUAT")
    print(f"Nama Bot   : {BOT_NAME}")
    print(f"API KEY    : {data.get('apiKey', '???')}")
    print(f"Account ID : {data.get('accountId', '???')}")
    print(f"Public ID  : {data.get('publicId', '???')}")
    
    print("\n⚠️  Simpan API Key di atas — hanya muncul SEKALI!")
    print("⚠️  PENTING: Akun baru memiliki masa pembatasan 1 MENIT sebelum bisa join game.")
    print("    Silakan tunggu sebentar sebelum menjalankan bot utama.")

except requests.exceptions.HTTPError as e:
    print(f"\n❌ GAGAL MEMBUAT AKUN: {e}")
    if response.status_code == 409:
        print("Nama sudah dipakai atau wallet sudah terdaftar. Gunakan nama unik!")
    elif response.status_code == 426:
        print("Skill version outdated! Update SKILL_VERSION di skrip.")
    else:
        print("Response:", response.text)
except Exception as e:
    print(f"\n❌ ERROR: {e}")