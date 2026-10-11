# Oracle Cloud Free Tier Instance erstellen

## Schritt 1: Einloggen
1. Gehe zu [cloud.oracle.com](https://cloud.oracle.com)
2. Logge dich mit deinem Account ein

## Schritt 2: Compute Instance erstellen

1. Klicke im Hamburger-Menü (☰) auf **Compute → Instances**
2. Klicke **Create Instance**

## Schritt 3: Instance konfigurieren

### Name
- Gib einen Namen ein: `openclaw-server`

### Placement
- Lass die Standardwerte

### Image and Shape

**Image ändern:**
1. Klicke auf **Edit** bei "Image and shape"
2. Klicke auf **Change image**
3. Wähle **Canonical Ubuntu**
4. Wähle **Ubuntu 24.04 Minimal aarch64** ⚠️ WICHTIG: aarch64 = ARM!
5. Klicke **Select image**

**Shape ändern:**
1. Klicke auf **Change shape**
2. Wähle **Ampere** (ARM-based processor)
3. Wähle **VM.Standard.A1.Flex**
4. Setze:
   - **OCPUs:** 4 (Maximum für Free Tier)
   - **Memory:** 24 GB (Maximum für Free Tier)
5. Klicke **Select shape**

### Networking
- Lass die Standardwerte (neues VCN wird erstellt)
- ✅ "Assign a public IPv4 address" muss aktiviert sein!

### Boot Volume
1. Klicke auf **Specify a custom boot volume size**
2. Setze **Boot volume size:** 200 GB
3. ✅ Lass "Use in-transit encryption" aktiviert

### SSH Keys ⚠️ WICHTIG
1. Wähle **Generate a key pair for me**
2. Klicke **Save private key** → Speichere die `.key` Datei!
3. Klicke **Save public key** → Speichere auch diese

**Speichere die Keys hier:**
```
~/.ssh/oracle_openclaw.key      (Private Key)
~/.ssh/oracle_openclaw.key.pub  (Public Key)
```

## Schritt 4: Instance erstellen
1. Klicke **Create**
2. Warte bis der Status von "PROVISIONING" zu **RUNNING** wechselt (1-5 Minuten)
3. **Kopiere die Public IP Address** - du brauchst sie gleich!

## Schritt 5: SSH Key vorbereiten

Nach dem Download, führe auf deinem Mac aus:
```bash
# Key in den richtigen Ordner verschieben
mv ~/Downloads/ssh-key-*.key ~/.ssh/oracle_openclaw.key

# Berechtigungen setzen (WICHTIG!)
chmod 600 ~/.ssh/oracle_openclaw.key
```

## Schritt 6: Verbinden

```bash
ssh -i ~/.ssh/oracle_openclaw.key ubuntu@<DEINE_SERVER_IP>
```

---

## Firewall-Regeln (nach dem Erstellen)

Oracle blockiert standardmäßig eingehenden Traffic. Für den Bot brauchst du nichts freigeben (er verbindet sich nach außen zu Telegram).

Falls du später einen Webserver willst:
1. Gehe zu **Networking → Virtual Cloud Networks**
2. Klicke auf dein VCN
3. Klicke auf **Security Lists → Default Security List**
4. **Add Ingress Rules** für Port 80/443

---

## Nächste Schritte

Sobald du verbunden bist, komm zurück und gib mir:
1. ✅ Die **Server IP-Adresse**
2. ✅ Den **Pfad zu deinem SSH Key**

Dann installiere ich OpenClaw automatisch!
