#!/usr/bin/env bash
set -euo pipefail

out_dir="${1:-certs/dev}"
days="${DAYS:-365}"
p12_passphrase="${P12_PASSPHRASE:-dev-password}"

mkdir -p "${out_dir}"
chmod 700 "${out_dir}"

if [[ -e "${out_dir}/ca.crt" || -e "${out_dir}/client.crt" || -e "${out_dir}/server.crt" ]]; then
  cat >&2 <<EOF
Refusing to overwrite existing certs in ${out_dir}.
Delete the directory first or choose another output directory:

  $0 certs/another-dev-dir
EOF
  exit 1
fi

tmp_dir="$(mktemp -d)"
trap 'rm -rf "${tmp_dir}"' EXIT

cat >"${tmp_dir}/server.ext" <<'EOF'
basicConstraints=CA:FALSE
keyUsage=digitalSignature,keyEncipherment
extendedKeyUsage=serverAuth
subjectAltName=@alt_names

[alt_names]
DNS.1=localhost
IP.1=127.0.0.1
IP.2=::1
EOF

cat >"${tmp_dir}/client.ext" <<'EOF'
basicConstraints=CA:FALSE
keyUsage=digitalSignature,keyEncipherment
extendedKeyUsage=clientAuth
EOF

cat >"${tmp_dir}/ca.ext" <<'EOF'
basicConstraints=critical,CA:TRUE,pathlen:0
keyUsage=critical,keyCertSign,cRLSign
subjectKeyIdentifier=hash
EOF

openssl req -newkey rsa:4096 -nodes \
  -keyout "${out_dir}/ca.key" \
  -out "${tmp_dir}/ca.csr" \
  -subj "/CN=mcp-secure-remote-dev-ca" >/dev/null 2>&1

openssl x509 -req -in "${tmp_dir}/ca.csr" \
  -signkey "${out_dir}/ca.key" \
  -out "${out_dir}/ca.crt" \
  -days "${days}" \
  -sha256 \
  -extfile "${tmp_dir}/ca.ext" >/dev/null 2>&1

openssl req -newkey rsa:2048 -nodes \
  -keyout "${out_dir}/server.key" \
  -out "${tmp_dir}/server.csr" \
  -subj "/CN=localhost" >/dev/null 2>&1

openssl x509 -req -in "${tmp_dir}/server.csr" \
  -CA "${out_dir}/ca.crt" \
  -CAkey "${out_dir}/ca.key" \
  -CAserial "${tmp_dir}/ca.srl" \
  -CAcreateserial \
  -out "${out_dir}/server.crt" \
  -days "${days}" \
  -sha256 \
  -extfile "${tmp_dir}/server.ext" >/dev/null 2>&1

openssl req -newkey rsa:2048 -nodes \
  -keyout "${out_dir}/client.key" \
  -out "${tmp_dir}/client.csr" \
  -subj "/CN=mcp-secure-remote-dev-client" >/dev/null 2>&1

openssl x509 -req -in "${tmp_dir}/client.csr" \
  -CA "${out_dir}/ca.crt" \
  -CAkey "${out_dir}/ca.key" \
  -CAserial "${tmp_dir}/ca.srl" \
  -out "${out_dir}/client.crt" \
  -days "${days}" \
  -sha256 \
  -extfile "${tmp_dir}/client.ext" >/dev/null 2>&1

openssl pkcs12 -export \
  -inkey "${out_dir}/client.key" \
  -in "${out_dir}/client.crt" \
  -certfile "${out_dir}/ca.crt" \
  -out "${out_dir}/client.p12" \
  -passout "pass:${p12_passphrase}" >/dev/null 2>&1

chmod 600 "${out_dir}"/*.key "${out_dir}/client.p12"
chmod 644 "${out_dir}"/*.crt

cat <<EOF
Generated dev mTLS materials in ${out_dir}

Server:
  certificate: ${out_dir}/server.crt
  private key: ${out_dir}/server.key

Client:
  certificate: ${out_dir}/client.crt
  private key: ${out_dir}/client.key
  PKCS#12:     ${out_dir}/client.p12
  P12 pass:    ${p12_passphrase}

Trust anchor:
  CA bundle:   ${out_dir}/ca.crt
EOF
