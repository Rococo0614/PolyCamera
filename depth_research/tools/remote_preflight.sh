#!/usr/bin/env bash
set -euo pipefail

echo "[date]"
date --iso-8601=seconds

echo "[system]"
uname -a
if [ -f /etc/os-release ]; then
  cat /etc/os-release
fi

echo "[cpu]"
lscpu

echo "[memory]"
free -h

echo "[storage]"
df -hT

echo "[gpu]"
if command -v nvidia-smi >/dev/null 2>&1; then
  nvidia-smi
else
  echo "nvidia-smi not found"
fi

echo "[software]"
for command_name in git curl wget aria2c unzip python3 conda mamba uv tmux; do
  if command -v "${command_name}" >/dev/null 2>&1; then
    printf '%-10s ' "${command_name}"
    command -v "${command_name}"
  else
    printf '%-10s missing\n' "${command_name}"
  fi
done

echo "[python]"
python3 --version 2>/dev/null || true
python3 - <<'PY' 2>/dev/null || true
try:
    import torch
    print("torch", torch.__version__)
    print("torch_cuda", torch.version.cuda)
    print("cuda_available", torch.cuda.is_available())
    if torch.cuda.is_available():
        print("device", torch.cuda.get_device_name(0))
        print("capability", torch.cuda.get_device_capability(0))
except Exception as exc:
    print("torch_unavailable", repr(exc))
PY

echo "[network-head-checks]"
for url in \
  "https://github.com" \
  "https://pypi.org" \
  "https://www.campar.in.tum.de/public_datasets/2022_arxiv_jung/_dataset_processed.zip"; do
  echo "URL ${url}"
  curl -L -I --max-time 20 --silent --show-error "${url}" | head -n 8 || true
done
