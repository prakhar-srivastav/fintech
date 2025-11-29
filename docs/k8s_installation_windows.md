# 1. Install WSL2 (if not already installed)
# Open PowerShell as Administrator:
wsl --install

# Restart your computer if prompted

# 2. Start WSL2 Ubuntu
wsl

# 3. Inside WSL2, install Tailscale
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
# Authenticate in browser

# 4. Get WSL Tailscale IP
tailscale ip -4

# 5. Test connectivity to Mac
ping <your-mac-tailscale-ip>
curl -k https://<your-mac-tailscale-ip>:6443

# 6. Install k3s as worker node
# REPLACE <mac-tailscale-ip> and <token> with your actual values!
curl -sfL https://get.k3s.io | K3S_URL=https://<mac-tailscale-ip>:6443 \
  K3S_TOKEN=<your-k3s-token-from-mac> \
  sh -

# 7. Check status
sudo systemctl status k3s-agent

# 8. View logs
sudo journalctl -u k3s-agent -f