# 1. Install Rancher Desktop
brew install --cask rancher

# 2. Open Rancher Desktop application
# - Wait for it to fully start
# - Ensure Kubernetes is enabled in Preferences
# - Wait for "Kubernetes: Running" status

# 3. Install Tailscale
brew install tailscale

# 4. Start Tailscale
sudo tailscale up
# - Open the URL provided in your browser
# - Log in or create a Tailscale account
# - Authenticate the device

# 5. Get your Mac's Tailscale IP
tailscale ip -4
# Note this IP (e.g., 100.x.x.x) - YOU'LL NEED IT!

# 6. Verify kubectl is working
kubectl get nodes
# Should see: lima-rancher-desktop node

# 7. Get the k3s server token
rdctl shell
sudo cat /var/lib/rancher/k3s/server/node-token
# COPY THIS TOKEN - YOU'LL NEED IT!
exit

# 8. (Optional) Add Tailscale IP to k3s certificate for better connectivity
rdctl shell
sudo mkdir -p /etc/rancher/k3s
sudo tee /etc/rancher/k3s/config.yaml > /dev/null <<EOF
tls-san:
  - $(tailscale ip -4)
EOF
sudo systemctl restart k3s
exit