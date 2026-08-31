#!/usr/bin/env bash
set -euo pipefail

OUT_DIR="${1:-.local-certs}"
mkdir -p "$OUT_DIR"
umask 077

openssl genrsa -out "$OUT_DIR/ca-key.pem" 4096
openssl req -x509 -new -nodes -key "$OUT_DIR/ca-key.pem" \
  -sha256 -days 3650 -out "$OUT_DIR/ca.pem" \
  -subj "/CN=RK Screencast Local CA"

openssl genrsa -out "$OUT_DIR/server-key.pem" 2048
openssl req -new -key "$OUT_DIR/server-key.pem" -out "$OUT_DIR/server.csr" \
  -subj "/CN=orangepi5pro"
cat > "$OUT_DIR/server-ext.cnf" <<'EOF'
basicConstraints=critical,CA:FALSE
keyUsage=critical,digitalSignature,keyEncipherment
extendedKeyUsage=serverAuth
subjectAltName=DNS:orangepi5pro,DNS:orangepi5pro.local,IP:192.168.50.1,IP:192.168.1.109
EOF
openssl x509 -req -in "$OUT_DIR/server.csr" -CA "$OUT_DIR/ca.pem" \
  -CAkey "$OUT_DIR/ca-key.pem" -CAcreateserial -out "$OUT_DIR/server-cert.pem" \
  -days 825 -sha256 -extfile "$OUT_DIR/server-ext.cnf"
cp "$OUT_DIR/server-cert.pem" "$OUT_DIR/cert.pem"
cp "$OUT_DIR/server-key.pem" "$OUT_DIR/key.pem"
rm -f "$OUT_DIR/server.csr" "$OUT_DIR/server-ext.cnf" "$OUT_DIR/ca.srl"
echo "Generated CA and server certificate in $OUT_DIR"
