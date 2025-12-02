# OneDrive AI Organizer – Klasör Ağacı Çıkarıcı (Colab)

Bu proje, OneDrive hesabındaki **tüm klasör ve dosya ağacını**  
**Google Colab** üzerinden çıkarıp bir **CSV dosyasına** kaydetmek için hazırlandı.

- Çalıştırma ortamı: **Google Colab**
- Kaynak kod: **GitHub**
- Kimlik doğrulama: **Microsoft Graph + Device Code Flow**
- Kullanıcıdan beklenen: Sadece Microsoft hesabıyla oturum açıp **yetkilendirmeyi onaylamak** ✅

---

## 0. Ön koşul – Azure’da App Registration (bir kereye mahsus)

1. `https://portal.azure.com` adresine git.
2. **Azure Active Directory → App registrations → New registration**
3. İsim örneği: `onedrive-ai-organizer-app`
4. **Supported account types**:  
   `Accounts in this organizational directory only` (veya `common/organizations` ihtiyaca göre)
5. Register’a tıkla.
6. Açılan ekranda:
   - **Application (client) ID**’yi not al → bunu Colab’de kullanacağız.
7. Sol menüden **Authentication**:
   - `Add a platform` → `Mobile and desktop applications`
   - Redirect URI olarak:
     - `https://login.microsoftonline.com/common/oauth2/nativeclient`
   - Eğer varsa **Allow public client flows** / benzeri seçenekleri **Enable** et.
8. Sol menüden **API permissions**:
   - `Add a permission` → `Microsoft Graph` → `Delegated`
   - En az:
     - `Files.Read.All`
   - Gerekirse admin’den `Grant admin consent` iste.

> Bu adımlar tek seferlik. Sonrasında Colab defterinde sadece **CLIENT_ID** yazman yeterli olacak.

---

## 1. Bu not defterini Colab’te aç

Aşağıdaki butona tıklayarak projedeki notebook’u **direkt Google Colab’te açabilirsin**:

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/<GITHUB_USER>/onedrive-ai-organizer/blob/master/notebooks/onedrive_tree.ipynb)

> Not: İlk seferde `onedrive_tree.ipynb` yoksa, Colab’te yeni bir notebook oluşturup  
> kaydedebilir, sonra bu linki README’ye ekleyebilirsin.

---

## 2. Notebook ne yapıyor?

1. Gerekli Python paketlerini yüklüyor (`msal`, `requests`, `pandas`, `tqdm`).
2. Senin girdiğin **CLIENT_ID** ve tenant bilgisiyle **device code flow** başlatıyor.
3. Ekrana **“Şu adrese git → şu kodu gir”** mesajını yazıyor.
4. Sen tarayıcıda açıp Microsoft hesabınla giriş yapıp yetki veriyorsun.
5. Kod, aldığın access token ile:
   - `me/drive/root` üzerinden **OneDrive kök klasörünü** buluyor,
   - Tüm klasör/dosya ağacını **rekürsif geziyor**,
   - Her öğe için: `id, path, is_folder, size, last_modified, web_url` bilgilerini topluyor.
6. Sonuçları `onedrive_tree.csv` dosyasına kaydedip indirilebilir hale getiriyor.

---

## 3. Sonraki adım

Bu CSV’yi aldıktan sonra:

- Klasör hiyerarşini benimle paylaşabilirsin,
- Birlikte yeni **mantıklı hiyerarşi + AI sınıflandırma** pipeline’ını tasarlarız,
- Ardından bu repo’ya **idempotent çalışan sınıflandırma kodlarını** ekleriz.

---
