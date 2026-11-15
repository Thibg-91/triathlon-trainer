# Héberger Triathlon Trainer sur un Raspberry Pi

Objectif : l'appli tourne 24h/24 sur un Raspberry Pi à la maison, et tu y accèdes depuis ton téléphone **depuis n'importe quel réseau** (4G, wifi extérieur), en HTTPS, sans ouvrir de port sur ta box.

```
Téléphone (4G)  ──Tailscale (chiffré)──▶  Pi : tailscale serve (HTTPS)  ──▶  uvicorn 127.0.0.1:8000
```

- **Tailscale** relie tes appareils dans un réseau privé (« tailnet »). Rien n'est exposé publiquement.
- **`tailscale serve`** fournit une adresse `https://<nom-du-pi>.<tailnet>.ts.net` avec un vrai certificat, nécessaire pour installer l'appli sur l'écran d'accueil.
- L'appli écoute uniquement en local (`127.0.0.1`) : seul Tailscale peut la joindre.

## Matériel

- Raspberry Pi 4 (2 Go de RAM suffisent largement)
- Carte microSD 16 Go+ (ou mieux : SSD en USB, plus fiable dans la durée)
- Alimentation officielle 5 V / 3 A

## 1. Préparer le Pi

1. Avec **Raspberry Pi Imager**, flasher **Raspberry Pi OS Lite (64-bit)**.
2. Dans les options de l'Imager (⚙️) : nom d'hôte (ex. `tri-pi`), utilisateur/mot de passe, wifi si besoin, **activer SSH**.
3. Démarrer le Pi, puis depuis ton PC :

```bash
ssh <utilisateur>@tri-pi.local
sudo apt update && sudo apt full-upgrade -y
sudo apt install -y git
```

> L'OS 64 bits (Bookworm ou plus récent, Python ≥ 3.11) est nécessaire.

## 2. Installer l'appli

```bash
git clone https://github.com/Thibg-91/triathlon-trainer.git
cd triathlon-trainer
./deploy/install.sh
```

Le script :

- crée un utilisateur système `triathlon` (sans shell, sans droits) ;
- copie l'appli dans `/opt/triathlon-trainer` avec son environnement Python ;
- stocke la base dans `/var/lib/triathlon-trainer/triathlon.db` ;
- installe le service systemd `triathlon-trainer` (démarrage automatique, redémarrage en cas de plantage) ;
- active une **sauvegarde quotidienne** de la base (3h30, conservée 30 jours).

Vérification sur le Pi : `curl http://127.0.0.1:8000/healthz` → `{"status":"ok"}`.

## 3. Accès distant avec Tailscale

### Sur le Pi

```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
```

Ouvre le lien affiché pour connecter le Pi à ton compte Tailscale (Google, GitHub, Microsoft…).

### Activer HTTPS (une seule fois)

Dans la console d'admin Tailscale (https://login.tailscale.com/admin/dns) :

1. vérifier que **MagicDNS** est activé ;
2. activer **HTTPS Certificates**.

### Publier l'appli dans le tailnet

```bash
./deploy/install.sh --serve
```

(équivaut à `sudo tailscale serve --bg http://127.0.0.1:8000`). Si Serve n'est pas encore autorisé sur ton tailnet, la commande affiche un lien pour l'activer : ouvre-le puis relance.

La commande affiche l'adresse, du type `https://tri-pi.ton-tailnet.ts.net`. Grâce à `--bg`, la publication **reprend toute seule après un redémarrage** du Pi.

### Sur le téléphone

1. Installer l'app **Tailscale** (App Store / Play Store) et se connecter avec le même compte.
2. Ouvrir `https://tri-pi.ton-tailnet.ts.net`.
3. Installer l'appli :
   - **iPhone (Safari)** : Partager → « Sur l'écran d'accueil » ;
   - **Android (Chrome)** : menu ⋮ → « Installer l'application ».

Laisse Tailscale activé sur le téléphone (il consomme très peu de batterie).

## Au quotidien

| Action | Commande (sur le Pi) |
|---|---|
| Voir les logs | `sudo journalctl -u triathlon-trainer -f` |
| Redémarrer | `sudo systemctl restart triathlon-trainer` |
| État du service | `systemctl status triathlon-trainer` |
| Mettre à jour | `cd ~/triathlon-trainer && git pull && ./deploy/install.sh` |
| Sauvegarde immédiate | `sudo systemctl start triathlon-trainer-backup` |
| Lister les sauvegardes | `sudo ls -lt /var/lib/triathlon-trainer/backups` |
| Restaurer | `sudo ./deploy/restore.sh /var/lib/triathlon-trainer/backups/<fichier>.db.gz` |
| Arrêter la publication | `sudo tailscale serve reset` |

La configuration (port, adresse d'écoute, durée de conservation) se trouve dans `/etc/default/triathlon-trainer`.

### Sauvegardes hors du Pi

Les sauvegardes restent sur la carte SD : si elle lâche, elles disparaissent avec. Pour en garder une copie ailleurs, depuis ton PC :

```bash
scp "<utilisateur>@tri-pi.local:/var/lib/triathlon-trainer/backups/*.gz" ~/sauvegardes-tri/
```

(nécessite d'ajouter ton utilisateur au groupe : `sudo usermod -aG triathlon $USER`, puis te reconnecter.)

## Accès depuis le réseau local sans Tailscale (optionnel)

Dans `/etc/default/triathlon-trainer`, mettre `TRI_HOST=0.0.0.0`, puis `sudo systemctl restart triathlon-trainer`. L'appli est alors aussi joignable en `http://tri-pi.local:8000` depuis la maison (en HTTP, donc pas installable comme appli).

## ⚠️ Sécurité

L'appli **n'a pas d'authentification**. C'est sans risque avec `tailscale serve`, car seuls les appareils de ton tailnet y ont accès. En revanche :

- **ne pas** utiliser `tailscale funnel` (qui publie sur Internet) ;
- **ne pas** ouvrir de port sur la box vers le Pi.

…tant qu'un système de connexion n'a pas été ajouté à l'appli.

## Dépannage

- **Le service ne démarre pas** : `sudo journalctl -u triathlon-trainer -n 50`.
- **Erreur 502 via l'URL Tailscale** : vérifier que l'appli répond en local (`curl http://127.0.0.1:8000/healthz`) et que la cible de `tailscale serve status` est bien `http://127.0.0.1:8000`.
- **Le téléphone n'ouvre pas l'adresse `.ts.net`** : vérifier que Tailscale est connecté sur le téléphone et que MagicDNS est activé.
- **Après une mise à jour, l'ancien affichage persiste** : fermer complètement l'appli sur le téléphone et la rouvrir (le service worker se met à jour au lancement suivant).
