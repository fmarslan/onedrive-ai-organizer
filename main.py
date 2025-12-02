#!/usr/bin/env python
"""
OneDrive klasör & dosya ağacını çıkarıp onedrive_tree.csv olarak kaydeden tek script.

Kullanım (lokal):
    pip install -r requirements.txt
    # CLIENT_ID'yi ortam değişkeni ile (önerilen)
    export MS_CLIENT_ID="00000000-0000-0000-0000-000000000000"
    python main.py

Kullanım (Colab):
    !pip install -r requirements.txt
    # İstersen burada set edebilirsin:
    # %env MS_CLIENT_ID=00000000-0000-0000-0000-000000000000
    !python main.py
"""

import os
import time
import sys
import msal
import requests
import pandas as pd


GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"
SCOPES = ["Files.Read.All"]  # sadece okuma (temizlik için ek izin gerekebilir)


def get_config():
    """
    CLIENT_ID ve TENANT bilgisini al.
    - CLIENT_ID: zorunlu (Azure App Registration'dan)
    - TENANT: 'organizations' varsayılan, istersen 'common' kullanabilirsin
    """
    client_id = os.environ.get("MS_CLIENT_ID")
    if not client_id:
        client_id = input("Azure Application (client) ID (MS_CLIENT_ID yok): ").strip()

    if not client_id:
        print("HATA: Bir CLIENT_ID vermen gerekiyor (Azure App Registration).")
        sys.exit(1)

    tenant = os.environ.get("MS_TENANT", "organizations")
    authority = f"https://login.microsoftonline.com/{tenant}"

    return client_id, authority


def acquire_token_device_code(client_id, authority):
    """
    Device code flow ile kullanıcıyı login / authorize etmeye yönlendirir.
    Sen sadece ekrandaki URL'ye gidip kodu girersin, gerisini MSAL halleder.
    """
    app = msal.PublicClientApplication(client_id, authority=authority)

    flow = app.initiate_device_flow(scopes=SCOPES)
    if "user_code" not in flow:
        raise RuntimeError("Device flow başlatılamadı. Azure app ayarlarını kontrol et.")

    print("\n=== Yetkilendirme Adımları ===\n")
    print(flow["message"])  # Burada gideceğin URL ve gireceğin kod yazıyor.
    print("\nBu adımı tamamladıktan sonra bu script otomatik devam edecek...\n")

    result = app.acquire_token_by_device_flow(flow)
    if "access_token" not in result:
        raise RuntimeError(f"Token alınamadı: {result}")

    print("✅ Access token alındı.\n")
    return result["access_token"]


def graph_get(url, access_token, params=None):
    """Graph GET isteği + pagination, tüm sayfalardaki 'value'ları birleştirir."""
    headers = {"Authorization": f"Bearer {access_token}"}
    items = []

    while url:
        resp = requests.get(url, headers=headers, params=params)
        if resp.status_code != 200:
            print("Hata:", resp.status_code, resp.text)
            resp.raise_for_status()

        data = resp.json()
        items.extend(data.get("value", []))
        url = data.get("@odata.nextLink", None)
        params = None  # nextLink zaten parametre içerir

        time.sleep(0.1)  # API'yi çok sık boğmamak için küçük gecikme

    return items


def walk_onedrive(access_token):
    """
    Tüm OneDrive ağacını dolaş ve sonuçları liste olarak döndür.
    Rekürsiyon yerine stack kullanıyoruz (derin klasörlerde recursion limit'e takılmamak için).
    """
    headers = {"Authorization": f"Bearer {access_token}"}
    root_resp = requests.get(f"{GRAPH_BASE_URL}/me/drive/root", headers=headers)
    root_resp.raise_for_status()
    root = root_resp.json()

    root_id = root["id"]
    root_name = root.get("name", "root")
    print(f"Kök klasör: {root_name} (id={root_id})")
    print("Tüm ağaç taranıyor, bu biraz sürebilir...\n")

    results = []
    stack = [(root_id, "")]  # (item_id, path_prefix)

    while stack:
        current_id, current_path = stack.pop()

        children_url = f"{GRAPH_BASE_URL}/me/drive/items/{current_id}/children"
        children = graph_get(children_url, access_token)

        for ch in children:
            name = ch.get("name")
            is_folder = "folder" in ch
            size = ch.get("size", 0)
            last_modified = ch.get("lastModifiedDateTime")
            item_id = ch.get("id")
            web_url = ch.get("webUrl")

            full_path = f"{current_path}/{name}" if current_path else name

            results.append(
                {
                    "id": item_id,
                    "path": full_path,
                    "name": name,
                    "is_folder": is_folder,
                    "size": size,
                    "last_modified": last_modified,
                    "web_url": web_url,
                }
            )

            if is_folder:
                stack.append((item_id, full_path))

    print(f"✅ Tarama bitti. Toplam öğe sayısı: {len(results)}")
    return results


def main():
    client_id, authority = get_config()
    access_token = acquire_token_device_code(client_id, authority)
    results = walk_onedrive(access_token)

    df = pd.DataFrame(results)
    output_file = "onedrive_tree.csv"
    df.to_csv(output_file, index=False, encoding="utf-8")

    print(f"\n✅ Klasör ağacı '{output_file}' dosyasına kaydedildi.")
    print("Bu dosyayı GitHub'a, Colab'e veya istediğin yere atıp analiz edebilirsin.")


if __name__ == "__main__":
    main()
