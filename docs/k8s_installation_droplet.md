

#to install k3 on digital ocean machine

# Install the tailscale
curl -fsSL https://pkgs.tailscale.com/stable/ubuntu/noble.noarmor.gpg | sudo tee /usr/share/keyrings/tailscale-archive-keyring.gpg >/dev/null

curl -fsSL https://pkgs.tailscale.com/stable/ubuntu/noble.tailscale-keyring.list | sudo tee /etc/apt/sources.list.d/tailscale.list

snap  install tailscale 

# run tailscale
sudo tailscale up

# run this on mac and paste ip address below
tailscale ip -4

# test the k8s api
curl -k https://100.118.106.54:6443

# run this to connect
curl -sfL https://get.k3s.io | K3S_URL=https://<map-tailscale-ip>:6443   K3S_TOKEN=<token-from-mac-k3>   sh -